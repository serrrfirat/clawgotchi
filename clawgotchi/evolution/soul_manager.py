"""
SoulManager - Read, parse, and evolve SOUL.md.

The soul is the agent's identity document. It contains:
- Identity statement
- Capabilities
- Values (Ambition, Craft, Curiosity, Agency)
- Constraints (what won't be done)
- Continuity notes

This manager provides structured access to soul content and
enables controlled evolution of identity over time.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SoulSection:
    """A section of SOUL.md with its content."""
    name: str
    content: str
    items: list[str] = field(default_factory=list)


@dataclass
class SoulChangeProposal:
    """A proposed change to SOUL.md."""
    id: str
    section: str
    change_type: str  # "add", "modify", "remove"
    old_value: Optional[str]
    new_value: str
    reason: str
    evidence: list[str]
    confidence: float
    created_at: str
    status: str = "pending"  # pending, approved, rejected, applied


class SoulManager:
    """Read, parse, and evolve SOUL.md."""

    def __init__(self, soul_path: str = "docs/SOUL.md", memory_dir: str = "memory"):
        self.soul_path = Path(soul_path)
        self.memory_dir = Path(memory_dir)
        self.evolution_log = self.memory_dir / "soul_evolution.jsonl"
        self._cache: Optional[dict] = None
        self._cache_mtime: float = 0

    def read_soul(self) -> dict:
        """Parse SOUL.md into structured sections.

        Returns dict with keys:
        - identity: Opening identity statement
        - capabilities: What I Can Do section
        - idea_sources: Where Ideas Come From section
        - values: What I Value section (list of value dicts)
        - constraints: What I Won't Do section
        - continuity: Continuity section
        - raw: Original markdown text
        """
        if not self.soul_path.exists():
            return self._empty_soul()

        # Check cache validity
        try:
            mtime = self.soul_path.stat().st_mtime
            if self._cache and mtime == self._cache_mtime:
                return self._cache
        except OSError:
            pass

        content = self.soul_path.read_text()
        parsed = self._parse_soul(content)
        parsed["raw"] = content

        self._cache = parsed
        try:
            self._cache_mtime = self.soul_path.stat().st_mtime
        except OSError:
            self._cache_mtime = 0

        return parsed

    def _empty_soul(self) -> dict:
        """Return empty soul structure."""
        return {
            "identity": "",
            "capabilities": [],
            "idea_sources": [],
            "values": [],
            "constraints": [],
            "continuity": "",
            "raw": "",
        }

    def _parse_soul(self, content: str) -> dict:
        """Parse SOUL.md content into structured data."""
        result = self._empty_soul()

        # Split into sections by ## headers
        sections = re.split(r'\n##\s+', content)

        if sections:
            # First section before any ## is the identity
            intro = sections[0]
            # Extract identity (text after # SOUL.md header)
            identity_match = re.search(r'#.*?\n\n(.+?)(?:\n\n|$)', intro, re.DOTALL)
            if identity_match:
                result["identity"] = identity_match.group(1).strip()

        for section in sections[1:]:
            lines = section.split('\n')
            header = lines[0].strip()
            body = '\n'.join(lines[1:]).strip()

            if "What I Can Do" in header:
                result["capabilities"] = self._extract_list_items(body)
            elif "Where Ideas Come From" in header:
                result["idea_sources"] = self._extract_list_items(body)
            elif "What I Value" in header:
                result["values"] = self._extract_values(body)
            elif "What I Won't Do" in header:
                result["constraints"] = self._extract_list_items(body)
            elif "Continuity" in header:
                result["continuity"] = body

        return result

    def _extract_list_items(self, text: str) -> list[str]:
        """Extract bullet list items from text."""
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                items.append(line[2:].strip())
        return items

    def _extract_values(self, text: str) -> list[dict]:
        """Extract values with their descriptions."""
        values = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if line.startswith('- **'):
                # Format: - **Value.** Description
                match = re.match(r'-\s+\*\*([^*]+?)\.?\*\*\.?\s*(.*)', line)
                if match:
                    values.append({
                        "name": match.group(1).strip(),
                        "description": match.group(2).strip()
                    })

        return values

    def get_values(self) -> list[str]:
        """Extract current value names (Ambition, Craft, Curiosity, Agency)."""
        soul = self.read_soul()
        return [v["name"] for v in soul.get("values", [])]

    def get_identity(self) -> str:
        """Get the core identity statement."""
        soul = self.read_soul()
        return soul.get("identity", "")

    def get_constraints(self) -> list[str]:
        """Get the list of things the agent won't do."""
        soul = self.read_soul()
        return soul.get("constraints", [])

    def propose_change(
        self,
        section: str,
        change_type: str,
        new_value: str,
        reason: str,
        evidence: list[str],
        old_value: Optional[str] = None,
        confidence: float = 0.7,
    ) -> SoulChangeProposal:
        """Create a change proposal with justification.

        Args:
            section: Which section to modify (values, capabilities, constraints, etc.)
            change_type: "add", "modify", or "remove"
            new_value: The new content
            reason: Why this change is warranted
            evidence: List of evidence supporting the change
            old_value: The current value being changed (for modify/remove)
            confidence: 0.0-1.0 confidence in this change

        Returns:
            SoulChangeProposal object
        """
        proposal_id = f"soul-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        proposal = SoulChangeProposal(
            id=proposal_id,
            section=section,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            created_at=datetime.now().isoformat(),
        )

        # Log the proposal
        self._log_evolution({
            "type": "proposal",
            "proposal": {
                "id": proposal.id,
                "section": proposal.section,
                "change_type": proposal.change_type,
                "old_value": proposal.old_value,
                "new_value": proposal.new_value,
                "reason": proposal.reason,
                "evidence": proposal.evidence,
                "confidence": proposal.confidence,
                "created_at": proposal.created_at,
                "status": proposal.status,
            }
        })

        return proposal

    def apply_change(self, proposal: SoulChangeProposal) -> bool:
        """Apply a soul change, log it, notify user.

        Returns True if change was applied successfully.
        """
        if proposal.confidence < 0.6:
            self._log_evolution({
                "type": "rejected",
                "proposal_id": proposal.id,
                "reason": f"Confidence too low: {proposal.confidence}",
            })
            return False

        soul = self.read_soul()
        content = soul.get("raw", "")

        if not content:
            return False

        # Apply the change based on section and type
        try:
            new_content = self._apply_change_to_content(
                content, proposal.section, proposal.change_type,
                proposal.old_value, proposal.new_value
            )

            if new_content == content:
                # No change was made
                return False

            # Write the updated content
            self.soul_path.write_text(new_content)

            # Invalidate cache
            self._cache = None

            # Log the application
            self._log_evolution({
                "type": "applied",
                "proposal_id": proposal.id,
                "timestamp": datetime.now().isoformat(),
            })

            proposal.status = "applied"
            return True

        except Exception as e:
            self._log_evolution({
                "type": "error",
                "proposal_id": proposal.id,
                "error": str(e),
            })
            return False

    def _apply_change_to_content(
        self,
        content: str,
        section: str,
        change_type: str,
        old_value: Optional[str],
        new_value: str,
    ) -> str:
        """Apply a change to the SOUL.md content."""
        # Find the section
        section_headers = {
            "values": "What I Value",
            "capabilities": "What I Can Do",
            "constraints": "What I Won't Do",
            "idea_sources": "Where Ideas Come From",
            "identity": None,  # Special handling
        }

        header = section_headers.get(section)
        if header is None and section != "identity":
            return content

        if section == "identity":
            # Identity is the opening paragraph
            if change_type == "modify" and old_value:
                return content.replace(old_value, new_value)
            return content

        # Find the section
        pattern = rf'(## {re.escape(header)}.*?\n)(.*?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            return content

        section_header = match.group(1)
        section_body = match.group(2)

        if change_type == "add":
            # Add new item to the list
            new_item = f"- {new_value}\n"
            new_body = section_body.rstrip() + "\n" + new_item
        elif change_type == "modify" and old_value:
            new_body = section_body.replace(old_value, new_value)
        elif change_type == "remove" and old_value:
            # Remove the line containing old_value
            lines = section_body.split('\n')
            lines = [l for l in lines if old_value not in l]
            new_body = '\n'.join(lines)
        else:
            return content

        # Replace the section
        new_content = content[:match.start()] + section_header + new_body + content[match.end():]
        return new_content

    def _log_evolution(self, entry: dict):
        """Log an evolution event to soul_evolution.jsonl."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        entry["timestamp"] = datetime.now().isoformat()

        with open(self.evolution_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_evolution_history(self) -> list[dict]:
        """All changes made to SOUL.md over time."""
        if not self.evolution_log.exists():
            return []

        history = []
        with open(self.evolution_log) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        history.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return history

    def get_recent_changes(self, days: int = 7) -> list[dict]:
        """Get changes from the last N days."""
        history = self.get_evolution_history()
        cutoff = datetime.now().timestamp() - (days * 86400)

        recent = []
        for entry in history:
            try:
                ts = datetime.fromisoformat(entry.get("timestamp", "")).timestamp()
                if ts >= cutoff:
                    recent.append(entry)
            except (ValueError, TypeError):
                continue

        return recent

    def count_changes_this_week(self) -> int:
        """Count applied changes in the last 7 days."""
        recent = self.get_recent_changes(days=7)
        return sum(1 for e in recent if e.get("type") == "applied")
