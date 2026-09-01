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
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                json=json,
                stream=stream,
            )
            response.raise_for_status()
            return response
        except ConnectionError as error:
            raise KoboldOfflineError(
                f"Could not connect to KoboldCpp at {url}. Make sure the server is running."
            ) from error
        except requests.HTTPError as error:
            raise KoboldError(f"KoboldCpp request failed: {error}") from error

    # ──────────────────────────────────────────────────────────────────────
    #  Stream parsers
    # ──────────────────────────────────────────────────────────────────────

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

    def _iter_tool_stream(
        self,
        response: "requests.Response",
    ) -> Iterator[Dict[str, Any]]:
        """
        Yield structured events from an OpenAI-compatible /v1/chat/completions
        stream that may contain both content and tool_calls.

        Each yielded event is a dict:
          {"type": "content",     "token": str}
          {"type": "tool_call",  "tool_call": dict}   # one per function call
          {"type": "done"}                          # final chunk / finish_reason
        """
        self._cancel_event.clear()
        _active_tools = {}
        for line in response.iter_lines():
            if not line:
                continue
            if self._cancel_event.is_set():
                print("CANCELLING GENERATION")
                return

            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                decoded_line = decoded_line[6:]
            try:
                data = json.loads(decoded_line)
            except json.JSONDecodeError:
                continue

            # The OpenAI chunk format nests the delta under choices[0].delta
            choices = data.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            finish_reason = choices[0].get("finish_reason")

            # ── Plain text token ────────────────────────────────────────────
            if "content" in delta and delta["content"] is not None:
                yield {"type": "content", "token": delta["content"]}

            # ── Tool-call fragment ──────────────────────────────────────────
            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    index = tc.get("index", 0)

                    # Initialize or update the buffer
                    if index not in _active_tools:
                        _active_tools[index] = {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    # Merge fields
                    if tc.get("id"):
                        _active_tools[index]["id"] = tc["id"]
                    if tc.get("function", {}).get("name"):
                        _active_tools[index]["function"]["name"] = tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        _active_tools[index]["function"]["arguments"] += tc["function"]["arguments"]

            # ── End of stream ───────────────────────────────────────────────
            if finish_reason is not None:
                print(_active_tools)
                for complete_tc in _active_tools.values():
                    yield {"type": "tool_call", "tool_call": complete_tc}

                yield {"type": "done"}

    # ──────────────────────────────────────────────────────────────────────
    #  Public generation methods
    # ──────────────────────────────────────────────────────────────────────

    def generateWithTools(
        self,
        messages: list[Dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
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
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream structured events from a tool-capable chat completion.

        Yields dicts of shape:
          {"type": "content",     "token": str}
          {"type": "tool_call",  "tool_call": dict}
          {"type": "done"}
        """
        payload = {
            "messages": messages,
            "max_length": max_length,
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "rep_pen": rep_pen,
            "replace_instruct_placeholders": format,
            "tools": tools,
            "tool_choice": tool_choice,
            "stream": True,
        }
        response = self._request(
            "POST",
            "/v1/chat/completions",
            json=payload,
            stream=True,
        )
        if stream:
            yield from self._iter_tool_stream(response)
        else:
            response = list(self._iter_tool_stream(response))
            print(response)
            if response[len(response) - 1]["type"] != "done" and discard_incomplete:
                print(f"Response was incomplete. Type was: {response[len(response) - 1]['type']}")
                return None
            else:
                print("Generation was GREAT SUCCESS")

            return "TEMP RESPONSE"

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
        self._cancel_event.clear()
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
                return result_text
            return result_text

    # ── Remaining helpers (unchanged) ─────────────────────────────────────

    def getMaxContext(self) -> int:
        response = self._request("GET", "/api/extra/true_max_context_length")
        return int(response.json()["value"])

    def countTokens(self, text: str) -> int:
        response = self._request("POST", "/api/extra/tokenize", json={"prompt": text})
        return int(response.json()["value"])

    def loadModel(self, modelName: str) -> None:
        print(f"Loading model '{modelName}'")

    def stopGeneration(self) -> None:
        self._cancel_event.set()
        self._request("POST", "/api/extra/abort")

    def ping(self) -> bool:
        try:
            short_timeout = 2.0
            self._session.get(f"{self.base_url}/", timeout=short_timeout)
            return True
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.Timeout:
            return False
        except Exception:
            return False


# Singleton instance
koboldInstance = KoboldInstance()
