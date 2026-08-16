import datetime
import json
from json import JSONDecodeError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import chathandler
import config
from ai import chatformatter
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

"""
Flow Chart
-----------

* User Sends Message
* Tiny Model decides where to route
* Load decided Model
* Send request and wait for response
* Display Response
* If context > max context then summarize
* Every few minutes scan all conversations and build a user profile
"""


class ChatRequest(BaseModel):
    chat_id: int
    message: str


class LoadChatRequest(BaseModel):
    chat_id: int


def sendMessage(text):
    return koboldInstance.sendMessage(text)


def chooseModel(message):
    setStatus("working", "Choosing Model")
    text = config.readSetting("prompts.choose_model")
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    setStatus("ready", "Ready")


def summarizeConversation(chat_id):
    setStatus("working", "Summarizing")
    prompt = config.readSetting("prompts.summarize_conversation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    text = text.replace("{max_length}", str(int(len(chatText) / 2)))
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, summary=answer)
    setStatus("ready", "Ready")


def analyzeConversation(chat_id):
    setStatus("working", "Analyzing")
    prompt = config.readSetting("prompts.analyze_conversation")
    chatText = chathandler.loadChat(chat_id)
    userFacts = chathandler.loadAnalysis()
    text = prompt.replace("{history}", chatText).replace("{user_facts}", userFacts)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]

    result = answer
    try:
        factsJson = json.loads(userFacts)
        answerJson = json.loads(answer)
        factsJson.extend(answerJson)
        result = json.dumps(factsJson)
    except JSONDecodeError:
        print("Warning. Could not parse json from model")

    chathandler.saveAnalysis(result)
    setStatus("ready", "Ready")


def catagorizeConversation(chat_id):
    setStatus("working", "Catagorizing")
    prompt = config.readSetting("prompts.catagorize_conversation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, tags=answer)
    setStatus("ready", "Ready")


def generateTitle(chat_id):
    setStatus("working", "Generating Title")
    prompt = config.readSetting("prompts.title_generation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, title=answer)
    setStatus("ready", "Ready")


def sendUserMessage(chat_id, user_message):
    # Build the prompt
    prompt = config.readSetting("prompts.system")
    chatText = chathandler.loadChat(chat_id)
    chatText = chatText + "{{[INPUT]}}" + user_message + "{{[OUTPUT]}}"
    chathandler.saveChat(chat_id, chatText)

    # Fill in placeholders
    user_profile = chathandler.loadAnalysis()
    current_date = datetime.datetime.now().strftime("%c")
    prompt = prompt.replace("{user_profile}", user_profile)
    prompt = prompt.replace("{date}", current_date)

    # Choose the model
    model = chooseModel(user_message)
    koboldInstance.loadModel(model)

    # Send the message
    setStatus("working", "Thinking")
    message = prompt + chatText
    response = sendMessage(message)
    split_response = chatformatter.seperateThinking(response)
    chatText = chatText + split_response["response"]
    chathandler.saveChat(chat_id, chatText)
    setStatus("ready", "Ready")

    return chatText


def chatLoop(chat_id, user_message):
    chatText = sendUserMessage(chat_id, user_message)

    print("Chat Length: " + str(len(chatText)))
    if len(chatText) > 500:
        print("Summarizing Conversation")
        summarizeConversation(chat_id)
        print("Catagorizing Conversation")
        catagorizeConversation(chat_id)
        print("Analyzing Conversation")
        analyzeConversation(chat_id)
        print("Generating Title")
        generateTitle(chat_id)


def startProgram():
    running = True
    chat_id = 2
    chatText = ""
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))
    while running:
        user_message = input("> ")
        if user_message == "new":
            chat_id = chat_id + 1
            print("New ID: " + str(chat_id))
        else:
            chatLoop(chat_id, user_message)


def setStatus(status="working", message=""):
    global state
    print("Set state: " + json.dumps(state))
    state = {"status": status, "message": message}


@app.on_event("startup")
def startup_event():
    koboldInstance.setEndpoint(config.readSetting("kobold.url"))


@app.post("/api/chat")
def send_message(req: ChatRequest):
    chat_id = req.chat_id
    user_message = req.message

    chatLoop(chat_id, user_message)
    chat_text = chathandler.loadChat(chat_id)

    return {"text": chat_text}


@app.post("/api/loadChat")
def load_messages(req: LoadChatRequest):
    chat_id = req.chat_id
    chat_text = chathandler.loadChat(chat_id)
    return {"text": chat_text}


@app.get("/api/status")
def get_status():
    global state
    return state


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")
