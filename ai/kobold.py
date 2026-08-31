import json
from threading import Event
from typing import Any, Dict, Iterator, Optional

import requests
from requests.exceptions import ConnectionError
from requests.models import Response

import loghandler as logging


class KoboldError(Exception):
    """Raised when a request to the KoboldCpp server fails."""


class KoboldOfflineError(Exception):
    """Kobold Server was not running"""


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
            self._cancel_event: Event = Event()
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
                # timeout=self.timeout,
            )
            response.raise_for_status()
            return response
        except ConnectionError as error:
            raise KoboldOfflineError(
                f"Could not connect to KoboldCpp at {url}. Make sure the server is running."
            ) from error
        except requests.HTTPError as error:
            raise KoboldError(f"KoboldCpp request failed: {error}") from error

    def _iter_stream(
        self,
        response: "requests.Response",
        text_field: str,
    ) -> Iterator[str]:
        """Yield `text_field` from each JSON object in a KoboldCpp stream."""
        self._cancel_event.clear()
        for line in response.iter_lines():
            if not line:
                continue

            if self._cancel_event.is_set():
                print("CANCELLING GENERATION")
                break

            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                decoded_line = decoded_line[6:]
            try:
                data = json.loads(decoded_line)
            except json.JSONDecodeError:
                continue
            yield str(data.get(text_field, ""))

    def generateWithTools(
        self, messages: list[Dict[str, Any]], tools: list[dict[str, Any]], tool_choice="auto"
    ) -> Iterator[str]:
        payload = {
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
        }

        response = self._request(
            "POST",
            "/v1/chat/completions",
            json=payload,
            stream=True,
        )

        return self._iter_stream(response, "token")

    def generate(
        self,
        prompt: str,
        max_length: int = 16384,
        temperature: float = 0.6,
        top_k: int = 20,
        top_p: float = 0.95,
        rep_pen: float = 1.05,
        image: Optional[str] = None,
        format: bool = True,
        extra: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        discard_incomplete: bool = True,
    ) -> Iterator[str] | str | None:
        """Send a prompt to the streaming generation endpoint and yield tokens as they arrive."""
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "max_length": max_length,
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "rep_pen": rep_pen,
            "replace_instruct_placeholders": format,
        }
        if image:
            payload["images"] = [image]
        if extra:
            payload.update(extra)

        logging.logToFile(prompt, tag="[PROMPT INPUT]")

        response = self._request(
            "POST",
            "/api/extra/generate/stream",
            json=payload,
            stream=True,
        )
        if stream:
            return self._iter_stream(response, "token")
        else:
            tokens = list(self._iter_stream(response, "token"))
            result_text = "".join(tokens)
            if self._cancel_event.is_set():
                if discard_incomplete:
                    return None
                else:
                    return result_text  # Return partial text

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

    def stopGeneration(self) -> None:
        """Signal the server to stop the current generation."""
        self._cancel_event.set()
        self._request("POST", "/api/extra/abort")

    def ping(self) -> bool:
        try:
            short_timeout = 2.0
            self._session.get(f"{self.base_url}/", timeout=short_timeout)
            return True
        except requests.exceptions.ConnectionError:
            # Could not connect at all
            return False
        except requests.exceptions.Timeout:
            # Server is taking too long to respond
            return False
        except Exception:
            # Any other error (like DNS issues)
            return False


# Singleton instance
koboldInstance = KoboldInstance()
