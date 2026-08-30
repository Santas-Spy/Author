import json
import logging
import sys
import threading

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import iterate_in_threadpool

import ai.orchestrator as orchestrator
import config
import databasehandler
from ai import chatformatter
from ai.kobold import KoboldError, koboldInstance

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
# Configure once at module level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,  # or sys.stderr
)
logger = logging.getLogger(__name__)
state = {"status": "ready", "message": "Ready"}


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


def check_run_background_processing():
    thread = threading.Thread(target=orchestrator.processChatsInBackground)
    thread.start()


@app.on_event("startup")
def startup_event():
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))
    check_run_background_processing()


@app.post("/api/chat")
async def send_message(req: ChatRequest, background_tasks: BackgroundTasks):
    try:
        orchestrator.cancelProcessing()
        chat_id = req.chat_id
        user_message = req.message
        force_thinking = req.force_thinking

        def token_gen():
            for item in orchestrator.sendUserMessage(
                chat_id=chat_id,
                user_message=user_message,
                force_thinking=force_thinking,
                use_tools=True,
            ):
                yield json.dumps(item) + "\n"

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
    # THIS IS SO BAD but it'll do for now. Use webpage's polling to schedule background processing
    check_run_background_processing()
    return orchestrator.getStatus()


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


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
