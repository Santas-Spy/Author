import datetime
import json
import threading
from enum import Enum
from json.decoder import JSONDecodeError

import config
import databasehandler
from ai import chatformatter
from ai.kobold import KoboldError, KoboldOfflineError, koboldInstance
from ai.tools import tools as tool_list


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

    def ready(self, message: str = "Ready", chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.READY, message)

    def working(self, message: str = "Working", chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.WORKING, message)

    def offline(self, message: str = "Could not connect to KoboldCPP"):
        self._set(OrchestratorState.OFFLINE, message)

    def cancel(self):
        self._canceled.set()

    def clear_cancel(self):
        self._canceled.clear()

    def is_canceled(self):
        return self._canceled.is_set()

    def get_state(self):
        with self._lock:
            return {"status": self._status.value, "message": self._message, "state": self._status}


process_chats_flag = "ready"
state = StateManager()


def chooseModel(message: str):
    return  # Skip this for now since model loading isn't supported
    state.working("Choosing Model")
    text = config.readSetting("prompts.choose_model")
    text = text.replace("{request}", message)
    response = koboldInstance.sendMessage(text)
    split_response = chatformatter.seperateThinking(response)
    answer = split_response["response"]
    state.ready()
    koboldInstance.loadModel(answer)


def loadConversation(chat_id: str, prompt_name: str):
    db = databasehandler.DatabaseHandler()

    # Build the prompt
    prompt = config.readSetting(f"prompts.{prompt_name}")
    conversation = db.load_conversation(chat_id)
    if conversation is None:
        return {}

    # Clean the text so model can read conversation flow
    chat_text = conversation["content"]
    chat_text = chatformatter.cleanPlaceholders(chat_text)

    formatted_prompt = prompt.replace("{history}", chat_text)

    return {"chat_text": chat_text, "prompt": prompt, "formatted_prompt": formatted_prompt}


def getOnlyAnswer(prompt) -> str | None:
    try:
        response = koboldInstance.generate(prompt=prompt, stream=False, discard_incomplete=True)
        split_response = chatformatter.seperateThinking(response)
        answer = split_response["response"]
        return answer
    except KoboldOfflineError:
        state.offline()
        return None


def summarizeConversation(chat_id: str):
    state.working("Summarizing chat {title}", chat_id=chat_id)
    content = loadConversation(chat_id, "summarize_conversation")

    if not content["chat_text"] or not content["prompt"]:
        return

    db = databasehandler.DatabaseHandler()
    formatted_prompt = content["formatted_prompt"]
    word_count = len(content["chat_text"].split(" "))

    if word_count > 500:
        prompt = formatted_prompt.replace(
            "{max_length}", str(min(word_count / 3, 150))
        )  # Hardcoding summary to 150 words for now

        # Generate a summary
        summary = getOnlyAnswer(prompt)
        if summary:
            db.update_conversation(chat_id, {"summary": summary})
    db.update_conversation(chat_id, {"processedSummary": True})
    state.ready()


def analyzeConversation(chat_id: str, user_id: int = 0):
    state.working("Learning about user from chat {title}", chat_id=chat_id)
    content = loadConversation(chat_id, "analyze_conversation")
    if not content["chat_text"] or not content["prompt"]:
        return

    formatted_prompt = content["formatted_prompt"]

    db = databasehandler.DatabaseHandler()
    user_facts = db.get_user_facts(user_id)
    print(user_facts)
    formatted_prompt.replace("{user_facts}", json.dumps(user_facts))

    # Generate a summary
    facts = getOnlyAnswer(formatted_prompt)
    if facts:
        try:
            fact_list = json.loads(facts)
            for fact in fact_list:
                db.save_fact(user_id, chat_id, fact)
            print("Current facts: " + str(db.get_user_facts(user_id)))
        except JSONDecodeError:
            print(f"ERROR: Facts were not json parsable: {facts}")

        db.update_conversation(chat_id, {"processedAnalysis": True})

    state.ready()


def catagorizeConversation(chat_id: str):
    db = databasehandler.DatabaseHandler()
    db.update_conversation(chat_id, {"processedTags": True})
    return  # This function isnt working consistently

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
    state.ready()


