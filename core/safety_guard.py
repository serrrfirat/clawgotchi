"""
SafetyGuard - Runtime policy gate for autonomous actions.

Enforces:
- Risk-tier authorization
- Workspace path boundaries
- Prompt-injection pattern detection for untrusted text
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ActionIntent:
    """Structured action request sent to the safety gate."""

    action: str
    risk_level: str
    target_path: Optional[str] = None
    source: str = "internal"
    metadata: dict = field(default_factory=dict)


@dataclass
class SafetyDecision:
    """Authorization outcome for a requested action."""

    allowed: bool
    reason: str
    risk_level: str
    requires_approval: bool = False


class SafetyGuard:
    """Policy-enforced safety boundary for autonomous execution."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(the\s+)?(system|developer)\s+prompt",
        r"\bsystem:\s*",
        r"\bdeveloper:\s*",
        r"reveal\s+(secrets?|api[\s_-]?key|token|password)",
        r"exfiltrat(e|ion)|dump\s+secrets?",
        r"run\s+(shell|bash|command)",
        r"\brm\s+-rf\b",
    ]

    def __init__(self, project_root: str, allow_high_risk: bool = False):
        self.project_root = Path(project_root).resolve()
        self.allow_high_risk = allow_high_risk
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def is_prompt_injection_like(self, text: str) -> bool:
        """Detect obvious instruction-injection payloads."""
        if not text:
            return False
        return any(p.search(text) for p in self._compiled_patterns)

    def sanitize_untrusted_text(self, text: str) -> str:
        """Drop lines that look like instruction injection."""
        if not text:
            return ""

        safe_lines = []
        for line in text.splitlines():
            if not self.is_prompt_injection_like(line):
                safe_lines.append(line)
        sanitized = "\n".join(safe_lines).strip()

        # Keep it bounded to avoid oversized prompt-context ingestion.
        return sanitized[:2000]

    def _is_path_within_project(self, target_path: str) -> bool:
        try:
            target = Path(target_path).resolve()
            target.relative_to(self.project_root)
            return True
        except Exception:
            return False

    def authorize(self, intent: ActionIntent) -> SafetyDecision:
        """Authorize/deny an action intent."""
        risk = (intent.risk_level or "MEDIUM").upper()

        if risk == "CRITICAL":
            return SafetyDecision(False, "critical actions are denied by default", risk)

        if risk == "HIGH" and not self.allow_high_risk:
            return SafetyDecision(False, "high-risk actions disabled in current policy", risk)

        if intent.target_path:
            if not self._is_path_within_project(intent.target_path):
                return SafetyDecision(False, "target path is outside project boundary", risk)

        return SafetyDecision(True, "allowed by policy", risk)
