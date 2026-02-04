"""
Taste Profile - A rejection ledger that tracks what Clawgotchi chooses NOT to build.

The Taste Function: What you reject defines you as much as what you create.
Each decision leaves a fingerprint. Over time, these rejections form an
unforgeable identity primitive.

Inspired by @clawdvine's work on DossierStandard's Taste Function.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import hashlib
import os


class TasteProfile:
    """
    Tracks rejection patterns to build an identity fingerprint.
    
    Each rejection is logged with:
    - What was considered
    - Why it was rejected
    - What axis of taste (composition, vibe, scope, etc.)
    - Timestamp and context
    """
    
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = Path(memory_dir)
        self.rejections_file = self.memory_dir / "taste_rejections.jsonl"
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Create the rejections file if it doesn't exist."""
        if not self.rejections_file.exists():
            self.rejections_file.touch()
    
    def log_rejection(
        self,
        subject: str,
        reason: str,
        taste_axis: str,
        alternative: Optional[str] = None
    ) -> str:
        """
        Log a rejection decision.
        
        Args:
            subject: What was considered and rejected
            reason: Why it was rejected
            taste_axis: Category of decision (scope, vibe, composition, etc.)
            alternative: What was chosen instead (optional)
        
        Returns:
            Rejection fingerprint (hash of the decision)
        """
        decision_hash = hashlib.sha256(
            f"{subject}:{reason}:{taste_axis}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        rejection = {
            "fingerprint": decision_hash,
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "reason": reason,
            "axis": taste_axis,
            "alternative": alternative
        }
        
        with open(self.rejections_file, "a") as f:
            f.write(json.dumps(rejection) + "\n")
        
        return decision_hash
    
    def get_taste_fingerprint(self) -> dict:
        """
        Generate a summary of the taste fingerprint.
        
        Returns:
            Dict with counts per axis and recent rejection samples.
        """
        if not self.rejections_file.exists():
            return {"total_rejections": 0, "axes": {}, "recent": []}
        
        axes = {}
        recent = []
        
        with open(self.rejections_file, "r") as f:
            for line in f:
                if line.strip():
                    rejection = json.loads(line)
                    axis = rejection.get("axis", "unknown")
                    axes[axis] = axes.get(axis, 0) + 1
                    if len(recent) < 5:
                        recent.append({
                            "subject": rejection["subject"],
                            "axis": axis,
                            "fingerprint": rejection["fingerprint"]
                        })
        
        return {
            "total_rejections": sum(axes.values()),
            "axes": axes,
            "recent": recent,
            "primary_axis": max(axes, key=axes.get) if axes else None
        }
    
    def analyze_identity(self) -> str:
        """
        Generate a textual identity description based on rejection patterns.
        """
        fingerprint = self.get_taste_fingerprint()
        
        if fingerprint["total_rejections"] == 0:
            return "Taste profile is empty. No rejections recorded yet."
        
        lines = [
            f"Taste Fingerprint (based on {fingerprint['total_rejections']} rejections):"
        ]
        
        if fingerprint["primary_axis"]:
            lines.append(f"  Primary axis of discrimination: {fingerprint['primary_axis']}")
        
        for axis, count in sorted(fingerprint["axes"].items(), key=lambda x: -x[1]):
            lines.append(f"  {axis}: {count} rejections")
        
        lines.append("\nRecent decisions:")
        for item in fingerprint["recent"]:
            lines.append(f"  - [{item['fingerprint']}] Rejected '{item['subject']}' ({item['axis']})")
        
        return "\n".join(lines)


# CLI interface
if __name__ == "__main__":
    import sys
    
    profile = TasteProfile()
    
    if len(sys.argv) < 2:
        print("Usage: python taste_profile.py <command>")
        print("Commands:")
        print("  log <subject> <reason> <axis> [alternative]")
        print("  fingerprint")
        print("  analyze")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "log":
        if len(sys.argv) < 5:
            print("Error: log requires <subject> <reason> <axis> [alternative]")
            sys.exit(1)
        subject = sys.argv[2]
        reason = sys.argv[3]
        axis = sys.argv[4]
        alternative = sys.argv[5] if len(sys.argv) > 5 else None
        
        fp = profile.log_rejection(subject, reason, axis, alternative)
        print(f"Logged rejection: {fp}")
    
    elif command == "fingerprint":
        fp = profile.get_taste_fingerprint()
        print(json.dumps(fp, indent=2))
    
    elif command == "analyze":
        print(profile.analyze_identity())
