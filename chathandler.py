import json
import os


def _loadFile(chat_id, filename):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    text = ""
    try:
        with open(filePath, "r") as file:
            text = file.read()
    except FileNotFoundError:
        print(f'Data "{filename}" was found for chat {chat_id}')

    return text


def _saveFile(chat_id, filename, text):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    with open(filePath, "w") as file:
        file.write(text)


def saveChat(chat_id, text):
    saveChatData(chat_id, text=text)


def saveAnalysis(chat_id, text):
    saveChatData(chat_id, analysis=text)


def saveSummary(chat_id, text):
    saveChatData(chat_id, summary=text)


def loadChat(chat_id) -> str:
    data = loadChatData(chat_id)
    chat_text = ""
    if "text" in data:
        chat_text = data["text"]
    return chat_text


def loadSummary(chat_id) -> str:
    data = loadChatData(chat_id)
    summary = ""
    if "summary" in data:
        summary = data["summary"]
    return summary


def loadAnalysis(chat_id) -> str:
    data = loadChatData(chat_id)
    analysis = ""
    if "analysis" in data:
        analysis = data["analysis"]
    return analysis


def saveChatData(chat_id, text=None, summary=None, tags=None, analysis=None):
    chat_data = {}
    raw_data = _loadFile(chat_id, "data.json")
    if raw_data != "":
        chat_data = json.loads(raw_data)

    if text is not None:
        chat_data["text"] = text

    if summary is not None:
        chat_data["summary"] = summary

    if analysis is not None:
        chat_data["analysis"] = analysis

    if tags is not None:
        chat_data["tags"] = tags

    chat_data["data_format"] = 2.0

    _saveFile(chat_id, "data.json", json.dumps(chat_data, indent=2))


def loadChatData(chat_id: int):
    chat_data = {}
    raw_data = _loadFile(chat_id, "data.json")
    if raw_data != "":
        chat_data = json.loads(raw_data)
    return chat_data
