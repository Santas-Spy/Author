import json
from typing import Any, Dict, Iterator, Optional

import requests
from requests.exceptions import ConnectionError

import ai.chatformatter as chatformatter
import loghandler as logging


class KoboldError(Exception):
    """Raised when a request to the KoboldCpp server fails."""


class KoboldInstance:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KoboldInstance, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not getattr(self, "_initialized", False):
            self._initialized = True
            self.setEndpoint("LOCATION_NOT_SET")

    def setEndpoint(self, url: str, timeout: float = 30.0) -> None:
        """Set the base URL of a running KoboldCpp server."""
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._cache: Dict[str, Any] = {}
        self._initialized = True

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> "requests.Response":
        """Send a request to the KoboldCpp server, raising a `KoboldError` on failure."""
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                json=json,
                stream=stream,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response
        except ConnectionError as error:
            raise KoboldError(
                f"Could not connect to KoboldCpp at {url}. "
                "Make sure the server is running."
            ) from error
        except requests.HTTPError as error:
            raise KoboldError(f"KoboldCpp request failed: {error}") from error

    def _iter_stream(
        self,
        response: "requests.Response",
        text_field: str,
    ) -> Iterator[str]:
        """Yield `text_field` from each JSON object in a KoboldCpp stream."""
        for line in response.iter_lines():
            if not line:
                continue
            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                decoded_line = decoded_line[6:]
            try:
                data = json.loads(decoded_line)
            except json.JSONDecodeError:
                continue
            yield str(data.get(text_field, ""))

    def sendMessage(
        self,
        prompt: str,
        max_length: int = 16384,
        temperature: float = 0.8,
        image: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a prompt to the streaming generation endpoint and return the full response."""
        logging.logToFile(prompt, tag="[RAW PROMPT INPUT]", logtype="raw_text.txt")
        prompt = chatformatter.lfm2_5(prompt)
        logging.logToFile(prompt, tag="[PROMPT INPUT]")

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "max_length": max_length,
            "temperature": temperature,
        }
        if image:
            payload["images"] = [image]
        if extra:
            payload.update(extra)

        response = self._request(
            "POST",
            "/api/extra/generate/stream",
            json=payload,
            stream=True,
        )
        return "".join(self._iter_stream(response, "token"))

    def generate(
        self,
        prompt: str,
        max_length: int = 16384,
        temperature: float = 0.8,
        image: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        """Send a prompt to the streaming generation endpoint and yield tokens as they arrive."""
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "max_length": max_length,
            "temperature": temperature,
        }
        if image:
            payload["images"] = [image]
        if extra:
            payload.update(extra)

        response = self._request(
            "POST",
            "/api/extra/generate/stream",
            json=payload,
            stream=True,
        )
        yield from self._iter_stream(response, "token")

    def getMaxContext(self) -> int:
        """Return the maximum context length reported by the server."""
        response = self._request("GET", "/api/extra/true_max_context_length")
        return int(response.json()["value"])

    def countTokens(self, text: str) -> int:
        """Return the token count for the given text according to the server."""
        response = self._request("POST", "/api/extra/tokenize", json={"prompt": text})
        return int(response.json()["value"])

    def loadModel(self, modelName: str) -> None:
        """Swap the active model on the server."""
        print(f"Loading model '{modelName}'")


# Singleton instance
koboldInstance = KoboldInstance()
