import datetime
import json
from json import JSONDecodeError

import chathandler
import config
from ai import chatformatter
from ai.kobold import KoboldError, koboldInstance

state = {"status": "ready", "message": "Ready"}
process_chats_flag = False


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


def summarizeConversation(chat_id: int):
    setStatus("working", f"Summarizing chat {chat_id}")

    # Build the prompt
    prompt = config.readSetting("prompts.summarize_conversation")
    chat_text = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chat_text)
    word_count = len(chat_text.split(" "))
    text = text.replace("{max_length}", str(word_count))

    # Generate a summary
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]

    # Save the summary
    chathandler.saveChatData(chat_id, summary=answer, processedSummary=True)
    new_word_count = len(answer.split(" "))
    print(f"Summarized conversation of length {word_count} to {new_word_count}")
    setStatus("ready", "Ready")


def analyzeConversation(chat_id: int):
    setStatus("working", f"Analyzing chat {chat_id}")
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
    chathandler.saveChatData(chat_id, processedAnalysis=True)
    setStatus("ready", "Ready")


def catagorizeConversation(chat_id: int):
    setStatus("working", f"Catagorizing chat {chat_id}")
    prompt = config.readSetting("prompts.catagorize_conversation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, tags=answer, processedCatagories=True)
    setStatus("ready", "Ready")


def generateTitle(chat_id: int):
    setStatus("working", f"Generating Title for chat {chat_id}")
    prompt = config.readSetting("prompts.title_generation")
    chatText = chathandler.loadChat(chat_id)
    text = prompt.replace("{history}", chatText)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    chathandler.saveChatData(chat_id, title=answer, processedTitle=True)
    setStatus("ready", "Ready")


def sendUserMessage(chat_id: int, user_message: str):
    chat_data = chathandler.loadChatData(chat_id)

    # Build the prompt
    prompt = config.readSetting("prompts.system")
    if "system_prompt" in chat_data:
        prompt = chat_data["system_prompt"]
        if prompt is None:
            prompt = ""
    chathandler.saveChatData(chat_id, system_prompt=prompt)

    # Build the conversation history
    chatText = ""
    if "text" in chat_data:
        chatText = chat_data["text"]

    # Allow continuations
    if user_message != None and user_message != "":
        chatText = chatText + "{{[INPUT]}}" + user_message + "{{[OUTPUT]}}"
        chathandler.saveChat(chat_id, chatText)

    # Fill in placeholders
    user_profile = "[]"
    if "analysis" in chat_data:
        user_profile = chat_data["analysis"]

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
        yield {"type": "token", "chat_id": chat_id, "token": token}
        print(token, end="", flush=True)
    print()
    split_response = chatformatter.seperateThinking(streamed_response)
    chatText = chatText + split_response["response"]
    chathandler.saveChat(chat_id, chatText)
    setStatus("ready", "Ready")

    yield {"type": "complete", "chat_id": chat_id, "text": chatText}


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


def setStatus(status: str = "working", message: str = ""):
    global state
    if state["status"] == status and state["message"] == message:
        return

    print("Set state: " + json.dumps(state), flush=True)
    state = {"status": status, "message": message}


def processChatsInBackground():
    global process_chats_flag
    process_chats_flag = True
    chat_ids = chathandler.listChatIDs()
    try:
        for chat_id, title in enumerate(chat_ids):
            chat_data = chathandler.loadChatData(chat_id)
            if "text" not in chat_data or chat_data["text"] == "":
                continue

            if not process_chats_flag:
                return
            if "processedSummary" not in chat_data or chat_data["processedSummary"] == False:
                summarizeConversation(chat_id)

            if not process_chats_flag:
                return
            if "processedCatagories" not in chat_data or chat_data["processedCatagories"] == False:
                catagorizeConversation(chat_id)

            if not process_chats_flag:
                return
            if "processedAnalysis" not in chat_data or chat_data["processedAnalysis"] == False:
                analyzeConversation(chat_id)

            if not process_chats_flag:
                return
            if "processedTitle" not in chat_data or chat_data["processedTitle"] == False:
                generateTitle(chat_id)
    except KoboldError:
        print("Kobold instance was not running. Could not process chats")
        process_chats_flag = True
    finally:
        process_chats_flag = True


def cancelProcessing():
    global process_chats_flag
    process_chats_flag = False
    stopGeneration()


def stopGeneration():
    koboldInstance.stopGeneration()


def getStatus():
    return state
