import threading
from enum import Enum

import databasehandler
from signals import emit_signal


class OrchestratorState(Enum):
    READY = "ready"
    WORKING = "working"
    OFFLINE = "offline"


class StateManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._status: OrchestratorState = OrchestratorState.READY
        self._message: str = "Ready"
        self._canceled: threading.Event = threading.Event()

    def _set(self, status: OrchestratorState, message: str):
        with self._lock:
            if self._status == status and self._message == message:
                return
            self._status = status
            self._message = message
            emit_signal("state_change")

    def _format_message(self, message, id):
        if id:
            db = databasehandler.DatabaseHandler()
            chat_name = id
            title = db.get_chat_title(id)
            if title is not None:
                chat_name = title
            message = message.format(title=chat_name)
        return message

    def ready(self, message: str = "Ready", chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.READY, message)

    def working(self, message: str = "Working", chat_id=None):
        message = self._format_message(message, chat_id)
        self._set(OrchestratorState.WORKING, message)

    def offline(self, message: str = "Could not connect to KoboldCPP"):
        self._set(OrchestratorState.OFFLINE, message)

    def cancel(self):
        self._canceled.set()

    def clear_cancel(self):
        self._canceled.clear()

    def is_canceled(self):
        return self._canceled.is_set()

    def get_state(self):
        with self._lock:
            return {"status": self._status.value, "message": self._message, "state": self._status}


stateManager = StateManager()
