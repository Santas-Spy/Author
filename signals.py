import asyncio
import json
import threading

from typing_extensions import AsyncGenerator

# Event Setup
_event_lock = threading.Lock()
_pending_events: list[dict] = []
_shutdown_event = threading.Event()


def emit_signal(signal_type: str, payload: dict | None = None):
    with _event_lock:
        print(f"Emitting signal: {signal_type}")
        _pending_events.append({"type": signal_type, "data": payload or {}})


def close_all_streams():
    _shutdown_event.set()


async def generate() -> AsyncGenerator[str, None]:
    while not _shutdown_event.is_set():
        with _event_lock:
            signals = list(_pending_events)
            _pending_events.clear()

        if signals:
            for signal in signals:
                yield f"event: {signal['type']}\n"
                yield f"data: {json.dumps(signal['data'])}\n\n"

        await asyncio.sleep(1)
