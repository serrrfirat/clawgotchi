"""
IkigaiEngine - Stage 2 autonomy scoring and policy gate.

Tracks what gives the agent long-term fulfillment across four axes:
- energy
- competence
- impact
- novelty

Also maintains a promotion/rollback gate for policy experiments.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class IkigaiEngine:
    """Scores actions by ikigai fitness and manages policy promotion."""

    ACTION_WEIGHTS = {
        "BUILD": {"energy": 0.20, "competence": 0.35, "impact": 0.30, "novelty": 0.15},
        "EXPLORE": {"energy": 0.30, "competence": 0.10, "impact": 0.15, "novelty": 0.45},
        "VERIFY": {"energy": 0.10, "competence": 0.40, "impact": 0.35, "novelty": 0.15},
        "CURATE": {"energy": 0.20, "competence": 0.20, "impact": 0.35, "novelty": 0.25},
        "INTEGRATE": {"energy": 0.15, "competence": 0.30, "impact": 0.40, "novelty": 0.15},
        "CONSOLIDATE": {"energy": 0.15, "competence": 0.25, "impact": 0.35, "novelty": 0.25},
        "REST": {"energy": 0.45, "competence": 0.10, "impact": 0.10, "novelty": 0.35},
    }

    def __init__(
        self,
        state_path: str = None,
        gate_path: str = None,
        success_target: float = 0.90,
    ):
        if state_path is None or gate_path is None:
            from config import MEMORY_DIR
            state_path = state_path or str(MEMORY_DIR / "ikigai_state.json")
            gate_path = gate_path or str(MEMORY_DIR / "policy_gate.json")

        self.state_path = Path(state_path)
        self.gate_path = Path(gate_path)
        self.success_target = success_target
        self.alpha = 0.25

        self.state = self._load_state()
        self.gate = self._load_gate()

    def _default_state(self) -> dict:
        return {
            "axes": {
                "energy": 0.50,
                "competence": 0.50,
                "impact": 0.50,
                "novelty": 0.50,
            },
            "actions": {},
            "updated_at": datetime.now().isoformat(),
        }

    def _default_gate(self) -> dict:
        return {
            "active_policy": "default",
            "history": {"default": [], "ikigai": []},
            "updated_at": datetime.now().isoformat(),
        }

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_state()

    def _load_gate(self) -> dict:
        if self.gate_path.exists():
            try:
                return json.loads(self.gate_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_gate()

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state["updated_at"] = datetime.now().isoformat()
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def _save_gate(self):
        self.gate_path.parent.mkdir(parents=True, exist_ok=True)
        self.gate["updated_at"] = datetime.now().isoformat()
        self.gate_path.write_text(json.dumps(self.gate, indent=2))

    @staticmethod
    def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _ema(self, current: float, target: float) -> float:
        return self._clip(current + self.alpha * (target - current))

    def _action_stats(self, action_type: str) -> dict:
        actions = self.state.setdefault("actions", {})
        if action_type not in actions:
            actions[action_type] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "avg_reward": 0.50,
            }
        return actions[action_type]

    def _axis_targets(self, action_type: str, success: bool, result_text: str) -> dict:
        base = dict(self.ACTION_WEIGHTS.get(action_type, self.ACTION_WEIGHTS["VERIFY"]))
        text = (result_text or "").lower()

        if success:
            base["energy"] = max(base["energy"], 0.60)
            base["competence"] = max(base["competence"], 0.55)
            base["impact"] = max(base["impact"], 0.55)
            base["novelty"] = max(base["novelty"], 0.60)
            if "built" in text or "integrated" in text:
                base["impact"] = self._clip(base["impact"] + 0.20)
            if "explor" in text or "new" in text:
                base["novelty"] = self._clip(base["novelty"] + 0.15)
            if "verified" in text or "passing" in text:
                base["competence"] = self._clip(base["competence"] + 0.15)
            base["energy"] = self._clip(base["energy"] + 0.10)
            return base

        base["energy"] = self._clip(base["energy"] - 0.30)
        base["competence"] = self._clip(base["competence"] - 0.35)
        base["impact"] = self._clip(base["impact"] - 0.30)
        base["novelty"] = self._clip(base["novelty"] - 0.15)
        return base

    def _reward_from_axes(self, axes: dict) -> float:
        return (
            0.25 * axes["energy"]
            + 0.30 * axes["competence"]
            + 0.30 * axes["impact"]
            + 0.15 * axes["novelty"]
        )

    def record_outcome(self, action_type: str, success: bool, result_text: str = ""):
        """Update action stats + ikigai axes from an executed action."""
        stats = self._action_stats(action_type)
        stats["attempts"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

        targets = self._axis_targets(action_type, success, result_text)
        axes = self.state.setdefault("axes", self._default_state()["axes"])
        for axis, target in targets.items():
            axes[axis] = self._ema(axes.get(axis, 0.5), target)

        reward = self._reward_from_axes(targets)
        stats["avg_reward"] = self._ema(stats.get("avg_reward", 0.5), reward)
        self._save_state()

    def _success_rate(self, action_type: str) -> float:
        stats = self._action_stats(action_type)
        attempts = stats.get("attempts", 0)
        if attempts == 0:
            return 1.0
        return stats.get("successes", 0) / attempts

    def expected_action_score(self, action_type: str, base_priority: float = 1.0) -> float:
        """Expected score for choosing an action now."""
        axes = self.state.get("axes", self._default_state()["axes"])
        weights = self.ACTION_WEIGHTS.get(action_type, self.ACTION_WEIGHTS["VERIFY"])
        intrinsic = sum(axes[axis] * w for axis, w in weights.items())

        stats = self._action_stats(action_type)
        attempts = stats.get("attempts", 0)
        success_rate = self._success_rate(action_type)
        failure_penalty = 1.0
        if attempts >= 5 and success_rate < self.success_target:
            failure_penalty = max(0.1, success_rate / self.success_target)

        reward_component = 0.5 + 0.5 * stats.get("avg_reward", 0.5)
        return intrinsic * base_priority * failure_penalty * reward_component

    def choose_action(self, candidates: list[str], base_priorities: Optional[dict] = None) -> Optional[str]:
        """Choose best candidate action by expected ikigai score."""
        if not candidates:
            return None
        base_priorities = base_priorities or {}

        best_action = None
        best_score = -1.0
        for action in candidates:
            base = base_priorities.get(action, 1.0)
            score = self.expected_action_score(action, base_priority=base)
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def record_policy_outcome(self, policy_name: str, success: bool):
        history = self.gate.setdefault("history", {"default": [], "ikigai": []})
        bucket = history.setdefault(policy_name, [])
        bucket.append(1 if success else 0)
        if len(bucket) > 500:
            del bucket[:-500]
        self._save_gate()

    def _policy_rate(self, policy_name: str, window: Optional[int] = None) -> float:
        history = self.gate.get("history", {}).get(policy_name, [])
        if window:
            history = history[-window:]
        if not history:
            return 0.0
        return sum(history) / len(history)

    def should_promote_policy(self, min_samples: int = 20, min_lift: float = 0.03) -> bool:
        """Promote ikigai if it beats default with enough evidence."""
        history = self.gate.get("history", {})
        ikigai_hist = history.get("ikigai", [])
        default_hist = history.get("default", [])
        if len(ikigai_hist) < min_samples or len(default_hist) < min_samples:
            return False

        ikigai_rate = self._policy_rate("ikigai", window=min_samples)
        default_rate = self._policy_rate("default", window=min_samples)
        return (ikigai_rate - default_rate) >= min_lift

    def should_rollback_policy(self, window: int = 30) -> bool:
        """Rollback active ikigai policy if it violates failure budget."""
        if self.get_active_policy() != "ikigai":
            return False
        history = self.gate.get("history", {}).get("ikigai", [])
        if len(history) < window:
            return False
        return self._policy_rate("ikigai", window=window) < self.success_target

    def get_active_policy(self) -> str:
        return self.gate.get("active_policy", "default")

    def set_active_policy(self, policy_name: str):
        self.gate["active_policy"] = policy_name
        self._save_gate()
