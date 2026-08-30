import json

import ai.tools.websearch as websearch

tools = [websearch.get_tool()]


def call_tool(tool):
    tool_name = tool["function"]["name"]
    if tool_name == "search_web":
        query = tool["function"]["arguments"]
        query = json.loads(query)["query"]
        websearch.execute(query)

    if tool_name == "get_weather":
        query = tool["function"]["arguments"]
        query = json.loads(query)["location"]
        print(f"Looking up weather: {query}")
