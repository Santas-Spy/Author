import json

import ai.tools.read_conversation as read_conversation
import ai.tools.websearch as websearch
from ai.tools import list_conversation

tools = [list_conversation.get_tool()]


def call_tool(tool) -> str:
    tool_name = tool["function"]["name"]
    print(f"calling tool: {tool_name}")
    if tool_name == "search_web":
        request = json.loads(tool["function"]["arguments"])
        query = request["query"]
        return websearch.execute(query)

    if tool_name == "read_conversation":
        request = json.loads(tool["function"]["arguments"])
        chat_id = request["conversation_id"]
        task = request["task_description"]
        result = read_conversation.execute(chat_id, task)
        return result

    if tool_name == "list_conversations":
        chat_list = list_conversation.execute()
        return json.dumps(chat_list)

    return "tool name did not match any valid tools"
