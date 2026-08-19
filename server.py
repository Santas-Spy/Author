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


def run_post_processing(chat_id):
    chat_data = chathandler.loadChatData(chat_id)
    if len(chat_data["text"]) > 500:
        orchestrator.summarizeConversation(chat_id)
        orchestrator.catagorizeConversation(chat_id)
        orchestrator.analyzeConversation(chat_id)
        orchestrator.generateTitle(chat_id)
        orchestrator.setStatus("ready", "Ready")


@app.on_event("startup")
def startup_event():
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))


@app.post("/api/chat")
async def send_message(req: ChatRequest, background_tasks: BackgroundTasks):
    chat_id = req.chat_id
    user_message = req.message

    def token_gen():
        yield from orchestrator.sendUserMessage(chat_id, user_message)

    background_tasks.add_task(run_post_processing, chat_id)

    return StreamingResponse(
        iterate_in_threadpool(token_gen()),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no"},  # stop nginx-style proxies from buffering
    )


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


@app.post("/api/updateChat")
def update_chat(req: UpdateChatRequest):
    chat_id = req.chat_id
    text = req.text
    chathandler.saveChat(chat_id, text)


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
