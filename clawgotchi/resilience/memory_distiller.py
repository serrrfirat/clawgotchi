"""
Memory Distiller - Compress daily memories and distill insights to long-term memory.

Session Memory (raw) → Daily Memory (memory/YYYY-MM-DD.md)
    ↓ distill()
Long-term Memory (MEMORY.md)
    ↓ vectorize()
Semantic Index (for retrieval)
"""

import os
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class MemoryItem:
    """A single memory entry to be distilled."""
    content: str
    timestamp: datetime
    source: str = "unknown"
    importance: float = 0.5  # 0.0 to 1.0
    tags: list[str] = field(default_factory=list)


@dataclass
class DistilledMemory:
    """A distilled memory ready for long-term storage."""
    content: str
    original_items: list[str]  # IDs or timestamps
    distilled_at: datetime
    categories: list[str]
    action_items: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)


def compress_session(session_log: str, max_chars: int = 5000) -> dict:
    """
    Compress a raw session log into structured memory.
    
    Args:
        session_log: Raw session log text
        max_chars: Maximum characters for summary
        
    Returns:
        dict with decisions, actions, summary, timestamp
    """
    decisions = extract_decisions(session_log)
    actions = extract_actions(session_log)
    summary = generate_summary(session_log, max_chars)
    
    return {
        "decisions": decisions,
        "actions": actions,
        "summary": summary,
        "timestamp": datetime.now().isoformat()
    }


def extract_decisions(text: str) -> list[str]:
    """Extract decision points from text."""
    patterns = [
        r"(?:decided|decision|chose|choice|selected|went with)\s*:?\s*(.+?)(?:\.|$)",
        r"(?:I|we|the system)\s+(?:will|shall|must|should)\s+(.+?)(?:\.|$)",
        r"(?:committed|agreed)\s+to\s+(.+?)(?:\.|$)",
    ]
    
    decisions = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        decisions.extend([m.strip() for m in matches if m.strip()])
    
    # Deduplicate and clean
    seen = set()
    unique = []
    for d in decisions:
        d_clean = d.strip().rstrip('.')
        if d_clean.lower() not in seen and len(d_clean) > 5:
            seen.add(d_clean.lower())
            unique.append(d_clean)
    
    return unique


def extract_actions(text: str) -> list[str]:
    """Extract action items from text."""
    patterns = [
        r"(?:action|todo|task|next step)\s*:?\s*(.+?)(?:\.|$)",
        r"(?:will|going to|plan to)\s+(.+?)(?:\.|$)",
        r"(?:need to|have to|must)\s+(.+?)(?:\.|$)",
    ]
    
    actions = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        actions.extend([m.strip() for m in matches if m.strip()])
    
    # Deduplicate
    seen = set()
    unique = []
    for a in actions:
        a_clean = a.strip().rstrip('.')
        if a_clean.lower() not in seen and len(a_clean) > 5:
            seen.add(a_clean.lower())
            unique.append(a_clean)
    
    return unique


def generate_summary(text: str, max_chars: int = 5000) -> str:
    """Generate a concise summary of the text."""
    # Simple extraction-based summary (could be enhanced with LLM)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]
    
    # Score sentences by keyword presence
    keywords = {'built', 'created', 'shipped', 'tested', 'fixed', 'learned', 'decided', 'completed', 'deployed'}
    scored = []
    for s in sentences:
        words = set(s.lower().split())
        score = len(words & keywords)
        scored.append((score, s))
    
    # Sort by score and take top sentences
    scored.sort(reverse=True)
    summary_parts = []
    current_len = 0
    
    for score, s in scored:
        if current_len + len(s) + 2 > max_chars:
            break
        summary_parts.append(s)
        current_len += len(s) + 2
    
    summary_parts.sort(key=lambda x: text.find(x))  # Restore original order
    summary = ' '.join(summary_parts)
    
    return summary[:max_chars] if summary else text[:max_chars]


