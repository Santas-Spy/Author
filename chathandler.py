import os

def _loadFile(chat_id, filename):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    text = ""
    try:
        with open(filePath, 'r') as file:
            text = file.read()
    except FileNotFoundError:
        print(f"Data \"{filename}\" was found for chat {chat_id}")

    return text

def _saveFile(chat_id, filename, text):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/{filename}"
    with open(filePath, 'w') as file:
        file.write(text)

def loadChat(chat_id):
	return _loadFile(chat_id, "chathistory.txt")

def saveChat(chat_id, text):
	_saveFile(chat_id, "chathistory.txt", text)

def loadSummary(chat_id):
	return _loadFile(chat_id, "summary.txt")

def saveSummary(chat_id, text):
	_saveFile(chat_id, "summary.txt", text)
