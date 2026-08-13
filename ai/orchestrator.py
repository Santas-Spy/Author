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
    raise NotImplementedError

def summarizeConversation():
    raise NotImplementedError

def analyzeConversation():
    raise NotImplementedError
