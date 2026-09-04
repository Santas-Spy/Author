import json

from ddgs import DDGS

import config
from ai import chatformatter
from ai.kobold import koboldInstance
from state import settings
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
    stateManager.working(message=f"Searching the web for: {query}")
    max_results = settings.readSetting("system.tools.web_search.max_results")
    results = DDGS().text(query, max_results=5)
    return json.dumps(results)
