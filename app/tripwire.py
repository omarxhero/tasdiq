"""Inline deterministic cluster tripwire.

X rapid DECLINEs sharing behavioral indicators within a rolling window ->
immediate cluster alert — macro detection never waits for the async AI loop.
(The AI agent then investigates via its sealed tool belt.)
"""
from __future__ import annotations
import threading, time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class TripwireEvent:
    txn_id: str
    band: str
    region_tag: str
    ts: float = field(default_factory=time.time)


class Tripwire:
    def __init__(self, threshold: int = 3, window_seconds: float = 180.0):
        self.threshold, self.window = threshold, window_seconds
        self._events: deque[TripwireEvent] = deque()
        self._lock = threading.Lock()

    def record_decline(self, txn_id: str, band: str, region_tag: str = "unknown"):
        with self._lock:
            self._events.append(TripwireEvent(txn_id, band, region_tag))
            now = time.time()
            while self._events and now - self._events[0].ts > self.window:
                self._events.popleft()
            same_region = [e for e in self._events if e.region_tag == region_tag]
            if len(same_region) >= self.threshold:
                ids = [e.txn_id for e in same_region[-self.threshold:]]
                self._events.clear()
                return {"cluster_alert": True, "region": region_tag,
                        "count": self.threshold, "txn_ids": ids,
                        "note": "inline tripwire fired — AI agent investigating via tool belt"}
        return {"cluster_alert": False}

    def status(self) -> dict:
        with self._lock:
            return {"window_s": self.window, "threshold": self.threshold,
                    "events_in_window": len(self._events)}
