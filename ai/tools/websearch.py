import json

from ddgs import DDGS

import config
from ai import chatformatter
from ai.kobold import koboldInstance
from state.state import stateManager

filter_search = [
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Read a webpages full page",
            "parameters": {
                "type": "object",
                "properties": {"href": {"type": "string", "description": "The href of the website to read"}},
                "required": ["href"],
            },
        },
    }
]


def get_tool():
    return None
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
    return "Websearch is currently unavailable"
    stateManager.working(message=f"Searching the web for: {query}")
    results = DDGS().text(query, max_results=5)
    return json.dumps(results)
