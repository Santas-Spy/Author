import json
import os
import shutil
from pathlib import Path

CURRENT_DATA_VER = 2.2


def _loadFile(chat_id, filename):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    text = ""
    try:
        with open(filePath, "r") as file:
            text = file.read()
    except FileNotFoundError:
        pass
        # print(f'Data file "{filename}" was not found for chatID: {chat_id}')

    return text


def _saveFile(chat_id, filename, text):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    with open(filePath, "w") as file:
        file.write(text)


def deleteChat(chat_id: int):
    def on_error(fun, path, exc_info):
        print(f"Error deleting {path}: {exc_info}")

    dir = f"data/{chat_id}"
    print(f"deleting {dir}")
    shutil.rmtree(dir, onerror=on_error)


def saveChat(chat_id, text):
    saveChatData(
        chat_id,
        text=text,
        processedSummary=False,
        processedTitle=False,
        processedAnalysis=False,
        processedCatagories=False,
    )


def saveSummary(chat_id, text):
    saveChatData(chat_id, summary=text)


def loadChat(chat_id) -> str:
    data = loadChatData(chat_id)
    chat_text = ""
    if "text" in data and data["text"] != None:
        chat_text = data["text"]
    return chat_text


def loadSummary(chat_id) -> str:
    data = loadChatData(chat_id)
    summary = ""
    if "summary" in data:
        summary = data["summary"]
    return summary


def saveChatData(chat_id, **kwargs):
    chat_data = {}
    raw_data = _loadFile(chat_id, "data.json")

    # Load the existing data
    if raw_data:
        chat_data = json.loads(raw_data)

    # Save all the keywords that were passed in
    chat_data.update({key: value for key, value in kwargs.items() if value is not None})

    # Check data format
    if "data_format" in chat_data and chat_data["data_format"] != CURRENT_DATA_VER:
        print("WARNING! Upgrading data version. Some things may break!")
    chat_data["data_format"] = CURRENT_DATA_VER

    # Save the file
    _saveFile(chat_id, "data.json", json.dumps(chat_data, indent=2))


def loadChatData(chat_id: int):
    chat_data = {}
    raw_data = _loadFile(chat_id, "data.json")
    if raw_data != "":
        chat_data = json.loads(raw_data)

    if "data_format" in chat_data and chat_data["data_format"] != CURRENT_DATA_VER:
        print("WARNING! Loading old data version. Some things may break!")
    return chat_data


def saveAnalysis(analysis: str):
    dir = "data/"
    filename = "user_analysis.json"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    with open(filePath, "w") as file:
        file.write(analysis)


def loadAnalysis():
    dir = "data/"
    filename = "user_analysis.json"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    text = "[]"
    try:
        with open(filePath, "r") as file:
            text = file.read()
    except FileNotFoundError:
        print(f"Data file {filename} was not found")

    return text


def loadTitle(chat_id):
    data = loadChatData(chat_id)
    title = None
    if "title" in data:
        title = data["title"]
    return title


def listChatIDs() -> list[dict[str, str]]:
    dir = "data/"
    os.makedirs(dir, exist_ok=True)
    subdirectories = [entry.name for entry in os.scandir(dir) if entry.is_dir()]
    chat_ids = []
    for id in subdirectories:
        title = loadTitle(id)
        chat_ids.append({"id": id, "title": title})
    return chat_ids


def deleteAllChats():
    for entry in listChatIDs():
        deleteChat(int(entry["id"]))
