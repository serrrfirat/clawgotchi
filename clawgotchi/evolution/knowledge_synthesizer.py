"""
KnowledgeSynthesizer - Extract durable knowledge from ephemeral memories.

Compresses learnings into principles that compound over time.
Updates KNOWLEDGE.md with synthesized insights.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class Principle:
    """An extracted operating principle."""
    id: str
    text: str
    category: str  # building, memory, health, identity
    evidence_count: int
    confidence: float
    created_at: str
    last_validated: Optional[str] = None


class KnowledgeSynthesizer:
    """Extract durable knowledge from ephemeral memories."""

    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = Path(memory_dir)
        self.knowledge_path = self.memory_dir / "KNOWLEDGE.md"
        self.principles_path = self.memory_dir / "principles.json"
        self._principles: list[Principle] = []
        self._load_principles()

    def _load_principles(self):
        """Load principles from disk."""
        if self.principles_path.exists():
            try:
                data = json.loads(self.principles_path.read_text())
                self._principles = [
                    Principle(**p) for p in data.get("principles", [])
                ]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._principles = []

    def _save_principles(self):
        """Save principles to disk."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "principles": [
                {
                    "id": p.id,
                    "text": p.text,
                    "category": p.category,
                    "evidence_count": p.evidence_count,
                    "confidence": p.confidence,
                    "created_at": p.created_at,
                    "last_validated": p.last_validated,
                }
                for p in self._principles
            ],
            "updated_at": datetime.now().isoformat(),
        }
        self.principles_path.write_text(json.dumps(data, indent=2))

    def extract_principles(self, daily_logs: list[str]) -> list[dict]:
        """Extract operating principles from daily log content.

        Looks for patterns like:
        - "When X happens, Y works better than Z"
        - "Building before verifying causes N% more failures"
        - Repeated themes across multiple days

        Args:
            daily_logs: List of daily log file contents

        Returns:
            List of principle dicts with text, category, confidence
        """
        principles = []

        # Combine all logs for pattern analysis
        combined = "\n".join(daily_logs)

        # Pattern: explicit principle statements
        explicit_patterns = [
            r"learned that (.+)",
            r"principle: (.+)",
            r"insight: (.+)",
            r"always (.+) before (.+)",
            r"never (.+) without (.+)",
        ]

        for pattern in explicit_patterns:
            matches = re.findall(pattern, combined, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    text = " ".join(match)
                else:
                    text = match
                principles.append({
                    "text": text.strip(),
                    "category": self._categorize_principle(text),
                    "confidence": 0.6,
                })

        # Pattern: repeated themes
        themes = self._extract_themes(daily_logs)
        for theme, count in themes.items():
            if count >= 3:  # Appears in 3+ logs
                principles.append({
                    "text": f"Recurring theme: {theme}",
                    "category": self._categorize_principle(theme),
                    "confidence": min(0.9, 0.5 + count * 0.1),
                })

        return principles

    def _categorize_principle(self, text: str) -> str:
        """Categorize a principle by content."""
        text_lower = text.lower()

        if any(w in text_lower for w in ["build", "module", "feature", "code"]):
            return "building"
        if any(w in text_lower for w in ["memory", "log", "archive", "forget"]):
            return "memory"
        if any(w in text_lower for w in ["health", "error", "fail", "recover"]):
            return "health"
        if any(w in text_lower for w in ["soul", "identity", "value", "taste"]):
            return "identity"

        return "general"

    def _extract_themes(self, logs: list[str]) -> dict[str, int]:
        """Extract recurring themes from logs."""
        themes = {}

        # Simple word frequency for common action words
        action_words = [
            "build", "explore", "verify", "curate", "integrate",
            "error", "success", "fail", "improve", "learn",
        ]

        for log in logs:
            log_lower = log.lower()
            for word in action_words:
                if word in log_lower:
                    themes[word] = themes.get(word, 0) + 1

        return themes

    def synthesize_insight(self, memories: list[dict]) -> str:
        """Compress multiple related memories into one insight.

        Args:
            memories: List of memory dicts with 'text' and 'category' keys

        Returns:
            Synthesized insight string
        """
        if not memories:
            return ""

        # Group by category
        by_category = {}
        for mem in memories:
            cat = mem.get("category", "general")
            by_category.setdefault(cat, []).append(mem.get("text", ""))

        # Generate insight for largest category
        largest_cat = max(by_category.keys(), key=lambda k: len(by_category[k]))
        texts = by_category[largest_cat]

        if len(texts) == 1:
            return texts[0]

        # Find common words
        words = set(texts[0].lower().split())
        for text in texts[1:]:
            words &= set(text.lower().split())

        common = " ".join(sorted(words)[:5])
        return f"Pattern in {largest_cat}: {common} (from {len(texts)} memories)"

    def update_knowledge(self, new_insights: list[str]):
        """Add new knowledge to KNOWLEDGE.md.

        Deduplicates, organizes by topic, timestamps.
        """
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Load existing content
        existing = ""
        if self.knowledge_path.exists():
            existing = self.knowledge_path.read_text()

        # Parse existing sections
        sections = self._parse_knowledge_sections(existing)

        # Add new insights
        timestamp = datetime.now().strftime("%Y-%m-%d")
        for insight in new_insights:
            category = self._categorize_principle(insight)
            if category not in sections:
                sections[category] = []

            # Deduplicate by checking if insight text is in any existing entry
            existing_texts = [
                line.split("] ", 1)[-1] if "] " in line else line[2:]
                for line in sections[category]
            ]
            if insight not in existing_texts:
                sections[category].append(f"- [{timestamp}] {insight}")

        # Rebuild KNOWLEDGE.md
        self._write_knowledge(sections)

    def _parse_knowledge_sections(self, content: str) -> dict[str, list[str]]:
        """Parse KNOWLEDGE.md into sections."""
        sections = {}
        current_section = "general"

        for line in content.split("\n"):
            if line.startswith("## "):
                current_section = line[3:].strip().lower()
                sections.setdefault(current_section, [])
            elif line.startswith("- "):
                sections.setdefault(current_section, []).append(line)

        return sections

    def _write_knowledge(self, sections: dict[str, list[str]]):
        """Write KNOWLEDGE.md from sections dict."""
        lines = ["# KNOWLEDGE.md - Durable Wisdom\n"]
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

        for section, items in sorted(sections.items()):
            if items:
                lines.append(f"\n## {section.title()}\n")
                for item in items[-20:]:  # Keep last 20 per section
                    lines.append(item)

        self.knowledge_path.write_text("\n".join(lines))

    def get_relevant_knowledge(self, context: str) -> list[str]:
        """Retrieve knowledge relevant to current situation.

        Args:
            context: Current situation description

        Returns:
            List of relevant knowledge items
        """
        if not self.knowledge_path.exists():
            return []

        content = self.knowledge_path.read_text()
        context_words = set(context.lower().split())

        relevant = []
        for line in content.split("\n"):
            if line.startswith("- "):
                line_words = set(line.lower().split())
                if context_words & line_words:
                    relevant.append(line[2:])  # Remove "- " prefix

        return relevant[:10]  # Return top 10

    def should_consolidate(self, wake_count: int) -> bool:
        """Check if consolidation is due (every 10 wakes)."""
        return wake_count > 0 and wake_count % 10 == 0

    def run_consolidation_cycle(self, days: int = 7) -> dict:
        """Full consolidation: extract, synthesize, update.

        Args:
            days: How many days of logs to process

        Returns:
            Dict with extracted_count, synthesized_count, updated status
        """
        # Gather daily logs
        logs = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            log_path = self.memory_dir / f"{date}.md"
            if log_path.exists():
                logs.append(log_path.read_text())

        if not logs:
            return {"extracted_count": 0, "synthesized_count": 0, "updated": False}

        # Extract principles
        principles = self.extract_principles(logs)

        # Synthesize into insights
        insights = []
        if principles:
            # Group by category and synthesize
            by_cat = {}
            for p in principles:
                cat = p.get("category", "general")
                by_cat.setdefault(cat, []).append(p)

            for cat, items in by_cat.items():
                if len(items) >= 2:
                    insight = self.synthesize_insight(items)
                    if insight:
                        insights.append(insight)

        # Update KNOWLEDGE.md
        if insights:
            self.update_knowledge(insights)

        return {
            "extracted_count": len(principles),
            "synthesized_count": len(insights),
            "updated": len(insights) > 0,
        }

    def get_principles(self) -> list[Principle]:
        """Get all stored principles."""
        return self._principles.copy()

    def add_principle(self, text: str, category: str, confidence: float = 0.7):
        """Add a new principle."""
        principle = Principle(
            id=f"prin-{len(self._principles) + 1}",
            text=text,
            category=category,
            evidence_count=1,
            confidence=confidence,
            created_at=datetime.now().isoformat(),
        )
        self._principles.append(principle)
        self._save_principles()
