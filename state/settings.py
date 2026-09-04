import config

settings = None


def reload_config():
    global settings
    settings = config.getConfig()


def update_settings(new_settings):
    global settings
    settings = new_settings


def readSetting(pathStr: str, default=None) -> str:
    global settings
    if settings is None:
        settings = reload_config()

    path = pathStr.split(".")
    setting = settings
    for step in path:
        if step not in setting or not isinstance(setting, dict):
            if default is not None:
                return default
            raise KeyError('Missing configuration key: "' + step + '" in key ' + pathStr)
        setting = setting[step]

    return setting
