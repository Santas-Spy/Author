import config
import ai.orchestrator as orchestrator

url = config.readSetting("kobold.url")
print(url)

orchestrator.startProgram()
