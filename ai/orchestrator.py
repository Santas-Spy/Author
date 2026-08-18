import datetime
import json
from json import JSONDecodeError

import chathandler
import config
from ai import chatformatter
from ai.kobold import koboldInstance

state = {"status": "ready", "message": "Ready"}


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
            sendUserMessage(chat_id, user_message)
            chat_data = chathandler.loadChatData(chat_id)
            if len(chat_data["text"]) > 500:
                summarizeConversation(chat_id)
                catagorizeConversation(chat_id)
                analyzeConversation(chat_id)
                generateTitle(chat_id)


def setStatus(status="working", message=""):
    global state
    print("Set state: " + json.dumps(state))
    state = {"status": status, "message": message}


def getStatus():
    return state
