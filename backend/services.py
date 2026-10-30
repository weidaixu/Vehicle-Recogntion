from __future__ import annotations
import json, os, threading, uuid
from pathlib import Path
from agent_tools import VehicleClassifier
from .session_store import SessionStore

class Services:
    def __init__(self):
        self.model_error = None
        try: self.classifier = VehicleClassifier("output/model.pt")
        except Exception as exc: self.classifier = None; self.model_error = str(exc)
        rows=json.loads(Path("cls_info/class_info.json").read_text(encoding="utf-8"))
        self.catalog={r["id"]:r for r in rows}; self.traces={}; self.sessions={}; self.store=SessionStore("output/vehicle_agent.sqlite"); self.lock=threading.Lock()
    def add_trace(self, tool, status, summary):
        tid=str(uuid.uuid4())
        with self.lock: self.traces[tid]={"tool":tool,"status":status,"summary":summary}
        return tid

services=Services()
