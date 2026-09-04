import config

settings = {}


def reload_config():
    global settings
    settings = config.getConfig()


def update_settings(new_settings):
    global settings
    settings = new_settings


def readSetting(pathStr: str, default=None) -> str:
    global settings
    path = pathStr.split(".")
    setting = settings
    for step in path:
        if step not in setting or not isinstance(setting, dict):
            if default is not None:
                return default
            raise KeyError('Missing configuration key: "' + step + '" in key ' + pathStr)
        setting = setting[step]

    return setting
