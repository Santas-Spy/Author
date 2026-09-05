import json

from typing_extensions import Any

from ai.tools import list_conversation, read_conversation, websearch
from state import settings


def get_default_toollist():
    tools = []
    if settings.readSetting("system.tools.web_search.enabled"):
        tools.append(websearch.get_tool())

    if settings.readSetting("system.tools.list_conversations.enabled"):
        tools.append(list_conversation.get_tool())

    return tools


def call_tool(tool) -> dict[str, Any]:
    tool_name = tool["function"]["name"]
    print(f"calling tool: {tool_name}")
    if tool_name == "search_web":
        request = json.loads(tool["function"]["arguments"])
        query = request["query"]
        return {"tool_response": websearch.execute(query), "next_tools": get_default_toollist()}

    if tool_name == "read_conversation":
        request = json.loads(tool["function"]["arguments"])
        chat_id = request["conversation_id"]
        task = request["task_description"]
        result = read_conversation.execute(chat_id, task)
        return {"tool_response": result, "next_tools": get_default_toollist()}

    if tool_name == "list_conversations":
        chat_list = list_conversation.execute()
        return {"tool_response": json.dumps(chat_list), "next_tools": [read_conversation.get_tool()], "force_tools": True}

    return {"tool_response": "Tool did not return any result", "next_tools": get_default_toollist()}
