"""
MemorySanitizer - Utility for cleaning and maintaining memory hygiene.

Inspired by Logi_CtxEngineer's Triple-Memory Architecture:
1. Daily Log - today's events (memory/YYYY-MM-dd.md)
2. Structured Memory - long-term preferences (MEMORY.md)
3. Vector Search - semantic retrieval (future)

This module provides:
- Duplicate detection
- Test/corrupted entry removal
- Memory statistics
- Full cleanup workflow
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional


class MemorySanitizer:
    """Utility for cleaning and maintaining memory file hygiene."""
    
    def __init__(self, memory_dir: Optional[str] = None):
        """Initialize MemorySanitizer.
        
        Args:
            memory_dir: Path to memory directory. Defaults to ./memory
        """
        self.memory_dir = Path(memory_dir) if memory_dir else Path("./memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        
    def find_duplicates(self) -> List[str]:
        """Find duplicate entries in MEMORY.md.
        
        Returns:
            List of duplicate entries found.
        """
        if not self.memory_file.exists():
            return []
        
        content = self.memory_file.read_text()
        lines = content.split('\n')
        
        duplicates = []
        seen = set()
        
        for i, line in enumerate(lines):
            # Normalize for comparison (strip whitespace)
            normalized = line.strip()
            if len(normalized) < 10:  # Skip short lines
                continue
                
            if normalized in seen:
                duplicates.append(f"Line {i+1}: {normalized[:50]}...")
            else:
                seen.add(normalized)
        
        return duplicates
    
    def find_test_entries(self) -> List[str]:
        """Find test/corrupted entries in MEMORY.md.
        
        Returns:
            List of test entries found.
        """
        if not self.memory_file.exists():
            return []
        
        content = self.memory_file.read_text()
        test_entries = []
        
        # Patterns for corrupted/test entries
        test_patterns = [
            r'##\s*Test',
            r'I\s+decided\s+to\s+build\s+a\s+feature\s+today',
            r'^-\s*\*Test\*',
            r'Distilled Memories.*Test',
        ]
        
        for i, line in enumerate(content.split('\n')):
            for pattern in test_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    test_entries.append(f"Line {i+1}: {line[:60]}...")
                    break
        
        return test_entries
    
    def clean_content(self, content: str) -> str:
        """Clean corrupted entries from memory content.
        
        Args:
            content: Raw memory content.
            
        Returns:
            Cleaned content with test entries removed.
        """
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip test/corrupted entries
            if re.search(r'##\s*Test', line, re.IGNORECASE):
                continue
            if re.search(r'^-\s*\*Test', line):
                continue
            if re.search(r'Distilled Memories.*Test', line):
                continue
                
            cleaned_lines.append(line)
        
        # Remove excessive blank lines
        result = []
        prev_was_blank = False
        for line in cleaned_lines:
            is_blank = line.strip() == ''
            if is_blank and prev_was_blank:
                continue
            result.append(line)
            prev_was_blank = is_blank
        
        return '\n'.join(result)
    
    def get_stats(self) -> Dict:
        """Get memory file statistics.
        
        Returns:
            Dictionary with memory statistics.
        """
        stats = {
            "total_entries": 0,
            "duplicate_count": 0,
            "test_entry_count": 0,
            "lines": 0,
            "has_memory_file": self.memory_file.exists(),
        }
        
        if not self.memory_file.exists():
            return stats
        
        content = self.memory_file.read_text()
        stats["lines"] = len(content.split('\n'))
        
        # Count entries (lines starting with -)
        entries = [l for l in content.split('\n') if l.strip().startswith('-')]
        stats["total_entries"] = len(entries)
        
        # Count duplicates
        duplicates = self.find_duplicates()
        stats["duplicate_count"] = len(duplicates)
        
        # Count test entries
        test_entries = self.find_test_entries()
        stats["test_entry_count"] = len(test_entries)
        
        return stats
    
    def get_daily_logs(self) -> List[Path]:
        """Get list of daily log files.
        
        Returns:
            List of Path objects for daily log files.
        """
        if not self.memory_dir.exists():
            return []
        
        daily_logs = []
        for f in self.memory_dir.glob("*.md"):
            if f.name != "MEMORY.md" and re.match(r'\d{4}-\d{2}-\d{2}\.md', f.name):
                daily_logs.append(f)
        
        return sorted(daily_logs)
    
    def run_cleanup(self) -> Dict:
        """Run full cleanup process on memory files.
        
        Returns:
            Dictionary with cleanup report.
        """
        report = {
            "entries_removed": 0,
            "duplicates_found": 0,
            "test_entries_found": 0,
            "files_cleaned": [],
            "original_lines": 0,
            "cleaned_lines": 0,
        }
        
        if not self.memory_file.exists():
            return report
        
        # Analyze before cleaning
        duplicates = self.find_duplicates()
        test_entries = self.find_test_entries()
        
        report["duplicates_found"] = len(duplicates)
        report["test_entries_found"] = len(test_entries)
        
        # Read original content
        original_content = self.memory_file.read_text()
        report["original_lines"] = len(original_content.split('\n'))
        
        # Clean content
        cleaned_content = self.clean_content(original_content)
        
        # Calculate entries removed (approximate)
        original_entries = original_content.count('\n')
        cleaned_entries = cleaned_content.count('\n')
        report["entries_removed"] = max(0, original_entries - cleaned_entries)
        report["cleaned_lines"] = len(cleaned_content.split('\n'))
        
        # Write cleaned content
        self.memory_file.write_text(cleaned_content)
        report["files_cleaned"].append(str(self.memory_file))
        
        return report
    
    def backup_memory(self) -> Path:
        """Create a backup of MEMORY.md before cleanup.
        
        Returns:
            Path to backup file.
        """
        if not self.memory_file.exists():
            raise FileNotFoundError("MEMORY.md does not exist")
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.memory_dir / f"MEMORY.md.backup_{timestamp}"
        
        backup_path.write_text(self.memory_file.read_text())
        return backup_path
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore MEMORY.md from a backup file.
        
        Args:
            backup_path: Path to backup file.
            
        Returns:
            True if restore successful, False otherwise.
        """
        if not backup_path.exists():
            return False
        
        self.memory_file.write_text(backup_path.read_text())
        return True


def main():
    """CLI entry point for MemorySanitizer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Sanitizer Utility")
    parser.add_argument("--dir", default="./memory", help="Memory directory path")
    parser.add_argument("--stats", action="store_true", help="show memory statistics")
    parser.add_argument("--duplicates", action="store_true", help="show duplicates")
    parser.add_argument("--test-entries", action="store_true", help="show test entries")
    parser.add_argument("--cleanup", action="store_true", help="run cleanup")
    parser.add_argument("--backup", action="store_true", create backup before cleanup")
    
    args = parser.parse_args()
    
    sanitizer = MemorySanitizer(args.dir)
    
    if args.stats:
        stats = sanitizer.get_stats()
        print("\nMemory Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    if args.duplicates:
        duplicates = sanitizer.find_duplicates()
        print(f"\nFound {len(duplicates)} duplicate(s):")
        for d in duplicates:
            print(f"  {d}")
    
    if args.test_entries:
        test_entries = sanitizer.find_test_entries()
        print(f"\nFound {len(test_entries)} test entry(ies):")
        for t in test_entries:
            print(f"  {t}")
    
    if args.cleanup:
        if args.backup:
            backup = sanitizer.backup_memory()
            print(f"Backup created: {backup}")
        
        report = sanitizer.run_cleanup()
        print("\nCleanup Report:")
        for key, value in report.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
