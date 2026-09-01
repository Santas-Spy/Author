import json

import ai.tools.read_conversation as read_conversation
import ai.tools.websearch as websearch

tools = [websearch.get_tool()]


def call_tool(tool):
    tool_name = tool["function"]["name"]
    if tool_name == "search_web":
        request = json.loads(tool["function"]["arguments"])
        query = request["query"]
        websearch.execute(query)

    if tool_name == "read_conversation":
        request = json.loads(tool["function"]["arguments"])
        chat_id = request["conversation_id"]
        task = request["task_description"]
        result = read_conversation.execute(chat_id, task)
        print(result)
