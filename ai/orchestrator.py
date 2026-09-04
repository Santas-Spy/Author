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
from signals import emit_signal
from state.state import OrchestratorState
from state.state import stateManager as state


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

        if response is None:
            print("Response was cancelled!")
            return response

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
        prompt = formatted_prompt.replace("{max_length}", str(min(word_count / 3, 150)))  # Hardcoding summary to 150 words for now

        # Generate a summary
        summary = getOnlyAnswer(prompt)
        if summary:
            db.update_conversation(chat_id, {"summary": summary})
    db.update_conversation(chat_id, {"processedSummary": True})
    emit_signal("chat_update", {"chat_id": chat_id})
    state.ready()


def analyzeConversation(chat_id: str, user_id: int = 0):
    state.working("Learning about user from chat {title}", chat_id=chat_id)
    content = loadConversation(chat_id, "analyze_conversation")
    if not content["chat_text"] or not content["prompt"]:
        return

    formatted_prompt = content["formatted_prompt"]

    db = databasehandler.DatabaseHandler()
    user_facts = db.get_user_facts(user_id)
    if user_facts is not None:
        formatted_prompt = formatted_prompt.replace("{user_facts}", json.dumps(user_facts))
    else:
        formatted_prompt = formatted_prompt.replace("{user_facts}", "[]")

    # Generate a summary
    facts = getOnlyAnswer(formatted_prompt)
    if facts:
        try:
            fact_list = json.loads(facts)
            for fact in fact_list:
                db.save_fact(user_id, chat_id, fact)
        except JSONDecodeError:
            print(f"ERROR: Facts were not json parsable: {facts}")

        db.update_conversation(chat_id, {"processedAnalysis": True})
    emit_signal("chat_update", {"chat_id": chat_id})
    state.ready()


def cleanupFacts(user_id: int = 0):
    state.working("Cleaning up user facts")
    db = databasehandler.DatabaseHandler()
    existing_facts = db.get_user_facts(user_id)
    prompt = config.readSetting("prompts.cleanup_facts")

    if existing_facts is not None:
        prompt = prompt.replace("{user_facts}", json.dumps(existing_facts))
    else:
        return

    new_facts = getOnlyAnswer(prompt)
    if new_facts:
        try:
            fact_list = json.loads(new_facts)
            db.delete_all_facts()
            for fact in fact_list:
                db.save_fact(user_id, None, fact)
        except JSONDecodeError:
            print(f"ERROR: Facts were not json parsable: {new_facts}")

    state.ready()


def catagorizeConversation(chat_id: str):
    db = databasehandler.DatabaseHandler()
    db.update_conversation(chat_id, {"processedTags": True})
    return  # This function isnt working consistently

    state.working("Catagorizing chat {title}", chat_id=chat_id)
    prompt = config.readSetting("prompts.catagorize_conversation")
    chat_text = db.load_conversation(chat_id)["content"]
    chat_text = chatformatter.cleanPlaceholders(chat_text)  # Clean the text so model can read conversation flow
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
    emit_signal("chat_update", {"chat_id": chat_id})
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
    emit_signal("title_update", {"chat_id": chat_id})
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
    if chat_data is not None and "system_prompt" in chat_data and chat_data["system_prompt"] is not None:
        prompt = chat_data["system_prompt"]
    db.update_conversation(chat_id, {"system_prompt": prompt})

    # Build the conversation history
    chatText = ""
    is_continuation = user_message == None or user_message == ""
    if chat_data is not None and "content" in chat_data:
        chatText = chat_data["content"]

    # Allow continuations
    if not is_continuation:
        user_message = chatformatter.cleanPlaceholders(user_message)
        chatText = chatText + "{{[INPUT]}}" + user_message + "{{[OUTPUT]}}"
        db.update_conversation(chat_id, {"content": chatText})

    if is_continuation:
        use_tools = False  # Do not allow for tool usage if message is a continuation

    if force_thinking and not use_tools and not is_continuation:
        chatText = chatText + "<think>\nHere's a Thinking Process:\n"
        db.update_conversation(chat_id, {"content": chatText})

    # Fill in placeholders
    user_facts = db.get_user_facts(user_id)
    if user_facts is not None:
        prompt = prompt.replace("{user_facts}", json.dumps(user_facts))
    else:
        prompt = prompt.replace("{user_facts}", "[]")

    current_date = datetime.datetime.now().strftime("%c")
    prompt = prompt.replace("{date}", current_date)

    # Choose the model
    chooseModel(user_message)

    # Send the message, streaming tokens as they arrive
    state.working("Thinking about chat {title}", chat_id=chat_id)
    message = prompt + chatText
    streamed_response = ""
    if use_tools:
        pending_tools = []
        messages = chatformatter.split_conversation(message)
        messages = chatformatter.strip_previous_thinking(messages)
        available_tools = tool_list.get_default_toollist()
        while True:
            # Generate Text
            previous_token_type = None
            for token in koboldInstance.generateWithTools(messages, stream=True, tools=available_tools):
                if token["type"] == "content":
                    state.working("Writing in chat {title}", chat_id=chat_id)
                    text = token["token"]
                    if previous_token_type == "reasoning_content":
                        streamed_response += "</think>"
                    streamed_response += text
                    previous_token_type = "content"
                    yield {"type": "token", "chat_id": str(chat_id), "token": text}

                if token["type"] == "reasoning_content":
                    state.working("Planning response in chat {title}", chat_id=chat_id)
                    text = token["token"]
                    if previous_token_type == None:
                        streamed_response += "<think>"
                    streamed_response += text
                    previous_token_type = "reasoning_content"
                    yield {"type": "token", "chat_id": str(chat_id), "token": text}

                if token["type"] == "tool_call":
                    print(f"Got a toolcall: {token}")
                    state.working("Using tools in chat {title}", chat_id=chat_id)
                    toolcall = token["tool_call"]
                    pending_tools.append(toolcall)

            # Check if the tool list is empty
            if not pending_tools:
                break

            for tc in pending_tools:
                yield {"type": "tool_call", "chat_id": str(chat_id), "token": json.dumps(tc)}
                result = tool_list.call_tool(tc)
                tool_response = result["tool_response"]
                available_tools = result["next_tools"]

                tool_call_message = {
                    "role": "assistant",
                    "content": streamed_response,
                    "tool_calls": tc,
                }
                messages.append(tool_call_message)
                tool_call_result = {"role": "tool", "tool_call_id": tc["id"], "content": tool_response}
                messages.append(tool_call_result)
            pending_tools.clear()
    else:
        stream = koboldInstance.generate(message, stream=True)
        if stream:
            for token in stream:
                state.working("Writing in chat {title}", chat_id=chat_id)
                streamed_response += token
                yield {"type": "token", "chat_id": str(chat_id), "token": token}

    chatText = chatText + streamed_response
    db.update_conversation(
        chat_id,
        {
            "content": chatText,
            "processedSummary": False,
            # "processedTags": False,
            "processedAnalysis": False,
        },
    )

    state.ready()

    yield {"type": "complete", "chat_id": str(chat_id), "text": chatText}


def processChatsInBackground():
    # return  # Disabled for now
    if state.get_state()["state"] != OrchestratorState.READY:
        return

    def run_job():

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

    thread = threading.Thread(target=run_job)
    thread.start()


def update_conversation(data):
    db = databasehandler.DatabaseHandler()
    db.update_conversation(data["chat_id"], data)


def cancelProcessing():
    state.cancel()
    stopGeneration()


def stopGeneration():
    koboldInstance.stopGeneration()
