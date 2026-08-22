import json
import os
from typing import Any

CONFIG = "defaultconfig"


def setConfig(new_config):
    global CONFIG
    CONFIG = new_config


def getConfig():
    file = os.path.join(CONFIG, "config.json")
    with open(file, "r") as f:
        config = json.loads(f.read())
        return config


def readSetting(pathStr: str, default=None) -> str:
    path = pathStr.split(".")
    setting = getConfig()

    for step in path:
        if step not in setting:
            if default is not None:
                return default
            raise KeyError('Missing configuration key: "' + step + '" in key ' + pathStr)
        setting = setting[step]
    return setting
