"""Planner — decomposes intent into execution plan."""
from __future__ import annotations

import uuid
from typing import Any

from packages.common.types import Intent, Plan, PlanStep

class Planner:
    def plan(self, intent: Intent) -> Plan:
        steps: list[PlanStep] = []
        risk = intent.risk_level
        requires_confirm = intent.requires_confirmation

        if intent.intent == "briefing":
            steps = [
                PlanStep(description="Get current time", tool=None),
                PlanStep(description="Get calendar", tool="calendar.get_today", agent="scheduling"),
                PlanStep(description="Get tasks", tool="tasks.list", agent="scheduling"),
                PlanStep(description="Get system status", tool="system.diagnostics", agent="system"),
                PlanStep(description="Summarize briefing", tool=None),
            ]
        elif intent.intent == "calendar.read":
            steps = [PlanStep(description="Fetch today's calendar", tool="calendar.get_today", agent="scheduling")]
        elif intent.intent == "computer.open":
            app = intent.slots.get("application", "unknown")
            steps = [PlanStep(description=f"Open {app}", tool="computer.open_application", arguments={"application": app}, agent="computer")]
        elif intent.intent in ("system.cpu", "system.ram"):
            tool = "system.cpu_status" if "cpu" in intent.intent else "system.ram_status"
            steps = [PlanStep(description="Check system", tool=tool, agent="system")]
        elif intent.intent in ("reminder.create", "task.create"):
            steps = [PlanStep(description="Create task/reminder", tool="tasks.create", arguments={"title": intent.raw}, agent="scheduling")]
        elif intent.intent == "research":
            # extract query
            q = intent.raw
            steps = [PlanStep(description=f"Search web for {q}", tool="search.web", arguments={"query": q}, agent="research")]
        elif intent.intent == "vision":
            steps = [PlanStep(description="Capture and analyze screen", tool="computer.screenshot", agent="vision"), PlanStep(description="Analyze image", tool="vision.analyze_image", agent="vision")]
        elif intent.intent == "time":
            steps = [PlanStep(description="Get current time", tool=None)]
        elif intent.intent.startswith("safety"):
            steps = [PlanStep(description=f"Safety command: {intent.intent}", tool=None)]
            # safety never requires approval, immediate
        else:
            # general: no tool, just answer
            steps = [PlanStep(description="Generate answer", tool=None, agent="general")]

        # compute max risk
        risk_levels = {"low":0,"moderate":2,"high":3,"critical":4}
        # For now trust intent risk
        return Plan(
            plan_id=uuid.uuid4().hex,
            goal=intent.goal,
            steps=steps,
            risk_level=risk,
            requires_confirmation=requires_confirm,
            reasoning=f"Intent {intent.intent} with confidence {intent.confidence}"
        )

planner = Planner()
