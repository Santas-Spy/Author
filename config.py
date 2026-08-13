import json
import os

CONFIG = "defaultconfig"
def setConfig(new_config):
    global CONFIG
    CONFIG = new_config

def getConfig():
    file = os.path.join(CONFIG, "config.json")
    with open(file, 'r') as f:
        config = json.loads(f.read())
        return config
