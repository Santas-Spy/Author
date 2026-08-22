import json
import threading
from turtle import done

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool

import ai.orchestrator as orchestrator
import chathandler
import config
from ai.kobold import koboldInstance

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

state = {"status": "ready", "message": "Ready"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    chat_id: int
    message: str


class UpdateChatRequest(BaseModel):
    chat_id: int
    text: str


class ChatActionRequest(BaseModel):
    chat_id: int


def _packageChatData(raw_data, chat_id):
    valid_keys = [
        "text",
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


def run_post_processing(chat_id: int):
    orchestrator.summarizeConversation(chat_id)
    orchestrator.catagorizeConversation(chat_id)
    orchestrator.analyzeConversation(chat_id)
    orchestrator.generateTitle(chat_id)
    orchestrator.setStatus("ready", "Ready")


def check_run_background_processing():
    # Check task is not already running
    if orchestrator.process_chats_flag == "working":
        print("Processing Task was already running")

    if orchestrator.process_chats_flag == "cancel":
        print("Processing Task was waiting to cancel")

    if orchestrator.process_chats_flag == "ready":
        # Check current app state
        if state["status"] == "ready":
            print("Running processing while idle")
            orchestrator.processChatsInBackground()
            print("Finished background processing")
        else:
            print("Checked processing but server was busy")

    timer = threading.Timer(10.0, check_run_background_processing)
    timer.start()


@app.on_event("startup")
def startup_event():
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))
    timer = threading.Timer(10.0, check_run_background_processing)
    timer.start()


@app.post("/api/chat")
async def send_message(req: ChatRequest, background_tasks: BackgroundTasks):
    orchestrator.cancelProcessing()
    chat_id = req.chat_id
    user_message = req.message

    def token_gen():
        for item in orchestrator.sendUserMessage(chat_id, user_message):
            yield json.dumps(item) + "\n"

    return StreamingResponse(
        iterate_in_threadpool(token_gen()),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no"},  # stop nginx-style proxies from buffering
    )


@app.post("/api/listChats")
def list_chats():
    subdirs = chathandler.listChatIDs()
    return {"chatIDs": subdirs}


@app.post("/api/processChat")
def process_chat(req: ChatActionRequest, background_tasks: BackgroundTasks):
    chat_id = req.chat_id
    run_post_processing(chat_id)
    return chathandler.loadChatData(chat_id)


@app.post("/api/loadChat")
def load_messages(req: ChatActionRequest):
    chat_id = req.chat_id
    chat_data = chathandler.loadChatData(chat_id)
    return _packageChatData(chat_data, chat_id)


@app.post("/api/deleteAllChats")
def delete_all_chats():
    orchestrator.cancelProcessing()
    orchestrator.stopGeneration()
    chathandler.deleteAllChats()


@app.post("/api/deleteChat")
def delete_chat(req: ChatActionRequest):
    orchestrator.cancelProcessing()
    orchestrator.stopGeneration()
    chathandler.deleteChat(req.chat_id)


@app.get("/api/status")
def get_status():
    return orchestrator.getStatus()


@app.post("/api/updateChat")
def update_chat(req: UpdateChatRequest):
    chat_id = req.chat_id
    text = req.text
    chathandler.saveChat(chat_id, text)


@app.post("/api/stop")
def stop_generation():
    orchestrator.stopGeneration()


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