def distill_daily_memory(
    daily_md_path: str,
    longterm_md_path: str = "MEMORY.md",
    lookback_days: int = 7
) -> dict:
    """
    Distill daily memories into long-term memory.
    
    Args:
        daily_md_path: Path to daily memory directory or file
        longterm_md_path: Path to long-term memory file
        lookback_days: How many days back to consider for distillation
        
    Returns:
        dict with summary of what was distilled
    """
    today = datetime.now()
    cutoff = today - timedelta(days=lookback_days)
    
    # Collect daily memory files
    daily_files = []
    daily_path = Path(daily_md_path)
    
    if daily_path.is_file() and daily_path.suffix == '.md':
        daily_files.append(daily_path)
    elif daily_path.is_dir():
        for f in daily_path.glob("*.md"):
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                if file_date >= cutoff:
                    daily_files.append(f)
            except ValueError:
                continue  # Skip non-date files
    
    # Extract content from daily files
    all_items = []
    for f in daily_files:
        try:
            content = f.read_text()
            date_str = f.stem
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                file_date = today
            
            # Extract memories using regex
            items = extract_memories_from_content(content, file_date, str(f))
            all_items.extend(items)
        except Exception:
            continue
    
    # Distill insights
    distilled = distill_memories(all_items)
    
    # Merge into long-term memory
    updated = merge_into_longterm(distilled, longterm_md_path)
    
    return {
        "files_processed": len(daily_files),
        "items_extracted": len(all_items),
        "memories_distilled": len(distilled),
        "items_added_to_longterm": updated.get("added", 0),
        "timestamp": today.isoformat()
    }


def extract_memories_from_content(content: str, timestamp: datetime, source: str) -> list[MemoryItem]:
    """Extract individual memory items from content."""
    items = []
    
    # Split by common separators
    blocks = re.split(r'\n## |\n### |\n- ', content)
    
    for block in blocks:
        block = block.strip()
        if not block or len(block) < 10:
            continue
        
        # Determine importance based on keywords
        importance = 0.5
        lower = block.lower()
        if any(w in lower for w in ['built', 'created', 'shipped', 'deployed']):
            importance = 0.9
        elif any(w in lower for w in ['learned', 'discovered', 'realized']):
            importance = 0.8
        elif any(w in lower for w in ['tested', 'verified', 'checked']):
            importance = 0.7
        elif any(w in lower for w in ['planning', 'considering', 'thinking']):
            importance = 0.4
        
        items.append(MemoryItem(
            content=block[:500],  # Truncate long blocks
            timestamp=timestamp,
            source=source,
            importance=importance
        ))
    
    return items


def distill_memories(items: list[MemoryItem]) -> list[DistilledMemory]:
    """Distill multiple memory items into consolidated memories."""
    if not items:
        return []
    
    # Group by similarity (simple keyword-based clustering)
    clusters = {}
    for item in items:
        # Simple clustering by first significant word
        words = item.content.lower().split()
        if not words:
            continue
        key = words[0][:10] if len(words[0]) > 3 else "general"
        
        if key not in clusters:
            clusters[key] = []
        clusters[key].append(item)
    
    # Create distilled memories from clusters
    distilled = []
    for key, cluster_items in clusters.items():
        # Merge cluster items
        combined_content = " | ".join(
            item.content[:100] for item in sorted(cluster_items, key=lambda x: -x.importance)[:5]
        )
        
        decisions = []
        actions = []
        
        for item in cluster_items:
            if 'decid' in item.content.lower() or 'chose' in item.content.lower():
                decisions.append(item.content)
            if 'will' in item.content.lower() or 'todo' in item.content.lower() or 'action' in item.content.lower():
                actions.append(item.content)
        
        distilled.append(DistilledMemory(
            content=combined_content[:1000],
            original_items=[item.source for item in cluster_items],
            distilled_at=datetime.now(),
            categories=[key],
            decisions=decisions[:3],
            action_items=actions[:3]
        ))
    
    return distilled


