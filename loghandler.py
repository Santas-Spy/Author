import os

def _getLogFile(filename="log.txt", clear=False):
    os.makedirs("logs", exist_ok=True)
    file = f"logs/{filename}"
    if clear:
        f = open(file, 'w')
        f.close()
    else:
        f = open(file, 'a')
        f.close()
    return file

def logToFile(text, tag=None, logtype="log.txt"):
    filename = _getLogFile(logtype)
    with open(filename, 'w') as f:
        if tag:
            f.write(tag)
            f.write("\n")

        f.write(text)
