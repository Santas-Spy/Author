import databasehandler
from state.state import stateManager


def get_tool():
    return {
        "type": "function",
        "function": {
            "name": "list_conversations",
            "description": "Generate a list of conversation id's and a brief summary of what the conversation contains. Use this if you believe specific information in a previous conversation would be useful.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }


def execute() -> dict[str, str]:
    stateManager.working("Listing previous conversations")
    db = databasehandler.DatabaseHandler()
    conversations = db.load_all_conversations()
    chat_list = {}
    for chat in conversations:
        id = chat["id"]
        summary = chat["summary"]
        if summary is not None:
            chat_list[id] = summary
    return chat_list
