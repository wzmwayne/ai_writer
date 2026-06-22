from __future__ import annotations

import hashlib
import time
import uuid
from threading import Lock


class StreamCacheEntry:
    __slots__ = ("stream_id", "events", "status", "error", "created_at", "content_hash")

    def __init__(self, stream_id: str):
        self.stream_id = stream_id
        self.events: list[dict] = []
        self.status: str = "streaming"  # streaming | done | error
        self.error: str | None = None
        self.created_at = time.time()
        self.content_hash: str | None = None

    def add_event(self, event_type: str, data: dict) -> int:
        seq = len(self.events)
        self.events.append({"seq": seq, "type": event_type, "data": dict(data)})
        return seq

    def mark_done(self):
        self.status = "done"
        raw = "".join(
            json.dumps(e["data"], separators=(",", ":"), ensure_ascii=False)
            for e in self.events
        )
        self.content_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def mark_error(self, error: str):
        self.status = "error"
        self.error = error

    def to_dict(self) -> dict:
        return {
            "stream_id": self.stream_id,
            "status": self.status,
            "events": self.events,
            "error": self.error,
            "content_hash": self.content_hash,
        }


import json  # noqa: E402 (needed by mark_done)


class StreamCache:
    TTL = 300  # 5 minutes

    def __init__(self):
        self._store: dict[str, StreamCacheEntry] = {}
        self._lock = Lock()

    def create(self) -> str:
        stream_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._store[stream_id] = StreamCacheEntry(stream_id)
        return stream_id

    def append(self, stream_id: str, event_type: str, data: dict) -> int | None:
        with self._lock:
            entry = self._store.get(stream_id)
            if entry is None:
                return None
            return entry.add_event(event_type, data)

    def mark_done(self, stream_id: str):
        with self._lock:
            entry = self._store.get(stream_id)
            if entry:
                entry.mark_done()

    def replace_content(self, stream_id: str, clean_text: str):
        """Replace all content events with a single clean content event. Preserves non-content events."""
        with self._lock:
            entry = self._store.get(stream_id)
            if not entry:
                return
            new_events: list[dict] = []
            for e in entry.events:
                if e["type"] == "content":
                    continue
                new_events.append(e)
            # Re-number seqs
            seq = len(new_events)
            new_events.append({"seq": seq, "type": "content", "data": {"content": clean_text}})
            entry.events = new_events

    def mark_error(self, stream_id: str, error: str):
        with self._lock:
            entry = self._store.get(stream_id)
            if entry:
                entry.mark_error(error)

    def get_events_since(self, stream_id: str, seq: int) -> dict | None:
        with self._lock:
            entry = self._store.get(stream_id)
            if entry is None:
                return None
            return {
                "status": entry.status,
                "events": [e for e in entry.events if e["seq"] > seq],
                "error": entry.error,
                "content_hash": entry.content_hash,
            }

    def cleanup(self):
        now = time.time()
        with self._lock:
            dead = [sid for sid, e in self._store.items() if now - e.created_at > self.TTL]
            for sid in dead:
                del self._store[sid]


stream_cache = StreamCache()
