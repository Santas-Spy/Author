from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chathandler
import config
from ai import chatformatter
from ai.kobold import koboldInstance

app = FastAPI()


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


def sendMessage(text):
    return koboldInstance.sendMessage(text)


def chooseModel(message):
    text = config.readSetting("prompts.choose_model")
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]


def summarizeConversation(chat_id):
    prompt = config.readSetting("prompts.summarize_conversation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, summary=answer)


def analyzeConversation(chat_id):
    prompt = config.readSetting("prompts.analyze_conversation")
    chatText = chathandler.loadChat(chat_id)
    userFacts = chathandler.loadAnalysis(chat_id)
    text = prompt.replace("{history}", chatText).replace("{user_facts}", userFacts)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, analysis=answer)


def catagorizeConversation(chat_id):
    prompt = config.readSetting("prompts.catagorize_conversation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, tags=answer)


def chatLoop(chat_id, user_message):
    chatText = chathandler.loadChat(chat_id)
    chatText = chatText + "{{[INPUT]}}" + user_message + "{{[OUTPUT]}}"
    chathandler.saveChat(chat_id, chatText)

    model = chooseModel(user_message)
    koboldInstance.loadModel(model)

    response = sendMessage(chatText)
    split_response = chatformatter.seperateThinking(response)
    chatText = chatText + split_response["response"]
    print(split_response["response"])
    chathandler.saveChat(chat_id, chatText)

    print("Chat Length: " + str(len(chatText)))
    if len(chatText) > 500:
        print("Summarizing Conversation")
        summarizeConversation(chat_id)
        print("Catagorizing Conversation")
        catagorizeConversation(chat_id)
        print("Analyzing Conversation")
        analyzeConversation(chat_id)


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
