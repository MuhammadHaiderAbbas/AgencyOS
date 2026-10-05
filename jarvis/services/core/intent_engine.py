"""IntentEngine — rule-based + LLM stub."""
from __future__ import annotations

import re
import uuid
from typing import Any

from packages.common.types import Intent

# Deterministic safety commands that bypass AI
SAFETY_PATTERNS = {
    r"^\s*(stop|cancel|pause|abort)\s*\.?\s*$": "safety_stop",
    r"emergency\s*stop": "safety_emergency_stop",
    r"lock(\s+computer)?": "safety_lock",
    r"disable\s+microphone": "safety_disable_mic",
    r"disable\s+camera": "safety_disable_camera",
}

INTENT_RULES: list[tuple[re.Pattern, str, list[str]]] = [
    (re.compile(r"\b(prepare|give).*morning\s+briefing\b", re.I), "briefing", []),
    (re.compile(r"\bwhat(?:'s| is)?\s.*(schedule|calendar|meeting)\b", re.I), "calendar.read", ["calendar.get_today"]),
    (re.compile(r"\bwhat\s+time\b|\bcurrent\s+time\b", re.I), "time", []),
    (re.compile(r"\bopen\s+(\w+)", re.I), "computer.open", ["computer.open_application"]),
    (re.compile(r"\b(what|show).*cpu\b", re.I), "system.cpu", ["system.cpu_status"]),
    (re.compile(r"\b(what|show).*ram\b", re.I), "system.ram", ["system.ram_status"]),
    (re.compile(r"\bwhat.*using.*ram\b", re.I), "system.ram", ["system.ram_status"]),
    (re.compile(r"\bcreate.*reminder\b", re.I), "reminder.create", ["tasks.create"]),
    (re.compile(r"\b(create|add).*task\b", re.I), "task.create", ["tasks.create"]),
    (re.compile(r"\bsearch.*(web|news)\b|\bsearch\s+for\b", re.I), "research", ["search.web"]),
    (re.compile(r"\b(analyze|what.*screen|screenshot)\b", re.I), "vision", ["computer.screenshot","vision.analyze_image"]),
    (re.compile(r"\bremind\s+me\b", re.I), "reminder.create", ["tasks.create"]),
]

class IntentEngine:
    def parse(self, text: str) -> Intent:
        raw = text.strip()
        low = raw.lower()

        # safety first
        for pat, intent_name in SAFETY_PATTERNS.items():
            if re.search(pat, low):
                return Intent(intent=intent_name, goal=raw, actions=[], risk_level=0, requires_confirmation=False, raw=raw, confidence=1.0)

        for regex, name, tools in INTENT_RULES:
            if regex.search(raw):
                actions = [{"tool": t} for t in tools]
                # extract slots for open app
                slots: dict[str, Any] = {}
                if name == "computer.open":
                    m = re.search(r"open\s+(\w+)", raw, re.I)
                    if m:
                        slots["application"] = m.group(1)
                risk = 0
                # email send etc would be higher
                if "email.send" in tools:
                    risk = 3
                return Intent(intent=name, goal=raw, actions=actions, slots=slots, risk_level=risk, requires_confirmation=False, raw=raw, confidence=0.85)

        # default: general assistant
        return Intent(intent="general", goal=raw, actions=[], slots={}, risk_level=0, requires_confirmation=False, raw=raw, confidence=0.6)

intent_engine = IntentEngine()
