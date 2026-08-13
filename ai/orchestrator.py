from ai.kobold import KoboldInstance, koboldInstance
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
    return koboldInstance.sendMessage(text)

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
    chatText = ""
    koboldInstance.setEndpoint(config.readSetting('kobold.url'))
    while running:
        userMessage = input("> ")
        #chatText = chathandler.loadChat(chat_id)
        chatText = chatText + "{{[INPUT]}}" + userMessage + "{{[OUTPUT]}}"
        #chathandler.saveChat(chat_id, chatText)

        model = chooseModel(userMessage)
        koboldInstance.loadModel(model)

        response = sendMessage(chatText)
        chatText = chatText + response
        #chathandler.saveChat(chat_id, chatText)

        print(response)
        print("Chat Length: " + str(len(chatText)))
