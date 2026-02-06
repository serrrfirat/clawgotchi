"""
SelfEvolutionLoop - hypothesis tracking for behavioral self-improvement.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class SelfEvolutionLoop:
    """Tracks cycle outcomes and proposes measurable behavior hypotheses."""

    AXIS_ACTION_MAP = {
        "energy": "CURATE",
        "competence": "VERIFY",
        "impact": "BUILD",
        "novelty": "EXPLORE",
    }

    def __init__(self, state_path: str = "memory/self_evolution.json"):
        self.state_path = Path(state_path)
        self.state = self._load()

    def _default_state(self) -> dict:
        return {
            "cycles": [],
            "hypotheses": [],
            "updated_at": datetime.now().isoformat(),
        }

    def _load(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_state()

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state["updated_at"] = datetime.now().isoformat()
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def record_cycle(
        self,
        action: str,
        success: bool,
        reward: float,
        policy: str = "default",
    ):
        cycle = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "success": bool(success),
            "reward": float(reward),
            "policy": policy,
        }
        self.state.setdefault("cycles", []).append(cycle)
        if len(self.state["cycles"]) > 2000:
            self.state["cycles"] = self.state["cycles"][-2000:]
        self._save()

    def success_rate(self, window: int = 30) -> float:
        cycles = self.state.get("cycles", [])
        if not cycles:
            return 0.0
        recent = cycles[-window:]
        return round(sum(1 for c in recent if c.get("success")) / len(recent), 3)

    def propose_hypothesis(self, axes: dict, action_stats: dict) -> Optional[dict]:
        """Create a hypothesis based on weakest ikigai axis."""
        if not axes:
            return None

        target_axis = min(axes, key=lambda k: axes.get(k, 0))
        suggested_action = self.AXIS_ACTION_MAP.get(target_axis, "VERIFY")
        action_info = action_stats.get(suggested_action, {})
        attempts = action_info.get("attempts", 0)
        successes = action_info.get("successes", 0)
        observed = (successes / attempts) if attempts else 0.0

        hypothesis = {
            "id": f"hyp-{uuid.uuid4().hex[:8]}",
            "created_at": datetime.now().isoformat(),
            "target_axis": target_axis,
            "suggested_action": suggested_action,
            "summary": (
                f"If I prioritize {suggested_action}, I can raise {target_axis} "
                f"(observed success {observed:.2f})."
            ),
            "status": "proposed",
        }
        self.state.setdefault("hypotheses", []).append(hypothesis)
        self._save()
        return hypothesis

    def evaluate_hypothesis(
        self,
        hypothesis_id: str,
        baseline_rate: float,
        min_lift: float = 0.03,
        window: int = 30,
    ) -> dict:
        """Evaluate whether a hypothesis should be promoted."""
        current_rate = self.success_rate(window=window)
        lift = round(current_rate - baseline_rate, 3)
        promote = lift >= min_lift

        result = {
            "hypothesis_id": hypothesis_id,
            "baseline_rate": baseline_rate,
            "current_rate": current_rate,
            "lift": lift,
            "promote": promote,
        }

        for hyp in self.state.get("hypotheses", []):
            if hyp.get("id") == hypothesis_id:
                hyp["status"] = "validated" if promote else "rejected"
                hyp["evaluation"] = result
                break

        self._save()
        return result
