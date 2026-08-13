import os

def loadChat(chat_id):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/chathistory.txt"
    text = ""
    try:
        with open(filePath, 'r') as file:
            text = file.read()
    except FileNotFoundError:
        print(f"No chat data was found for chat {chat_id}")

    return text

def saveChat(chat_id, text):
    dir = f"data/{chat_id}"
    os.makedirs(dir, exist_ok=True)
    filePath = f"{dir}/chathistory.txt"
    with open(filePath, 'w') as file:
        file.write(text)
