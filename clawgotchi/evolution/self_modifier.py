"""
SelfModifier - Propose and apply modifications to self based on outcomes.

This is the core of self-improvement: analyzing what worked and what
didn't, then proposing changes to identity (SOUL.md) and behavior
(priority weights).

Modification Rules:
- Gradual: Max 1 soul change per week
- Justified: Every change needs evidence from 7+ days of data
- Logged: All changes recorded in soul_evolution.jsonl
- Reversible: Keep history to undo if needed
- Notified: Changes are visible in memory
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from .soul_manager import SoulManager, SoulChangeProposal


@dataclass
class ModificationProposal:
    """A proposal to modify behavior or identity."""
    id: str
    target: str  # "soul", "priority", "behavior"
    change_type: str
    description: str
    evidence: list[str]
    confidence: float
    created_at: str
    status: str = "pending"


class SelfModifier:
    """Propose and apply modifications to self based on outcomes."""

    # Minimum thresholds for proposing changes
    MIN_DAYS_EVIDENCE = 7
    MIN_CONFIDENCE = 0.7
    MAX_CHANGES_PER_WEEK = 1

    def __init__(
        self,
        soul_manager: SoulManager,
        assumption_tracker=None,
        taste_profile=None,
        memory_dir: str = "memory",
    ):
        self.soul = soul_manager
        self.assumptions = assumption_tracker
        self.taste = taste_profile
        self.memory_dir = Path(memory_dir)
        self.proposals_path = self.memory_dir / "modification_proposals.json"
        self._proposals: list[ModificationProposal] = []
        self._load()

    def _load(self):
        """Load proposals from disk."""
        if self.proposals_path.exists():
            try:
                data = json.loads(self.proposals_path.read_text())
                self._proposals = [
                    ModificationProposal(**p) for p in data.get("proposals", [])
                ]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def _save(self):
        """Save proposals to disk."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "proposals": [
                {
                    "id": p.id,
                    "target": p.target,
                    "change_type": p.change_type,
                    "description": p.description,
                    "evidence": p.evidence,
                    "confidence": p.confidence,
                    "created_at": p.created_at,
                    "status": p.status,
                }
                for p in self._proposals
            ],
            "updated_at": datetime.now().isoformat(),
        }
        self.proposals_path.write_text(json.dumps(data, indent=2))

    def analyze_outcomes(self, window_days: int = 7) -> dict:
        """Analyze recent outcomes to identify patterns.

        Looks at:
        - What worked? (successful builds, high health scores)
        - What failed? (errors, low health, rejected ideas)
        - What's improving? (trends)

        Returns dict with:
        - successes: list of successful patterns
        - failures: list of failure patterns
        - trends: dict of metrics and their direction
        - recommendations: suggested changes
        """
        results = {
            "successes": [],
            "failures": [],
            "trends": {},
            "recommendations": [],
        }

        # Analyze daily logs
        logs_analyzed = 0
        error_count = 0
        build_count = 0
        success_count = 0

        for i in range(window_days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            log_path = self.memory_dir / f"{date}.md"

            if log_path.exists():
                content = log_path.read_text().lower()
                logs_analyzed += 1

                # Count outcomes
                error_count += content.count("error")
                error_count += content.count("failed")
                build_count += content.count("built")
                build_count += content.count("building")
                success_count += content.count("completed")
                success_count += content.count("success")

        if logs_analyzed == 0:
            return results

        # Calculate rates
        error_rate = error_count / logs_analyzed
        build_rate = build_count / logs_analyzed
        success_rate = success_count / max(1, build_count + error_count)

        results["trends"] = {
            "error_rate": error_rate,
            "build_rate": build_rate,
            "success_rate": success_rate,
        }

        # Identify patterns
        if error_rate > 1.0:
            results["failures"].append(f"High error rate: {error_rate:.1f}/day")
            results["recommendations"].append("Increase VERIFY frequency")

        if build_rate > 2.0 and success_rate < 0.5:
            results["failures"].append("Building too fast with low success")
            results["recommendations"].append("Slow down, verify more before building")

        if success_rate > 0.8:
            results["successes"].append(f"High success rate: {success_rate:.0%}")

        # Analyze taste profile rejections if available
        if self.taste:
            try:
                fp = self.taste.get_taste_fingerprint()
                recent = fp.get("recent", [])
                if len(recent) > 10:
                    # Many rejections might indicate good taste or over-filtering
                    results["successes"].append(f"Active curation: {len(recent)} rejections")
            except Exception:
                pass

        # Analyze assumption accuracy if available
        if self.assumptions:
            try:
                summary = self.assumptions.get_summary()
                accuracy = summary.get("accuracy", 0)
                if accuracy > 0.8:
                    results["successes"].append(f"High assumption accuracy: {accuracy:.0%}")
                elif accuracy < 0.5:
                    results["failures"].append(f"Low assumption accuracy: {accuracy:.0%}")
                    results["recommendations"].append("Review and update core assumptions")
            except Exception:
                pass

        return results

    def should_modify_soul(self) -> Tuple[bool, str]:
        """Determine if soul modification is warranted.

        Criteria:
        - Consistent pattern over 7+ days
        - High confidence (>0.7)
        - Not already changed this week

        Returns:
            (should_modify, reason)
        """
        # Check if already changed this week
        changes_this_week = self.soul.count_changes_this_week()
        if changes_this_week >= self.MAX_CHANGES_PER_WEEK:
            return False, f"Already made {changes_this_week} changes this week"

        # Analyze outcomes
        outcomes = self.analyze_outcomes(window_days=self.MIN_DAYS_EVIDENCE)

        # Need significant patterns
        if not outcomes["successes"] and not outcomes["failures"]:
            return False, "No significant patterns detected"

        # High success rate might warrant adding a value
        if outcomes["trends"].get("success_rate", 0) > 0.9:
            return True, "Consistently high success rate - consider reinforcing values"

        # High error rate might need constraint
        if outcomes["trends"].get("error_rate", 0) > 2.0:
            return True, "High error rate - consider adding constraint"

        # Strong recommendations from analysis
        if len(outcomes["recommendations"]) >= 2:
            return True, "Multiple improvement opportunities identified"

        return False, "No strong evidence for soul modification"

    def propose_soul_update(self) -> Optional[SoulChangeProposal]:
        """Generate a specific soul change proposal.

        Based on: taste evolution, assumption accuracy, build success.
        """
        should_modify, reason = self.should_modify_soul()
        if not should_modify:
            return None

        outcomes = self.analyze_outcomes()

        # Determine what kind of change
        if "high success" in reason.lower():
            # Reinforce current values
            return self.soul.propose_change(
                section="values",
                change_type="add",
                new_value="**Consistency.** Maintain what works while exploring new things.",
                reason=reason,
                evidence=outcomes["successes"],
                confidence=0.75,
            )

        if "error rate" in reason.lower():
            # Add a constraint
            return self.soul.propose_change(
                section="constraints",
                change_type="add",
                new_value="Rush building without verification - always verify after significant changes.",
                reason=reason,
                evidence=outcomes["failures"],
                confidence=0.7,
            )

        if outcomes["recommendations"]:
            # General improvement
            rec = outcomes["recommendations"][0]
            return self.soul.propose_change(
                section="capabilities",
                change_type="add",
                new_value=f"Self-correct based on outcomes: {rec}",
                reason=reason,
                evidence=outcomes["recommendations"],
                confidence=0.7,
            )

        return None

    def propose_priority_adjustment(self) -> Optional[dict]:
        """Suggest changes to action priority weights.

        E.g., "Increase EXPLORE frequency, VERIFY is always passing"
        """
        outcomes = self.analyze_outcomes()

        if not outcomes["trends"]:
            return None

        adjustments = {}
        reasons = []

        error_rate = outcomes["trends"].get("error_rate", 0)
        success_rate = outcomes["trends"].get("success_rate", 1)
        build_rate = outcomes["trends"].get("build_rate", 0)

        # High errors → more VERIFY
        if error_rate > 1.5:
            adjustments["VERIFY"] = +2
            reasons.append(f"Error rate {error_rate:.1f}/day → boost VERIFY")

        # Low build rate → more BUILD
        if build_rate < 0.5:
            adjustments["BUILD"] = +1
            reasons.append("Low build activity → boost BUILD")

        # High success but low exploration → more EXPLORE
        if success_rate > 0.8 and build_rate > 1:
            adjustments["EXPLORE"] = +1
            reasons.append("High success → safe to explore more")

        if not adjustments:
            return None

        return {
            "adjustments": adjustments,
            "reasons": reasons,
            "confidence": 0.7,
            "created_at": datetime.now().isoformat(),
        }

    def execute_modification(self, proposal: ModificationProposal) -> dict:
        """Apply the modification with full logging.

        Returns dict with success status and details.
        """
        if proposal.target == "soul":
            # Convert to SoulChangeProposal and apply
            soul_proposal = self.soul.propose_change(
                section="values",  # Default
                change_type=proposal.change_type,
                new_value=proposal.description,
                reason=f"Self-modification: {proposal.description}",
                evidence=proposal.evidence,
                confidence=proposal.confidence,
            )
            success = self.soul.apply_change(soul_proposal)
            proposal.status = "applied" if success else "failed"
            self._save()
            return {
                "success": success,
                "target": "soul",
                "message": f"Soul modification {'applied' if success else 'failed'}",
            }

        if proposal.target == "priority":
            # Priority adjustments are returned as recommendations
            # (actual application happens in autonomous_agent)
            proposal.status = "recommended"
            self._save()
            return {
                "success": True,
                "target": "priority",
                "message": "Priority adjustment recommended",
                "adjustments": proposal.description,
            }

        proposal.status = "unknown_target"
        self._save()
        return {
            "success": False,
            "target": proposal.target,
            "message": f"Unknown modification target: {proposal.target}",
        }

    def get_pending_proposals(self) -> list[ModificationProposal]:
        """Get all pending modification proposals."""
        return [p for p in self._proposals if p.status == "pending"]

    def get_recent_modifications(self, days: int = 7) -> list[dict]:
        """Get modifications from the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = []

        for p in self._proposals:
            if p.created_at >= cutoff and p.status == "applied":
                recent.append({
                    "id": p.id,
                    "target": p.target,
                    "description": p.description,
                    "created_at": p.created_at,
                })

        return recent

    def run_weekly_evolution(self) -> dict:
        """Run the weekly evolution cycle.

        1. Analyze outcomes
        2. Check if modification warranted
        3. Generate proposal if warranted
        4. Apply with appropriate safeguards

        Returns summary of actions taken.
        """
        results = {
            "analyzed": False,
            "proposed": False,
            "applied": False,
            "details": [],
        }

        # 1. Analyze
        outcomes = self.analyze_outcomes()
        results["analyzed"] = True
        results["details"].append(f"Analyzed {self.MIN_DAYS_EVIDENCE} days of outcomes")

        # 2. Check if warranted
        should_modify, reason = self.should_modify_soul()
        results["details"].append(f"Modification check: {reason}")

        if not should_modify:
            return results

        # 3. Generate proposal
        proposal = self.propose_soul_update()
        if proposal:
            results["proposed"] = True
            results["details"].append(f"Proposed: {proposal.new_value[:50]}...")

            # 4. Apply
            success = self.soul.apply_change(proposal)
            results["applied"] = success
            if success:
                results["details"].append("Soul modification applied successfully")
            else:
                results["details"].append("Soul modification failed to apply")

        # Also check priority adjustments
        priority_adj = self.propose_priority_adjustment()
        if priority_adj:
            results["priority_adjustment"] = priority_adj

        return results
