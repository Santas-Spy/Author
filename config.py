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

def readSetting(pathStr:str):
    config = getConfig()
    path = pathStr.split('.')
    setting = config

    for step in path:
        if step not in setting:
            raise KeyError("Missing configuration key: \"" + step + "\" in key " + pathStr)
        setting = setting[step]
    return setting
