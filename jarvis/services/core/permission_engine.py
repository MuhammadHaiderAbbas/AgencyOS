"""PermissionEngine — 5 levels."""
from __future__ import annotations

from dataclasses import dataclass

from packages.common.types import PermissionLevel

TRUST_THRESHOLDS = {
    "conservative": PermissionLevel.MODERATE,  # confirm L2+
    "balanced": PermissionLevel.HIGH,          # confirm L3+ (default)
    "autonomous": PermissionLevel.CRITICAL,    # confirm L4 only
}

RISK_TO_LEVEL = {
    "low": PermissionLevel.SAFE,
    "moderate": PermissionLevel.MODERATE,
    "high": PermissionLevel.HIGH,
    "critical": PermissionLevel.CRITICAL,
}

@dataclass
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    level: int
    reason: str

class PermissionEngine:
    def check(self, risk: str, trust_level: str = "balanced", is_critical_override: bool = False) -> PermissionDecision:
        level = RISK_TO_LEVEL.get(risk, PermissionLevel.SAFE)
        # L4 always requires approval
        if level == PermissionLevel.CRITICAL:
            return PermissionDecision(allowed=True, requires_approval=True, level=int(level), reason="Critical actions always require explicit confirmation")
        threshold = TRUST_THRESHOLDS.get(trust_level, PermissionLevel.HIGH)
        if level >= threshold:
            return PermissionDecision(allowed=True, requires_approval=True, level=int(level), reason=f"Risk {risk} (level {int(level)}) requires approval under trust={trust_level}")
        return PermissionDecision(allowed=True, requires_approval=False, level=int(level), reason="Allowed without confirmation")

    def check_tool(self, tool_risk: str, tool_requires_approval: bool, trust_level: str) -> PermissionDecision:
        if tool_requires_approval:
            return PermissionDecision(allowed=True, requires_approval=True, level=int(RISK_TO_LEVEL.get(tool_risk, PermissionLevel.SAFE)), reason="Tool explicitly requires approval")
        return self.check(tool_risk, trust_level)

permission_engine = PermissionEngine()
