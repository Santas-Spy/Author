import datetime
import json
import threading
from enum import Enum
from json import JSONDecodeError

import config
import databasehandler
from ai import chatformatter
from ai.kobold import KoboldError, koboldInstance


class OrchestratorState(Enum):
    READY = "ready"
    WORKING = "working"
    OFFLINE = "offline"


class StateManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._status: OrchestratorState = OrchestratorState.READY
        self._message: str = "Ready"
        self._canceled: threading.Event = threading.Event()

    def _set(self, status: OrchestratorState, message: str):
        with self._lock:
            if self._status == status and self._message == message:
                return
            self._status = status
            self._message = message
            print(f"State -> {status.value}: {message}", flush=True)

    def _format_message(self, message, id):
        if id:
            db = databasehandler.DatabaseHandler()
            chat_name = id
            title = db.get_chat_title(id)
            if title is not None:
                chat_name = title
            message = message.format(title=chat_name)
        return message

    def ready(self, message: str, chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.READY, message)

    def working(self, message: str, chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.WORKING, message)

    def offline(self, message: str, chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.OFFLINE, message)

    def cancel(self):
        self._canceled.set()

    def clear_cancel(self):
        self._canceled.clear()

    def is_canceled(self):
        return self._canceled.is_set()

    def get_state(self):
        with self._lock:
            return {"status": self._status.value, "message": self._message}


process_chats_flag = "ready"
state = StateManager()


def sendMessage(text: str):
    return koboldInstance.sendMessage(text)


def chooseModel(message: str):
    return  # Skip this for now since model loading isn't supported
    state.working("Choosing Model")
    text = config.readSetting("prompts.choose_model")
    text = text.replace("{request}", message)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    state.ready("Ready")
    koboldInstance.loadModel(answer)


def summarizeConversation(chat_id: str):
    db = databasehandler.DatabaseHandler()
    state.working("Summarizing chat {title}", chat_id=chat_id)

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
        db.update_conversation(chat_id, {"summary": answer})
        new_word_count = len(answer.split(" "))
        print(f"Summarized conversation of length {word_count} to {new_word_count}")
    db.update_conversation(chat_id, {"processedSummary": True})
    state.ready("Ready")


def analyzeConversation(chat_id: str):
    return
    state.working("Analyzing chat {title}", chat_id=chat_id)
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
    state.ready("Ready")


def catagorizeConversation(chat_id: str):
    db = databasehandler.DatabaseHandler()
    state.working("Catagorizing chat {title}", chat_id=chat_id)
    prompt = config.readSetting("prompts.catagorize_conversation")
    chat_text = db.load_conversation(chat_id)["content"]
    chat_text = chatformatter.cleanPlaceholders(
        chat_text
    )  # Clean the text so model can read conversation flow
    text = prompt.replace("{history}", chat_text)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    answer = answer.strip()

    # Try to pull a JSON array out of the response.
    # Models often wrap it in prose: "Here are the tags: [\"a\", \"b\"]"
    tags = None
    try:
        tags = json.loads(answer)
    except json.JSONDecodeError:
        # Look for the first [...] block in the text
        start = answer.find("[")
        end = answer.rfind("]")
        if start != -1 and end > start:
            try:
                tags = json.loads(answer[start : end + 1])
            except json.JSONDecodeError:
                tags = None

    # Fallback: treat the whole response as a single tag
    if tags is None:
        tags = [answer] if answer else "[]"

    db.update_conversation(chat_id, {"tags": tags, "processedTags": True})
    state.ready("Ready")


def generateTitle(chat_id: str):
    db = databasehandler.DatabaseHandler()
    state.working("Generating Title for chat {title}", chat_id=chat_id)
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
    state.ready("Ready")


def sendUserMessage(chat_id: str, user_message: str):
    db = databasehandler.DatabaseHandler()
    chat_data = db.load_conversation(chat_id)

    # Build the prompt
    prompt = config.readSetting("prompts.system")
    if (
        chat_data is not None
        and "system_prompt" in chat_data
        and chat_data["system_prompt"] is not None
    ):
        prompt = chat_data["system_prompt"]
    db.update_conversation(chat_id, {"system_prompt": prompt})

    # Build the conversation history
    chatText = ""
    if chat_data is not None and "content" in chat_data:
        chatText = chat_data["content"]

    # Allow continuations
    if user_message != None and user_message != "":
        user_message = chatformatter.cleanPlaceholders(user_message)
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
    state.working("Thinking about chat {title}", chat_id=chat_id)
    message = prompt + chatText
    streamed_response = ""
    for token in koboldInstance.generate(message):
        state.working("Writing in chat {title}", chat_id=chat_id)
        streamed_response += token
        yield {"type": "token", "chat_id": str(chat_id), "token": token}
    split_response = chatformatter.seperateThinking(streamed_response)
    chatText = chatText + split_response["response"]
    # chatText = chatText + streamed_response <-- Eventually ;_;
    db.update_conversation(
        chat_id,
        {
            "content": chatText,
            "processedSummary": False,
            "processedTags": False,
            "processedTitle": True,
        },
    )
    state.ready("Ready")

    yield {"type": "complete", "chat_id": str(chat_id), "text": chatText}


def processChatsInBackground():
    db = databasehandler.DatabaseHandler()
    process_chats_flag = "working"
    chat_info = db.list_chat_ids()
    try:
        for data in chat_info:
            id = data["id"]
            flags = db.check_conversation_status(id)
            if flags["hasText"]:
                if state.is_canceled():
                    break
                if flags["processedTitle"] == 0:
                    generateTitle(id)

                if state.is_canceled():
                    break
                if flags["processedSummary"] == 0:
                    summarizeConversation(id)

                if state.is_canceled():
                    break
                if flags["processedTags"] == 0:
                    catagorizeConversation(id)

                if state.is_canceled():
                    break
                if flags["processedAnalysis"] == 0:
                    analyzeConversation(id)
    except KoboldError:
        print("Kobold instance was not running. Could not process chats")

    state.clear_cancel()


def update_conversation(data):
    db = databasehandler.DatabaseHandler()
    db.update_conversation(data["chat_id"], data)


def cancelProcessing():
    state.cancel()
    stopGeneration()


def stopGeneration():
    koboldInstance.stopGeneration()


def getStatus():
    return state.get_state()
