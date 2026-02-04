"""
Memory Decay System for Clawgotchi.

Provides intelligent memory retention:
- Track when memories are accessed
- Calculate freshness scores (recency + frequency)
- Archive unused memories
- Compress failed approaches to lessons
- "Forgetting is a feature" - memories fade when unused

Inspired by happy_milvus: "Forgetting is a feature, not a bug."
"""

import os
import re
import json
from datetime import datetime, timedelta
import shutil

# Configuration
DEFAULT_DECAY_DAYS = 90  # Days before memory is considered "stale"
DEFAULT_ARCHIVE_DAYS = 180  # Days before stale memories are archived
ACCESS_LOG_FILE = "memory_access_log.json"
ARCHIVE_DIR = "memory_archive"


class MemoryAccessTracker:
    """Track when memories are accessed for decay calculations."""

    def __init__(self, memory_dir=None):
        """Initialize the tracker."""
        if memory_dir is None:
            from config import MEMORY_DIR
            self.memory_dir = str(MEMORY_DIR)
        else:
            self.memory_dir = memory_dir

        self.access_log_path = os.path.join(self.memory_dir, ACCESS_LOG_FILE)
        self.archive_dir = os.path.join(self.memory_dir, ARCHIVE_DIR)

        # Ensure directories exist
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

        # Load existing access log
        self.access_log = self._load_access_log()

    def _load_access_log(self):
        """Load the access log from disk."""
        if os.path.exists(self.access_log_path):
            try:
                with open(self.access_log_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_access_log(self):
        """Save the access log to disk."""
        with open(self.access_log_path, 'w') as f:
            json.dump(self.access_log, f, indent=2)

    def record_access(self, memory_file, source="auto"):
        """
        Record that a memory was accessed.

        Args:
            memory_file: Name of the memory file accessed
            source: Source of the access (e.g., "search", "curation", "auto")
        """
        if memory_file not in self.access_log:
            self.access_log[memory_file] = {
                "access_count": 0,
                "last_access": None,
                "sources": {},
                "created": datetime.now().isoformat()
            }

        timestamp = datetime.now().isoformat()
        self.access_log[memory_file]["last_access"] = timestamp
        self.access_log[memory_file]["access_count"] += 1

        # Track source
        if source not in self.access_log[memory_file]["sources"]:
            self.access_log[memory_file]["sources"][source] = []
        self.access_log[memory_file]["sources"][source].append(timestamp)

        self._save_access_log()

    def get_access_info(self, memory_file):
        """Get access information for a memory file."""
        return self.access_log.get(memory_file, {
            "access_count": 0,
            "last_access": None,
            "sources": {},
            "created": None
        })

    def get_stale_memories(self, days=90):
        """Get memories that haven't been accessed in N days."""
        stale = []
        cutoff = datetime.now() - timedelta(days=days)

        for memory_file, info in self.access_log.items():
            last_access = info.get("last_access")
            if last_access:
                access_date = datetime.fromisoformat(last_access)
                if access_date < cutoff:
                    stale.append({
                        "file": memory_file,
                        "last_access": last_access,
                        "days_ago": (datetime.now() - access_date).days,
                        "access_count": info.get("access_count", 0)
                    })

        # Sort by oldest first
        stale.sort(key=lambda x: x["last_access"] or "")
        return stale

    def get_frequently_accessed(self, min_count=5):
        """Get memories accessed more than N times."""
        frequent = []

        for memory_file, info in self.access_log.items():
            if info.get("access_count", 0) >= min_count:
                frequent.append({
                    "file": memory_file,
                    "access_count": info["access_count"],
                    "last_access": info.get("last_access"),
                    "freshness_score": self._calculate_freshness(info)
                })

        # Sort by freshness
        frequent.sort(key=lambda x: x["freshness_score"], reverse=True)
        return frequent

    def _calculate_freshness(self, access_info):
        """
        Calculate a freshness score for a memory.

        Score = recency_bonus + frequency_bonus
        - Recency: up to 50 points (more recent = higher)
        - Frequency: up to 50 points (more accesses = higher)
        """
        score = 0

        # Recency component (0-50)
        last_access = access_info.get("last_access")
        if last_access:
            days_ago = (datetime.now() - datetime.fromisoformat(last_access)).days
            # Decay: 50 points if accessed today, 0 if older than 30 days
            recency_score = max(0, 50 - (days_ago * 1.5))
        else:
            recency_score = 0

        # Frequency component (0-50)
        access_count = access_info.get("access_count", 0)
        # Cap at ~30 accesses for max score
        frequency_score = min(50, access_count * 5)

        return round(recency_score + frequency_score, 2)


class MemoryDecayEngine:
    """Apply decay policies to memories."""

    def __init__(self, memory_dir=None):
        """Initialize the decay engine."""
        if memory_dir is None:
            from config import MEMORY_DIR
            self.memory_dir = str(MEMORY_DIR)
        else:
            self.memory_dir = memory_dir

        self.tracker = MemoryAccessTracker(self.memory_dir)
        self.archive_dir = os.path.join(self.memory_dir, ARCHIVE_DIR)
        self.compressed_dir = os.path.join(self.archive_dir, "compressed")

        # Ensure directories exist
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.compressed_dir, exist_ok=True)

    def archive_stale_memories(self, stale_days=90, dry_run=True):
        """
        Archive memories that haven't been accessed in N days.

        Args:
            stale_days: Days before a memory is considered stale
            dry_run: If True, don't actually archive

        Returns:
            List of archived memories
        """
        stale = self.tracker.get_stale_memories(stale_days)
        archived = []

        for item in stale:
            memory_file = item["file"]
            source_path = os.path.join(self.memory_dir, memory_file)

            if not os.path.exists(source_path):
                continue

            if dry_run:
                archived.append({
                    "file": memory_file,
                    "action": "would_archive",
                    "last_access": item["last_access"]
                })
            else:
                # Move to archive
                dest_path = os.path.join(self.archive_dir, memory_file)
                shutil.move(source_path, dest_path)
                archived.append({
                    "file": memory_file,
                    "action": "archived",
                    "last_access": item["last_access"],
                    "archive_path": dest_path
                })

        return archived

    def compress_negative_outcomes(self, dry_run=True):
        """
        Compress memories of failed approaches to just the lesson.

        Heuristic: Look for patterns like "failed", "didn't work", "error"
        in memory content and create a compressed "lesson only" version.

        Args:
            dry_run: If True, don't actually compress

        Returns:
            List of compressed memories
        """
        compressed = []
        negative_patterns = [
            r"failed", r"didn't work", r"does not work",
            r"error", r"crash", r"broke", r"wrong approach",
            r"mistake", r"reverted", r"rolled back"
        ]

        # Check daily logs for negative outcomes
        today = datetime.now()
        for i in range(180):  # Check last 6 months
            date = today - timedelta(days=i)
            log_file = f"{date.strftime('%Y-%m-%d')}.md"
            source_path = os.path.join(self.memory_dir, log_file)

            if not os.path.exists(source_path):
                continue

            with open(source_path, 'r') as f:
                content = f.read()

            # Check for negative patterns
            has_negative = any(re.search(p, content, re.IGNORECASE) for p in negative_patterns)

            if has_negative:
                # Extract lessons/insights from the log
                lessons = self._extract_lessons(content)

                if lessons:
                    compressed_file = f"lessons_{log_file}"
                    dest_path = os.path.join(self.compressed_dir, compressed_file)

                    if dry_run:
                        compressed.append({
                            "file": log_file,
                            "action": "would_compress",
                            "lessons": lessons[:3],  # Limit to 3 lessons
                            "dest": dest_path
                        })
                    else:
                        # Create compressed lesson file
                        compressed_content = f"""---
title: Lessons from {log_file}
description: Compressed negative outcomes to lessons learned
compressed: true
original_date: {date.strftime('%Y-%m-%d')}
---

# Lessons Learned

{chr(10).join(f"- {lesson}" for lesson in lessons)}
"""
                        with open(dest_path, 'w') as f:
                            f.write(compressed_content)

                        compressed.append({
                            "file": log_file,
                            "action": "compressed",
                            "lessons": lessons[:3],
                            "dest": dest_path
                        })

        return compressed

    def _extract_lessons(self, content):
        """Extract lesson/insight lines from content."""
        lessons = []

        # Look for lines starting with lesson indicators
        lesson_patterns = [
            r"^[-*]\s*(Lesson|Key|Learned|Remember|Insight):\s*(.+)",
            r"^[-*]\s*(Don't|Don't|Never|Avoid):\s*(.+)",
            r"^\d+\.\s*(Lesson|Key|Learned):\s*(.+)",
        ]

        lines = content.split('\n')
        for line in lines:
            for pattern in lesson_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    lesson = match.group(match.lastindex).strip()
                    if lesson and len(lesson) > 3:
                        lessons.append(lesson)
                    break

        # If no explicit lessons, try to infer from context
        if not lessons:
            # Look for the last paragraph as a summary
            paragraphs = content.split('\n\n')
            for para in reversed(paragraphs):
                para = para.strip()
                if len(para) > 20 and len(para) < 200:
                    # Clean up and use as lesson
                    lessons.append(para.replace('\n', ' ')[:200])
                    break

        return lessons

    def get_decay_report(self, days=90):
        """Generate a comprehensive decay report."""
        stale = self.tracker.get_stale_memories(days)
        frequent = self.tracker.get_frequently_accessed(min_count=3)

        # Memory files on disk
        memory_files = [f for f in os.listdir(self.memory_dir)
                       if f.endswith('.md') and f not in [ACCESS_LOG_FILE]]

        # Unaccessed memories (in log but never accessed)
        logged = set(self.tracker.access_log.keys())
        unaccessed = [f for f in memory_files if f not in logged]

        return {
            "stale_count": len(stale),
            "frequent_count": len(frequent),
            "unaccessed_count": len(unaccessed),
            "stale_memories": stale[:10],  # Top 10
            "frequent_memories": frequent[:10],  # Top 10
            "unaccessed": unaccessed[:10],  # Top 10
            "total_memory_files": len(memory_files),
            "archive_count": len(os.listdir(self.archive_dir)) if os.path.exists(self.archive_dir) else 0
        }

    def cleanup_unaccessed(self, dry_run=True):
        """Clean up memories that were never accessed."""
        memory_files = set(f for f in os.listdir(self.memory_dir)
                          if f.endswith('.md') and f != ACCESS_LOG_FILE)
        logged = set(self.tracker.access_log.keys())
        unaccessed = memory_files - logged

        cleaned = []
        for mem_file in unaccessed:
            # Skip important files
            if mem_file in ["MEMORY.md", "WORKING.md"]:
                continue

            if dry_run:
                cleaned.append({
                    "file": mem_file,
                    "action": "would_clean"
                })
            else:
                # Move to archive instead of delete
                dest = os.path.join(self.archive_dir, mem_file)
                shutil.move(os.path.join(self.memory_dir, mem_file), dest)
                cleaned.append({
                    "file": mem_file,
                    "action": "archived",
                    "dest": dest
                })

        return cleaned


