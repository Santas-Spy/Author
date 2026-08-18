from turtle import done

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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


class LoadChatRequest(BaseModel):
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


@app.on_event("startup")
def startup_event():
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))


@app.post("/api/chat")
def send_message(req: ChatRequest):
    chat_id = req.chat_id
    user_message = req.message

    orchestrator.sendUserMessage(chat_id, user_message)
    chat_data = chathandler.loadChatData(chat_id)
    if len(chat_data["text"]) > 500:
        orchestrator.summarizeConversation(chat_id)
        orchestrator.catagorizeConversation(chat_id)
        orchestrator.analyzeConversation(chat_id)
        orchestrator.generateTitle(chat_id)
    return _packageChatData(chat_data, chat_id)


@app.post("/api/listChats")
def list_chats():
    subdirs = chathandler.listChatIDs()
    return {"chatIDs": subdirs}


@app.post("/api/loadChat")
def load_messages(req: LoadChatRequest):
    chat_id = req.chat_id
    chat_data = chathandler.loadChatData(chat_id)
    return _packageChatData(chat_data, chat_id)


@app.get("/api/status")
def get_status():
    return orchestrator.getStatus()


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
