import json

import config
import databasehandler
from ai import chatformatter
from ai.kobold import koboldInstance


def get_tool():
    return {
        "type": "function",
        "function": {
            "name": "read_conversation",
            "description": "Read the contents of a previous conversation for any important information. If the contents are too long, an agent will summarize the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "The ID of the conversation to read",
                    },
                    "task_description": {
                        "type": "string",
                        "description": "A brief outline of what the agent should focus on when creating it's summary",
                    },
                },
                "required": ["conversation_id"],
            },
        },
    }


def execute(conversation_id, task) -> str:
    print("Reading conversation")
    db = databasehandler.DatabaseHandler()
    conversation = db.load_conversation(conversation_id)
    if conversation is None:
        return "Conversation could not be read."

    else:
        raw_text = conversation["content"]
        if raw_text is None:
            return "Conversation was empty"

        if raw_text.length < config.readSetting(
            "system.tools.read_conversation.max_conversation_length", 1500
        ):
            return raw_text

        target_word_count = config.readSetting(
            "system.tools.read_conversation.target_summary_size", 500
        )
        prompt = config.readSetting("prompts.summarize_key_information")
        prompt = prompt.replace("{task}", task)
        prompt = prompt.replace("{conversation}", raw_text)
        prompt = prompt.replace("{word_count}", target_word_count)
        response = koboldInstance.generate(prompt)
        if response is None:
            print("Response was cancelled!")
            return "There was an error reading the conversation"

        split_response = chatformatter.seperateThinking(response)
        answer = split_response["response"]
        return answer
