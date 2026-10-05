import pytest
import sys
from pathlib import Path

# ensure jarvis is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.core.permission_engine import permission_engine

def test_safe_no_approval():
    d = permission_engine.check("low", "balanced")
    assert d.allowed is True
    assert d.requires_approval is False

def test_high_requires_approval_balanced():
    d = permission_engine.check("high", "balanced")
    assert d.requires_approval is True

def test_critical_always():
    for trust in ["conservative","balanced","autonomous"]:
        d = permission_engine.check("critical", trust)
        assert d.requires_approval is True

def test_conservative_confirms_moderate():
    d = permission_engine.check("moderate", "conservative")
    assert d.requires_approval is True

def test_autonomous_only_critical():
    d = permission_engine.check("high", "autonomous")
    # high should NOT require approval in autonomous (only critical)
    assert d.requires_approval is False
    d2 = permission_engine.check("low", "autonomous")
    assert d2.requires_approval is False