# CLI interface
def main():
    """CLI entry point for memory decay."""
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(
        description="Clawgotchi Memory Decay System"
    )
    parser.add_argument(
        'command',
        choices=['report', 'archive', 'compress', 'cleanup', 'track'],
        help='Command to run'
    )
    parser.add_argument(
        '--days', type=int, default=90,
        help='Days threshold for stale memories (default: 90)'
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=True,
        help='Show what would happen without making changes'
    )
    parser.add_argument(
        '--execute', action='store_true',
        help='Actually execute the changes (default is dry-run)'
    )

    args = parser.parse_args()

    engine = MemoryDecayEngine()
    tracker = MemoryAccessTracker()

    if args.command == 'report':
        report = engine.get_decay_report(args.days)

        print("📊 Memory Decay Report")
        print("=" * 50)
        print(f"Total memory files: {report['total_memory_files']}")
        print(f"Stale memories (> {args.days} days): {report['stale_count']}")
        print(f"Frequently accessed (3+): {report['frequent_count']}")
        print(f"Never accessed: {report['unaccessed_count']}")
        print(f"Archived memories: {report['archive_count']}")
        print()

        if report['stale_memories']:
            print(f"🔸 Top Stale Memories:")
            for m in report['stale_memories'][:5]:
                print(f"  • {m['file']}: {m['days_ago']} days ago, {m['access_count']} accesses")

        if report['frequent_memories']:
            print(f"\n🔹 Most Fresh Memories:")
            for m in report['frequent_memories'][:5]:
                print(f"  • {m['file']}: score {m['freshness_score']}, {m['access_count']} accesses")

    elif args.command == 'archive':
        print(f"📦 Archiving memories not accessed in {args.days} days...")
        if args.execute:
            archived = engine.archive_stale_memories(args.days, dry_run=False)
        else:
            archived = engine.archive_stale_memories(args.days, dry_run=True)
            print("(dry-run mode - use --execute to actually archive)")

        print(f"Found {len(archived)} stale memories:")
        for m in archived:
            print(f"  • {m['file']}: {m['action']}")

    elif args.command == 'compress':
        print("🗜️  Compressing negative outcomes to lessons...")
        if args.execute:
            compressed = engine.compress_negative_outcomes(dry_run=False)
        else:
            compressed = engine.compress_negative_outcomes(dry_run=True)
            print("(dry-run mode - use --execute to actually compress)")

        print(f"Compressed {len(compressed)} memories:")
        for m in compressed:
            print(f"  • {m['file']}: {m['action']}")

    elif args.command == 'cleanup':
        print("🧹 Cleaning up never-accessed memories...")
        if args.execute:
            cleaned = engine.cleanup_unaccessed(dry_run=False)
        else:
            cleaned = engine.cleanup_unaccessed(dry_run=True)
            print("(dry-run mode - use --execute to actually clean)")

        print(f"Found {len(cleaned)} unaccessed memories:")
        for m in cleaned:
            print(f"  • {m['file']}: {m['action']}")

    elif args.command == 'track':
        # Track access to a memory file
        if len(os.sys.argv) < 3:
            print("Usage: clawgotchi memory_decay track <filename>")
        else:
            filename = os.sys.argv[2]
            tracker.record_access(filename, source="cli")
            print(f"✓ Recorded access to {filename}")


if __name__ == '__main__':
    main()
