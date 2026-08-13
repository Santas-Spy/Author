from ai.kobold import koboldInstance
import config
import data.chathandler as chathandler

"""
Flow Chart
-----------

* User Sends Message
* Tiny Model decides where to route
* Load decided Model
* Send request and wait for response
* Display Response
* If context > max context then summarize
* Every few minutes scan all conversations and build a user profile
"""

def sendMessage(text):
    raise NotImplementedError

def chooseModel(message):
    text = config.readSetting('prompts.choose_model')
    response = koboldInstance.sendMessage(text)
    print(response)

def summarizeConversation():
    raise NotImplementedError

def analyzeConversation():
    raise NotImplementedError

def startProgram():
    running = True
    chat_id = 1
    koboldInstance.setEndpoint(config.readSetting('kobold.url'))
    while running:
        userMessage = input("> ")
        text = chathandler.loadChat(chat_id)
        text = text + "{{USER}}" + userMessage
        chathandler.saveChat(chat_id, text)

        model = chooseModel(userMessage)
        koboldInstance.loadModel(model)
