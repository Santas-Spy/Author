import json

from ddgs import DDGS

import config
from ai import chatformatter
from ai.kobold import koboldInstance

filter_search = [
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Read a webpages full page",
            "parameters": {
                "type": "object",
                "properties": {
                    "href": {"type": "string", "description": "The href of the website to read"}
                },
                "required": ["href"],
            },
        },
    }
]


def get_tool():
    return {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    }


def execute(query) -> str:
    print(f"Searching the web for: {query}. Web searches are currently disabled")
    return "Web searches are currently disabled"
    results = DDGS().text(query, max_results=5)
    prompt = config.readSetting("prompts.websearch")
    prompt = prompt.replace("{query}", query)
    prompt = prompt.replace("{web_result}", json.dumps(results))
    messages = chatformatter.split_conversation(prompt)
    website = koboldInstance.generateWithTools(
        messages, tools=filter_search, tool_choice="required"
    )
    print(f"Got back: {results}")
    print(f"searching website {website}")