def merge_into_longterm(distilled: list[DistilledMemory], longterm_path: str) -> dict:
    """Merge distilled memories into the long-term memory file."""
    longterm_file = Path(longterm_path)
    
    existing_content = ""
    if longterm_file.exists():
        existing_content = longterm_file.read_text()
    
    # Check for duplicates
    existing_memories = set()
    for line in existing_content.split('\n'):
        # Match lines like "- **2024-01-15**: content" or "- content"
        match = re.search(r"[-*:]\s*\**\d{4}-\d{2}-\d{2}\**\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            # Has date prefix, extract content after date
            extracted = match.group(1).strip().lower()
        else:
            # No date prefix, extract from line
            match = re.search(r"[-*:] (.+)$", line)
            if match:
                extracted = match.group(1).strip().lower()
                # Remove markdown bold
                extracted = re.sub(r'\*\*', '', extracted).strip()
            else:
                continue
        
        if len(extracted) >= 10:
            existing_memories.add(extracted[:100])
    
    new_entries = []
    for mem in distilled:
        mem_preview = mem.content[:100].lower()
        if mem_preview not in existing_memories:
            new_entries.append(f"- **{mem.distilled_at.strftime('%Y-%m-%d')}**: {mem.content}")
            existing_memories.add(mem_preview)
    
    # Append new entries
    if new_entries:
        new_section = f"\n## Distilled Memories ({datetime.now().strftime('%B %Y')})\n"
        new_section += "\n".join(new_entries)
        new_section += "\n"
        
        updated_content = existing_content + new_section
        longterm_file.write_text(updated_content)
        
        return {"added": len(new_entries), "path": longterm_path}
    
    return {"added": 0, "path": longterm_path}


def is_worth_distilling(content: str, min_importance: float = 0.6) -> bool:
    """
    Quick check if content is worth distilling.
    
    Args:
        content: Text to check
        min_importance: Minimum importance threshold
        
    Returns:
        True if worth distilling
    """
    # Count important markers
    markers = {
        'decision': ['decided', 'chose', 'committed', 'agreed'],
        'action': ['will', 'todo', 'action', 'next'],
        'learning': ['learned', 'discovered', 'realized', 'found'],
        'completion': ['built', 'created', 'shipped', 'completed', 'deployed']
    }
    
    score = 0
    content_lower = content.lower()
    
    for category, keywords in markers.items():
        for kw in keywords:
            if kw in content_lower:
                if category == 'completion':
                    score += 3
                elif category == 'learning':
                    score += 2
                else:
                    score += 1
    
    # Max score is 3 (one completion keyword), min importance 0.6 means need at least 1.8
    # Let's say 2+ score means worth distilling
    return score >= 2


def build_memory_index(memory_dir: str = "memory") -> dict:
    """Build a simple semantic index of all memories."""
    index = {
        "by_date": {},
        "by_category": {},
        "by_tag": {},
        "keywords": {}
    }
    
    memory_path = Path(memory_dir)
    if not memory_path.exists():
        return index
    
    for f in memory_path.glob("*.md"):
        try:
            content = f.read_text()
            date_key = f.stem  # YYYY-MM-DD
            
            # Index by date
            index["by_date"][date_key] = {
                "path": str(f),
                "word_count": len(content.split()),
                "line_count": len(content.split('\n'))
            }
            
            # Extract keywords
            words = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())
            word_freq = {}
            for w in words:
                if w not in ['this', 'that', 'with', 'from', 'have', 'been', 'were', 'they']:
                    word_freq[w] = word_freq.get(w, 0) + 1
            
            # Top keywords
            sorted_words = sorted(word_freq.items(), key=lambda x: -x[1])[:10]
            index["keywords"][date_key] = dict(sorted_words)
            
        except Exception:
            continue
    
    return index


def check_weekly_review(memory_dir: str = "memory") -> dict:
    """
    Check if a weekly memory review is needed.
    
    Returns:
        dict with review status and suggestions
    """
    memory_path = Path(memory_dir)
    if not memory_path.exists():
        return {"needed": False, "reason": "No memory directory"}
    
    today = datetime.now()
    weekly_review_day = today.weekday()  # Monday = 0
    
    # Check for unreviewed daily memories
    reviewed_files = set()
    if memory_path.exists():
        review_log = memory_path / ".review_log.json"
        if review_log.exists():
            try:
                reviewed_files = set(json.loads(review_log.read_text()).get("reviewed", []))
            except Exception:
                reviewed_files = set()
    
    unreviewed = []
    for f in memory_path.glob("*.md"):
        if f.stem not in reviewed_files and f.stem != "MEMORY":
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                days_ago = (today - file_date).days
                if 1 <= days_ago <= 7:  # Last week's entries
                    unreviewed.append({
                        "file": str(f),
                        "date": f.stem,
                        "days_ago": days_ago
                    })
            except ValueError:
                continue
    
    return {
        "needed": len(unreviewed) > 0,
        "count": len(unreviewed),
        "files": unreviewed[:5],  # First 5
        "suggestion": f"Review {len(unreviewed)} unreviewed daily memories" if unreviewed else "All caught up!"
    }


def quick_distill(session_log: str) -> str:
    """
    Quick one-line distillation of a session.
    
    Args:
        session_log: Raw session text
        
    Returns:
        One-line summary suitable for MEMORY.md
    """
    decisions = extract_decisions(session_log)
    actions = extract_actions(session_log)[:2]
    
    summary = []
    if decisions:
        summary.append(f"Decided: {decisions[0]}")
    if actions:
        summary.append(f"Actions: {', '.join(actions[:2])}")
    
    return " | ".join(summary) if summary else generate_summary(session_log, 200)