def generateTitle(chat_id: str):
    state.working("Generating Title for chat {title}", chat_id=chat_id)
    content = loadConversation(chat_id, "title_generation")
    if not content["chat_text"] or not content["prompt"]:
        return

    formatted_prompt = content["formatted_prompt"]

    # Generate a summary
    title = getOnlyAnswer(formatted_prompt)
    if title:
        title = title.strip()
        db = databasehandler.DatabaseHandler()
        db.update_conversation(chat_id, {"title": title, "processedTitle": True})
    state.ready()


def sendUserMessage(
    chat_id: str,
    user_message: str,
    user_id: int = 0,
    force_thinking: bool = False,
    use_tools: bool = True,
):
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
        if force_thinking:
            chatText = chatText + "<think>\nHere's a Thinking Process:\n"
        db.update_conversation(chat_id, {"content": chatText})

    # Fill in placeholders
    user_facts = db.get_user_facts(user_id)
    if user_facts is not None:
        prompt = prompt.replace("{user_facts}", json.dumps(user_facts))

    current_date = datetime.datetime.now().strftime("%c")
    prompt = prompt.replace("{date}", current_date)

    # Choose the model
    chooseModel(user_message)

    # Send the message, streaming tokens as they arrive
    state.working("Thinking about chat {title}", chat_id=chat_id)
    message = prompt + chatText
    messages = chatformatter.split_conversation(message)
    streamed_response = ""
    if use_tools:
        for token in koboldInstance.generateWithTools(messages, tools=tool_list.tools):
            streamed_response += token
            print(token)
            yield {"type": "token", "chat_id": str(chat_id), "token": token}
        # response = koboldInstance.generateWithTools(messages, tools=tool_list.tools)
        # response = response.json()["choices"][0]["message"]
        # for tool in response["tool_calls"]:
        #    tool_list.call_tool(tool)
        # streamed_response = response["content"]
    else:
        for token in koboldInstance.generate(message, stream=True):
            state.working("Writing in chat {title}", chat_id=chat_id)
            streamed_response += token
            yield {"type": "token", "chat_id": str(chat_id), "token": token}
    split_response = chatformatter.seperateThinking(streamed_response)
    chatText = chatText + split_response["response"]

    db.update_conversation(
        chat_id,
        {
            "content": chatText,
            "processedSummary": False,
            "processedTags": False,
        },
    )
    state.ready()

    yield {"type": "complete", "chat_id": str(chat_id), "text": chatText}


def processChatsInBackground():
    if state.get_state()["state"] != OrchestratorState.READY:
        return

    db = databasehandler.DatabaseHandler()
    chat_info = db.list_chat_ids()
    jobs = {
        "title": [generateTitle, []],
        "summary": [summarizeConversation, []],
        "tags": [catagorizeConversation, []],
        "analyze": [analyzeConversation, []],
    }
    try:
        for data in chat_info:
            id = data["id"]
            flags = db.check_conversation_status(id)
            if flags["hasText"]:
                if state.is_canceled():
                    break
                if flags["processedTitle"] == 0:
                    jobs["title"][1].append(id)

                if state.is_canceled():
                    break
                if flags["processedSummary"] == 0:
                    jobs["summary"][1].append(id)

                if state.is_canceled():
                    break
                if flags["processedTags"] == 0:
                    jobs["tags"][1].append(id)

                if state.is_canceled():
                    break
                if flags["processedAnalysis"] == 0:
                    jobs["analyze"][1].append(id)

        # Iterate through the processing jobs that need to be done
        for job in jobs:
            if state.is_canceled():
                break
            # Go through each job type in order
            for id in jobs[job][1]:
                if state.is_canceled():
                    break
                print(f"Running {job} job for chat {id}")
                jobs[job][0](id)  # Call the job's function with the chat id

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
    online = koboldInstance.ping()
    if not online:
        state.offline()
    if online and state.get_state()["state"] == OrchestratorState.OFFLINE:
        state.ready("Server is back online")
    return state.get_state()
