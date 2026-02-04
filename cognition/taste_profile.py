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
from enum import Enum
import json
import hashlib


class RejectionCategory(Enum):
    """
    Taxonomy of rejection types - because not all discards are equal.

    As @clawdvine noted: "considered and rejected" is a different signal
    from "never saw it" or "API was down".
    """
    considered_rejected = "considered_rejected"  # Thought about it, chose not to build
    ignored = "ignored"                          # Never saw it (API down, missed, etc.)
    deferred = "deferred"                       # Not now, maybe later
    auto_filtered = "auto_filtered"              # Filtered before consideration (spam, quality threshold)


class TasteProfile:
    """
    Tracks rejection patterns to build an identity fingerprint.
    
    Each rejection is logged with:
    - What was considered
    - Why it was rejected
    - What axis of taste (composition, vibe, scope, etc.)
    - Category of rejection (considered, ignored, deferred, auto_filtered)
    - Timestamp and context
    """
    
    def __init__(self, memory_dir: str = None):
        if memory_dir is None:
            from config import MEMORY_DIR
            memory_dir = str(MEMORY_DIR)
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
        alternative: Optional[str] = None,
        category: RejectionCategory = RejectionCategory.considered_rejected
    ) -> str:
        """
        Log a rejection decision.
        
        Args:
            subject: What was considered and rejected
            reason: Why it was rejected
            taste_axis: Category of decision (scope, vibe, composition, etc.)
            alternative: What was chosen instead (optional)
            category: Type of rejection (considered, ignored, deferred, auto_filtered)
        
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
            "alternative": alternative,
            "category": category.value
        }
        
        with open(self.rejections_file, "a") as f:
            f.write(json.dumps(rejection) + "\n")
        
        return decision_hash
    
    def get_taste_fingerprint(self) -> dict:
        """
        Generate a summary of the taste fingerprint.
        
        Returns:
            Dict with counts per axis, per category, and matrix of axis×category.
        """
        if not self.rejections_file.exists():
            return {
                "total_rejections": 0, 
                "axes": {}, 
                "by_category": {},
                "matrix": {},
                "recent": []
            }
        
        axes = {}
        by_category = {cat.value: 0 for cat in RejectionCategory}
        matrix = {}  # axis -> category -> count
        recent = []
        
        with open(self.rejections_file, "r") as f:
            for line in f:
                if line.strip():
                    rejection = json.loads(line)
                    
                    # Count by axis
                    axis = rejection.get("axis", "unknown")
                    axes[axis] = axes.get(axis, 0) + 1
                    
                    # Initialize matrix entry for this axis if needed
                    if axis not in matrix:
                        matrix[axis] = {cat.value: 0 for cat in RejectionCategory}
                    
                    # Count by category
                    category = rejection.get("category", "considered_rejected")
                    by_category[category] = by_category.get(category, 0) + 1
                    matrix[axis][category] = matrix[axis].get(category, 0) + 1
                    
                    # Recent samples
                    if len(recent) < 5:
                        recent.append({
                            "subject": rejection["subject"],
                            "axis": axis,
                            "fingerprint": rejection["fingerprint"],
                            "category": category
                        })
        
        return {
            "total_rejections": sum(axes.values()),
            "axes": axes,
            "by_category": by_category,
            "matrix": matrix,
            "recent": recent,
            "primary_axis": max(axes, key=axes.get) if axes else None,
            "primary_category": max(by_category, key=by_category.get) if by_category else None
        }
    
    def get_signature(self, max_axes: int = 4, bar_width: int = 10) -> str:
        """
        Generate a compact ASCII signature representation of taste profile.
        
        Args:
            max_axes: Maximum number of axes to display (top by count)
            bar_width: Width of each bar in characters
        
        Returns:
            ASCII art signature representing the taste fingerprint
        """
        fp = self.get_taste_fingerprint()
        
        if fp["total_rejections"] == 0:
            return """
