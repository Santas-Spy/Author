import asyncio
import json
import logging
import sys
import threading
import time
from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from requests.models import Response
from starlette.concurrency import iterate_in_threadpool
from typing_extensions import AsyncGenerator

import ai.orchestrator as orchestrator
import config
import databasehandler
import signals
import state.settings as settings
from ai.kobold import KoboldError, koboldInstance
from state.state import stateManager

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
# Configure once at module level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,  # or sys.stderr
)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    chat_id: str
    message: str
    force_thinking: bool


class SettingsRequest(BaseModel):
    settings: dict[str, Any]


SettingsRequest.model_rebuild()


class UpdateChatRequest(BaseModel):
    chat_id: str
    model_config = ConfigDict(extra="allow")


class ChatActionRequest(BaseModel):
    chat_id: str


def _packageChatData(raw_data, chat_id):
    valid_keys = [
        "content",
        "summary",
        "tags",
        "title",
        "system_prompt",
        "analysis_prompt",
    ]
    data = {"chat_id": chat_id}
    for key in valid_keys:
        if key in raw_data:
            data[key] = raw_data[key]

    return data


def run_post_processing(chat_id: str):
    orchestrator.generateTitle(chat_id)
    orchestrator.summarizeConversation(chat_id)
    orchestrator.catagorizeConversation(chat_id)
    orchestrator.analyzeConversation(chat_id)
    orchestrator.state.ready()
    signals.emit_signal("chat_update", {"chat_id": chat_id})


async def check_run_background_processing():
    while True:
        orchestrator.processChatsInBackground()
        await asyncio.sleep(10)


@app.on_event("startup")
def startup_event():
    settings.reload_config()
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))
    asyncio.create_task(check_run_background_processing())


@app.on_event("shutdown")
def on_shutdown():
    signals.close_all_streams()


@app.post("/api/chat")
async def send_message(req: ChatRequest, background_tasks: BackgroundTasks):
    try:
        orchestrator.cancelProcessing()
        chat_id = req.chat_id
        user_message = req.message
        force_thinking = req.force_thinking

        def token_gen():
            for item in orchestrator.sendUserMessage(chat_id=chat_id, user_message=user_message, force_thinking=force_thinking):
                yield json.dumps(item) + "\n"

            signals.emit_signal("chat_update", {"chat_id": chat_id})

        return StreamingResponse(
            iterate_in_threadpool(token_gen()),
            media_type="text/plain; charset=utf-8",
            headers={"X-Accel-Buffering": "no"},  # stop nginx-style proxies from buffering
        )
    except KoboldError as error:
        logger.error(error)
        return {"type": "error", "chat_id": req.chat_id, "message": error.args}


@app.post("/api/listChats")
def list_chats():
    db = databasehandler.DatabaseHandler()
    return {"chatIDs": db.list_chat_ids()}


@app.post("/api/processChat")
def process_chat(req: ChatActionRequest, background_tasks: BackgroundTasks):
    try:
        db = databasehandler.DatabaseHandler()
        chat_id = req.chat_id
        run_post_processing(chat_id)
        return db.load_conversation(chat_id)
    except KoboldError as error:
        logger.error(error)
        return {"type": "error", "chat_id": req.chat_id, "message": error.args}


@app.post("/api/loadChat")
def load_messages(req: ChatActionRequest):
    chat_id = req.chat_id
    if chat_id is None:
        logger.info("Chat_id was None for LoadChat")
        return

    db = databasehandler.DatabaseHandler()
    chat_data = db.load_conversation(chat_id)
    return chat_data


@app.post("/api/deleteAllChats")
def delete_all_chats():
    db = databasehandler.DatabaseHandler()
    orchestrator.cancelProcessing()
    orchestrator.stopGeneration()
    db.delete_all_chats()


@app.post("/api/deleteChat")
def delete_chat(req: ChatActionRequest):
    db = databasehandler.DatabaseHandler()
    chat_id = req.chat_id
    orchestrator.cancelProcessing()
    orchestrator.stopGeneration()
    db.delete_chat(chat_id)


@app.get("/api/status")
def get_status():
    return stateManager.get_state()


@app.post("/api/updateChat")
def update_chat(req: UpdateChatRequest):
    data = req.model_dump()
    orchestrator.update_conversation(data)


@app.post("/api/stop")
def stop_generation():
    try:
        orchestrator.stopGeneration()
    except KoboldError as error:
        logger.error(error)
        return {"type": "error", "message": error.args}


@app.post("/api/generateID")
def generate_ID():
    logger.info("Creating ID")
    db = databasehandler.DatabaseHandler()
    new_id = db.create_conversation()
    return {"id": new_id}


@app.post("/api/regenerateTitle")
def regenerate_title(req: ChatActionRequest):
    chat_id = req.chat_id
    orchestrator.update_conversation({"chat_id": chat_id, "processedTitle": False})
    signals.emit_signal("title_update", {"chat_id": chat_id})


@app.get("/api/events")
async def sse_event_stream():
    return StreamingResponse(
        signals.generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/getSettings")
async def get_settings():
    return settings.settings


@app.post("/api/saveSettings")
async def save_setting(req: SettingsRequest):
    settings.update_settings(req.settings)
    print("Settings updated")


@app.post("/api/reloadSettings")
async def reload_setting():
    settings.reload_config()
    print("Settings reloaded")


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
