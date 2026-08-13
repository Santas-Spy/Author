import json
import requests
import loghandler as logging
from requests.exceptions import ConnectionError
import ai.chatformatter as chatformatter


class KoboldInstance:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KoboldInstance, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.setEndpoint("LOCATION_NOT_SET")
        self._initialized = True

    def __preprocess_prompt__(self, prompt: str):
        prompt = prompt.replace(
            "{{[SYSTEM]}}", "<|turn>system\n"
        )  # <-- This assumes the system prompt is *always* first
        prompt = prompt.replace("{{[INPUT]}}", "<turn|>\n<|turn>user\n")
        prompt = prompt.replace("{{[OUTPUT]}}", "<|turn>model\n<|channel>thought\n *")
        return prompt

    def setEndpoint(self, url):
        self.base_url = url
        self.generate_url = self.base_url + "/api/extra/generate/stream"
        self.context_url = self.base_url + "/api/extra/true_max_context_length"
        self.tokencount_url = self.base_url + "/api/extra/tokenize"
        self._initialized = True

    def sendMessage(self, prompt, max_length=1024, temperature=0.8, image=None):
        logging.logToFile(prompt, tag="[RAW PROMPT INPUT]", logtype="raw_text.txt")
        prompt = chatformatter.lfm2_5(prompt)
        logging.logToFile(prompt, tag="[PROMPT INPUT]")

        payload = {
            "prompt": prompt,
            "max_length": max_length,
            "temperature": temperature,
        }

        if image:
            payload["images"] = [image]

        # Using the streaming endpoint
        full_response = ""
        try:
            response = requests.post(self.generate_url, json=payload, stream=True)

            if response.status_code != 200:
                return f"Error: {response.status_code} - {response.text}"

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    # Koboldcpp stream usually returns JSON objects per line
                    try:
                        if decoded_line.startswith("data: "):
                            data = json.loads(decoded_line[6:])
                            full_response += data["token"]
                    except json.JSONDecodeError:
                        full_response += decoded_line

        except ConnectionError:
            return "Error: Kobold Instance not found. Please make sure the koboldCPP server is running"

        return full_response

    def getMaxContext(self) -> int:
        max_context = 0
        try:
            response = requests.get(self.context_url)

            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    data = json.loads(decoded_line)
                    max_context = data["value"]

        except ConnectionError:
            print(
                "Kobold Instance not found. Please make sure the koboldCPP server is running"
            )

        return max_context

    def countTokens(self, text) -> int:
        token_count = 0
        payload = {"prompt": text}

        try:
            response = requests.post(self.tokencount_url, json=payload)

            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    data = json.loads(decoded_line)
                    token_count = int(data["value"])

        except ConnectionError:
            print(
                "Kobold Instance not found. Please make sure the koboldCPP server is running"
            )

        return token_count

    def loadModel(self, modelName):
        print("Model swapping is not yet supported")
        return

# Singleton instance
koboldInstance = KoboldInstance()
