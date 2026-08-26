import datetime
import json
from json import JSONDecodeError

import config
import databasehandler
from ai import chatformatter
from ai.kobold import KoboldError, koboldInstance

state = {"status": "ready", "message": "Ready"}
process_chats_flag = "ready"


def sendMessage(text: str):
    return koboldInstance.sendMessage(text)


def chooseModel(message: str):
    return  # Skip this for now since model loading isn't supported
    setStatus("working", "Choosing Model")
    text = config.readSetting("prompts.choose_model")
    text = text.replace("{request}", message)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    setStatus("ready", "Ready")
    koboldInstance.loadModel(answer)


def summarizeConversation(chat_id: str):
    db = databasehandler.DatabaseHandler()
    setStatus("working", f"Summarizing chat {chat_id}")

    # Build the prompt
    prompt = config.readSetting("prompts.summarize_conversation")
    chat_text = db.load_conversation(chat_id)["content"]
    chat_text = chatformatter.cleanPlaceholders(
        chat_text
    )  # Clean the text so model can read conversation flow
    text = prompt.replace("{history}", chat_text)
    word_count = len(chat_text.split(" "))

    if word_count > 500:
        text = text.replace(
            "{max_length}", str(min(word_count / 3, 150))
        )  # Hardcoding summary to 150 words for now

        # Generate a summary
        response = koboldInstance.sendMessage(text)
        split_response = chatformatter.seperateThinking(response)
        answer = split_response["response"]

        # Save the summary
        db.update_conversation(chat_id, {"summary": answer, "processedSummary": True})
        new_word_count = len(answer.split(" "))
        print(f"Summarized conversation of length {word_count} to {new_word_count}")
    setStatus("ready", "Ready")


def analyzeConversation(chat_id: str):
    return
    setStatus("working", f"Analyzing chat {chat_id}")
    prompt = config.readSetting("prompts.analyze_conversation")
    chat_text = DatabaseHandler.load_conversation(chat_id)["content"]
    chat_text = chatformatter.cleanPlaceholders(
        chat_text
    )  # Clean the text so model can read conversation flow
    userFacts = chathandler.loadAnalysis()
    text = prompt.replace("{history}", chat_text).replace("{user_facts}", userFacts)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]

    if answer.strip() != "" and answer.strip() != "[]":
        result = answer
        try:
            factsJson = json.loads(userFacts)
            answerJson = json.loads(answer)
            factsJson.extend(answerJson)
            result = json.dumps(factsJson)
        except JSONDecodeError:
            print("Warning. Tried to append new user facts but could not parse json")

        chathandler.saveAnalysis(result)
    chathandler.saveChatData(chat_id, processedAnalysis=True)
    setStatus("ready", "Ready")


def catagorizeConversation(chat_id: str):
    db = databasehandler.DatabaseHandler()
    setStatus("working", f"Catagorizing chat {chat_id}")
    prompt = config.readSetting("prompts.catagorize_conversation")
    chat_text = db.load_conversation(chat_id)["content"]
    chat_text = chatformatter.cleanPlaceholders(
        chat_text
    )  # Clean the text so model can read conversation flow
    text = prompt.replace("{history}", chat_text)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    db.update_conversation(chat_id, {"tags": answer, "processedCatagories": True})
    setStatus("ready", "Ready")


def generateTitle(chat_id: str):
    db = databasehandler.DatabaseHandler()
    setStatus("working", f"Generating Title for chat {chat_id}")
    prompt = config.readSetting("prompts.title_generation")
    chat_text = db.load_conversation(chat_id)["content"]
    chat_text = chatformatter.cleanPlaceholders(
        chat_text
    )  # Clean the text so model can read conversation flow
    text = prompt.replace("{history}", chat_text)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    db.update_conversation(chat_id, {"title": answer, "processedTitle": True})
    setStatus("ready", "Ready")


def sendUserMessage(chat_id: str, user_message: str):
    db = databasehandler.DatabaseHandler()
    chat_data = db.load_conversation(chat_id)

    # Build the prompt
    prompt = config.readSetting("prompts.system")
    if "system_prompt" in chat_data:
        prompt = chat_data["system_prompt"]
        if prompt is None:
            prompt = ""
    db.update_conversation(chat_id, {"system_prompt": prompt})

    # Build the conversation history
    chatText = ""
    if "text" in chat_data:
        chatText = chat_data["text"]

    # Allow continuations
    if user_message != None and user_message != "":
        chatText = chatText + "{{[INPUT]}}" + user_message + "{{[OUTPUT]}}"
        db.update_conversation(chat_id, {"content": chatText})

    # Fill in placeholders
    user_profile = "{}"

    current_date = datetime.datetime.now().strftime("%c")
    prompt = prompt.replace("{user_profile}", user_profile)
    prompt = prompt.replace("{date}", current_date)

    # Choose the model
    chooseModel(user_message)

    # Send the message, streaming tokens as they arrive
    setStatus("working", f"Thinking about chat {chat_id}")
    message = prompt + chatText
    streamed_response = ""
    for token in koboldInstance.generate(message):
        setStatus("working", f"Writing in chat {chat_id}")
        streamed_response += token
        yield {"type": "token", "chat_id": str(chat_id), "token": token}
        print(token, end="", flush=True)
    print()
    split_response = chatformatter.seperateThinking(streamed_response)
    chatText = chatText + split_response["response"]
    db.update_conversation(chat_id, {"content": chatText})
    setStatus("ready", "Ready")

    yield {"type": "complete", "chat_id": str(chat_id), "text": chatText}


def setStatus(status: str = "working", message: str = ""):
    global state
    if state["status"] == status and state["message"] == message:
        return

    print("Set state: " + json.dumps(state), flush=True)
    state = {"status": status, "message": message}


def processChatsInBackground():
    db = databasehandler.DatabaseHandler()
    global process_chats_flag
    process_chats_flag = "working"
    chat_info = db.list_chat_ids()
    try:
        for data in chat_info:
            id = data["id"]
            flags = db.check_conversation_status(id)
            print(flags)

            if process_chats_flag == "cancel":
                return
            if flags["processedSummary"] == 0:
                summarizeConversation(id)

            if process_chats_flag == "cancel":
                return
            if flags["processedTags"] == 0:
                catagorizeConversation(id)

            if process_chats_flag == "cancel":
                return
            if flags["processedAnalysis"] == 0:
                analyzeConversation(id)

            if process_chats_flag == "cancel":
                return
            if flags["processedTitle"] == 0:
                generateTitle(id)
    except KoboldError:
        print("Kobold instance was not running. Could not process chats")

    process_chats_flag = "ready"


def cancelProcessing():
    global process_chats_flag
    process_chats_flag = "cancel"
    stopGeneration()
    process_chats_flag = "ready"


def stopGeneration():
    koboldInstance.stopGeneration()


def getStatus():
    return state
