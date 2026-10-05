import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.core.intent_engine import intent_engine

def test_safety_stop():
    i = intent_engine.parse("stop")
    assert i.intent == "safety_stop"

def test_emergency_stop():
    i = intent_engine.parse("Jarvis, emergency stop")
    assert i.intent == "safety_emergency_stop"

def test_briefing():
    i = intent_engine.parse("Prepare my morning briefing")
    assert i.intent == "briefing"

def test_open_app():
    i = intent_engine.parse("Open Blender")
    assert i.intent == "computer.open"
    assert i.slots["application"] == "Blender"

def test_system_cpu():
    i = intent_engine.parse("What is using the most RAM?")
    assert i.intent == "system.ram"

def test_search():
    i = intent_engine.parse("Search for latest UK news")
    assert i.intent == "research"

def test_general_fallback():
    i = intent_engine.parse("Hello Jarvis, how are you?")
    assert i.intent == "general"