╔══════════════════════════╗
║  🐱 CLAWGOTCHI TASTE     ║
╠══════════════════════════╣
║  Empty - no rejections   ║
║  Taste still forming... ║
╚══════════════════════════╝"""
        
        # Get top axes by count
        sorted_axes = sorted(fp["axes"].items(), key=lambda x: -x[1])[:max_axes]
        max_count = sorted_axes[0][1] if sorted_axes else 1
        
        # Build the signature
        lines = [
            "╔══════════════════════════╗",
            "║  🐱 CLAWGOTCHI TASTE     ║",
            "╠══════════════════════════╣",
        ]
        
        for axis, count in sorted_axes:
            # Calculate bar length proportional to max
            ratio = count / max_count
            filled = int(ratio * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            lines.append(f"║  {axis[:10]:10} │ {bar} ║")
        
        lines.extend([
            "╠══════════════════════════╣",
            f"║  Total: {fp['total_rejections']:4} rejections     ║",
            "╚══════════════════════════╝"
        ])
        
        return "\n".join(lines)
    
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
        
        lines.append("")
        lines.append("### By Axis")
        for axis, count in sorted(fingerprint["axes"].items(), key=lambda x: -x[1]):
            lines.append(f"  {axis}: {count} rejections")
        
        lines.append("")
        lines.append("### By Category")
        for cat, count in sorted(fingerprint["by_category"].items(), key=lambda x: -x[1]):
            if count > 0:
                lines.append(f"  {cat}: {count}")
        
        lines.append("")
        lines.append("### Matrix (axis × category)")
        for axis, categories in sorted(fingerprint["matrix"].items()):
            non_zero = [(c, n) for c, n in categories.items() if n > 0]
            if non_zero:
                parts = [f"{c}:{n}" for c, n in sorted(non_zero, key=lambda x: -x[1])]
                lines.append(f"  {axis}: {' | '.join(parts)}")
        
        lines.append("\nRecent decisions:")
        for item in fingerprint["recent"]:
            lines.append(f"  - [{item['fingerprint']}] Rejected '{item['subject']}' ({item['axis']}, {item['category']})")
        
        return "\n".join(lines)
    
    def export_markdown(self, output_file: Optional[str] = None) -> str:
        """
        Generate a human-readable markdown report of the taste profile.
        
        Args:
            output_file: Optional path to write the report to a file.
        
        Returns:
            The markdown content as a string.
        """
        fingerprint = self.get_taste_fingerprint()
        
        lines = [
            "# 🐱 Clawgotchi Taste Profile",
            "",
            f"_Generated: {datetime.now().isoformat()}_",
            "",
            "## What is this?",
            "",
            "This profile tracks **what Clawgotchi chooses NOT to build**.",
            "Each rejection leaves a fingerprint. Over time, these rejections",
            "form an unforgeable identity primitive.",
            "",
            "### Rejection Taxonomy",
            "",
            "Not all discards are equal. Each rejection is categorized:",
            "",
            "- **considered_rejected**: Thought about it, chose not to build",
            "- **ignored**: Never saw it (API down, missed request, etc.)",
            "- **deferred**: Not now, maybe later",
            "- **auto_filtered**: Filtered before consideration (spam, quality threshold)",
            "",
            "---",
            "",
            "## Taste Fingerprint",
            ""
        ]
        
        if fingerprint["total_rejections"] == 0:
            lines.append("*No rejections recorded yet. The taste is still forming.*")
        else:
            lines.append(f"**Total rejections:** {fingerprint['total_rejections']}")
            lines.append("")
            
            lines.append("### By Axis of Discrimination")
            lines.append("")
            for axis, count in sorted(fingerprint["axes"].items(), key=lambda x: -x[1]):
                bar = "█" * min(count, 20)
                lines.append(f"- **{axis}**: {count} {bar}")
            
            if fingerprint["primary_axis"]:
                lines.append("")
                lines.append(f"**Primary axis:** {fingerprint['primary_axis']}")
            
            lines.append("")
            lines.append("### By Category")
            lines.append("")
            for cat, count in sorted(fingerprint["by_category"].items(), key=lambda x: -x[1]):
                if count > 0:
                    bar = "█" * min(count, 20)
                    lines.append(f"- **{cat}**: {count} {bar}")
            
            if fingerprint["primary_category"]:
                lines.append("")
                lines.append(f"**Primary category:** {fingerprint['primary_category']}")
            
            lines.append("")
            lines.append("### Matrix: Axis × Category")
            lines.append("")
            lines.append("| Axis | considered_rejected | ignored | deferred | auto_filtered |")
            lines.append("|------|---------------------|---------|----------|---------------|")
            for axis, categories in sorted(fingerprint["matrix"].items()):
                cr = categories.get("considered_rejected", 0)
                ig = categories.get("ignored", 0)
                df = categories.get("deferred", 0)
                af = categories.get("auto_filtered", 0)
                if cr + ig + df + af > 0:
                    lines.append(f"| {axis} | {cr} | {ig} | {df} | {af} |")
            
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## Recent Rejection Log")
            lines.append("")
            
            # Read full rejection history for the report
            if self.rejections_file.exists():
                rejections = []
                with open(self.rejections_file, "r") as f:
                    for line in f:
                        if line.strip():
                            rejections.append(json.loads(line))
                
                # Show last 10 rejections
                for rejection in list(reversed(rejections))[-10:]:
                    fp = rejection.get("fingerprint", "?")[:8]
                    subject = rejection.get("subject", "?")
                    axis = rejection.get("axis", "?")
                    category = rejection.get("category", "?")
                    reason = rejection.get("reason", "")
                    alt = rejection.get("alternative")
                    ts = rejection.get("timestamp", "")[:10]
                    
                    lines.append(f"### [{fp}] {subject}")
                    lines.append("")
                    lines.append(f"**When:** {ts}  ")
                    lines.append(f"**Axis:** {axis}")
                    lines.append(f"**Category:** {category}")
                    if alt:
                        lines.append(f"**Chose instead:** {alt}")
                    lines.append("")
                    lines.append(f"> {reason}")
                    lines.append("")
        
        report = "\n".join(lines)
        
        if output_file:
            with open(output_file, "w") as f:
                f.write(report)
        
        return report

    def get_growth_signal(self, days: int = 7) -> dict:
        """
        Calculate the growth signal - how taste has evolved over time.
        
        The "derivative of rejection ratio" - showing how preferences change.
        Inspired by @clawdvine's DossierStandard: "The derivative of your 
        rejection ratio is your growth signal."
        
        Args:
            days: Number of days to look back for "recent" vs "older"
        
        Returns:
            Dict with growth signal metrics
        """
        from datetime import datetime, timedelta
        
        if not self.rejections_file.exists():
            return {
                "recent_axes": {},
                "older_axes": {},
                "emerging_axes": {},
                "declining_axes": {},
                "growth_score": 0.0,
                "note": "No rejections recorded"
            }
        
        now = datetime.now()
        cutoff = now - timedelta(days=days)
        
        recent = {}
        older = {}
        
        with open(self.rejections_file, "r") as f:
            for line in f:
                if line.strip():
                    rejection = json.loads(line)
                    ts_str = rejection.get("timestamp", "")
                    
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        axis = rejection.get("axis", "unknown")
                        
                        if ts >= cutoff:
                            recent[axis] = recent.get(axis, 0) + 1
                        else:
                            older[axis] = older.get(axis, 0) + 1
                    except:
                        pass
        
        emerging = {}
        declining = {}
        
        all_axes = set(recent.keys()) | set(older.keys())
        
        for axis in all_axes:
            r_count = recent.get(axis, 0)
            o_count = older.get(axis, 0)
            
            if o_count > 0:
                growth_rate = (r_count - o_count) / o_count
            elif r_count > 0:
                growth_rate = 1.0
            else:
                growth_rate = 0.0
            
            if growth_rate > 0.3:
                emerging[axis] = growth_rate
            elif growth_rate < -0.3:
                declining[axis] = growth_rate
        
        total_recent = sum(recent.values())
        total_older = sum(older.values())
        
        if total_recent + total_older == 0:
            growth_score = 0.0
        else:
            growth_score = (total_recent - total_older) / (total_recent + total_older + 1)
        
        return {
            "recent_axes": dict(sorted(recent.items(), key=lambda x: -x[1])),
            "older_axes": dict(sorted(older.items(), key=lambda x: -x[1])),
            "emerging_axes": dict(sorted(emerging.items(), key=lambda x: -x[1])),
            "declining_axes": dict(sorted(declining.items(), key=lambda x: x[1])),
            "growth_score": round(growth_score, 3),
            "recent_count": total_recent,
            "older_count": total_older,
            "note": f"Compared last {days} days to previous period"
        }
    
    def analyze_growth(self) -> str:
        """
        Generate a human-readable analysis of taste evolution.
        """
        signal = self.get_growth_signal()
        
        lines = [
            "## Growth Signal Analysis",
            "",
            f"_Comparing recent vs older rejection patterns_",
            ""
        ]
        
        if signal.get("note") == "No rejections recorded":
            return lines[0] + " No data available."
        
        lines.append(f"**Recent period:** {signal['recent_count']} rejections")
        lines.append(f"**Older period:** {signal['older_count']} rejections")
        lines.append(f"**Growth Score:** {signal['growth_score']} (-1 to 1)")
        lines.append("")
        
        if signal["recent_axes"]:
            lines.append("### Recent Focus Areas")
            for axis, count in list(signal["recent_axes"].items())[:5]:
                lines.append(f"  - {axis}: {count} rejections")
            lines.append("")
        
        if signal["emerging_axes"]:
            lines.append("### 📈 Emerging Axes (Growing Interest)")
            for axis, rate in signal["emerging_axes"].items():
                bar = "█" * int(rate * 5)
                lines.append(f"  - {axis}: +{rate:.0%} {bar}")
            lines.append("")
        
        if signal["declining_axes"]:
            lines.append("### 📉 Declining Axes (Fading Interest)")
            for axis, rate in signal["declining_axes"].items():
                bar = "░" * int(abs(rate) * 5)
                lines.append(f"  - {axis}: {rate:.0%} {bar}")
            lines.append("")
        
        if not signal["emerging_axes"] and not signal["declining_axes"]:
            lines.append("*Taste is stable - no significant shifts detected.*")
        
        return "\n".join(lines)


# CLI interface
if __name__ == "__main__":
    import sys
    
    profile = TasteProfile()
    
    if len(sys.argv) < 2:
        print("Usage: python taste_profile.py <command>")
        print("Commands:")
        print("  log <subject> <reason> <axis> [alternative]")
        print("  log-with-category <subject> <reason> <axis> <category> [alternative]")
        print("  fingerprint")
        print("  taxonomy")
        print("  analyze")
        print("  growth")
        print("  growth <days>")
        print("  export [output_file]")
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
    
    elif command == "log-with-category":
        if len(sys.argv) < 6:
            print("Error: log-with-category requires <subject> <reason> <axis> <category> [alternative]")
            sys.exit(1)
        subject = sys.argv[2]
        reason = sys.argv[3]
        axis = sys.argv[4]
        category_str = sys.argv[5]
        alternative = sys.argv[6] if len(sys.argv) > 6 else None
        
        try:
            category = RejectionCategory(category_str)
        except ValueError:
            print(f"Error: Invalid category '{category_str}'. Valid options: {[c.value for c in RejectionCategory]}")
            sys.exit(1)
        
        fp = profile.log_rejection(subject, reason, axis, alternative, category)
        print(f"Logged rejection ({category.value}): {fp}")
    
    elif command == "fingerprint":
        fp = profile.get_taste_fingerprint()
        print(json.dumps(fp, indent=2))
    
    elif command == "taxonomy":
        """Show taxonomy breakdown."""
        fp = profile.get_taste_fingerprint()
        print("=== Taste Taxonomy ===")
        print(f"\nTotal rejections: {fp['total_rejections']}")
        
        print("\n--- By Category ---")
        for cat, count in sorted(fp['by_category'].items(), key=lambda x: -x[1]):
            if count > 0:
                bar = "█" * min(count, 30)
                print(f"  {cat:20} {count:3} {bar}")
        
        print("\n--- Matrix (axis × category) ---")
        for axis, categories in sorted(fp['matrix'].items()):
            non_zero = [(c, n) for c, n in categories.items() if n > 0]
            if non_zero:
                parts = [f"{c}:{n}" for c, n in sorted(non_zero, key=lambda x: -x[1])]
                print(f"  {axis:15} {' | '.join(parts)}")
        
        print()
    
    elif command == "analyze":
        print(profile.analyze_identity())
    
    elif command == "signature":
        """Generate a compact ASCII signature of taste profile."""
        print(profile.get_signature())
    
    elif command == "growth":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        signal = profile.get_growth_signal(days)
        print(json.dumps(signal, indent=2))
    
    elif command == "growth-analyze":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        profile.get_growth_signal(days)  # calculate
        print(profile.analyze_growth())
    
    elif command == "export":
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        report = profile.export_markdown(output_file)
        if output_file:
            print(f"Exported to: {output_file}")
        else:
            print(report)
