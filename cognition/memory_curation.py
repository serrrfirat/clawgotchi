"""
Memory Curation System for Clawgotchi.

Provides tools to:
- Extract insights from daily logs
- Curate long-term memories
- Search and manage memories
- Detect and protect sensitive data (API keys, passwords, tokens)

Inspired by DriftSteven's "Memory Layers: Files Beat Brain Every Time"
"""

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


# Patterns that indicate sensitive data
SENSITIVE_PATTERNS = [
    # Generic API key patterns
    (r'api[_-]?key\s*[:=]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?', 'API Key'),
    (r'secret\s*[:=]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?', 'Secret'),
    (r'token\s*[:=]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?', 'Token'),
    (r'password\s*[:=]\s*["\']?[^"\'\s]{8,}["\']?', 'Password'),
    # Moltbook specific
    (r'moltbook[_-]?sk[_-]?[A-Za-z0-9]{20,}', 'Moltbook API Key'),
    # Generic secret patterns
    (r'["\']?[A-Za-z0-9_=-]{30,}["\']?', 'Potential Secret'),
    # Private key patterns
    (r'-----BEGIN\s+(RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', 'Private Key'),
]


class SensitiveDataDetector:
    """Detect sensitive data in memory files to prevent leaks."""

    def __init__(self):
        """Initialize the detector with patterns."""
        self.patterns = SENSITIVE_PATTERNS

    def scan_file(self, file_path):
        """
        Scan a file for sensitive data patterns.

        Args:
            file_path: Path to file to scan

        Returns:
            List of detected sensitive data matches
        """
        matches = []

        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

                for line_num, line in enumerate(lines, 1):
                    for pattern, pattern_type in self.patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Redact the actual secret value for safety
                            redacted = self._redact_line(line)
                            matches.append({
                                'file': file_path,
                                'line': line_num,
                                'type': pattern_type,
                                'redacted_content': redacted
                            })
        except Exception as e:
            matches.append({
                'file': file_path,
                'line': 0,
                'type': 'Error',
                'redacted_content': f'Error reading file: {e}'
            })

        return matches

    def _redact_line(self, line):
        """Redact sensitive parts of a line while keeping context."""
        redacted = line
        for pattern, _ in self.patterns:
            # Replace matched secrets with [REDACTED]
            redacted = re.sub(
                pattern,
                f'[{_}]',
                redacted,
                flags=re.IGNORECASE
            )
        return redacted.strip()

    def scan_memory_directory(self, memory_dir):
        """
        Scan all memory files in a directory for sensitive data.

        Args:
            memory_dir: Path to memory directory

        Returns:
            List of all detected sensitive data matches
        """
        all_matches = []

        if not os.path.exists(memory_dir):
            return all_matches

        for filename in os.listdir(memory_dir):
            filepath = os.path.join(memory_dir, filename)
            if os.path.isfile(filepath):
                matches = self.scan_file(filepath)
                all_matches.extend(matches)

        return all_matches

    def is_safe_to_promote(self, text):
        """
        Check if text is safe to promote (no sensitive data).

        Args:
            text: Text to check

        Returns:
            Tuple of (is_safe, detected_types)
        """
        detected_types = []
        for pattern, pattern_type in self.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected_types.append(pattern_type)

        return len(detected_types) == 0, detected_types

    def redact_text(self, text):
        """
        Redact all sensitive data from text.

        Args:
            text: Text to redact

        Returns:
            Redacted text
        """
        redacted = text
        for pattern, pattern_type in self.patterns:
            redacted = re.sub(pattern, f'[{pattern_type}]', redacted, flags=re.IGNORECASE)
        return redacted


class MemoryConsistencyChecker:
    """
    Verify consistency of memory files to catch errors and contradictions.

    Checks for:
    - Broken internal links (references to missing files)
    - Contradictory statements (e.g., "X is true" vs "X is false")
    - Orphaned entries (mentions of non-existent concepts)
    """

    # Patterns that indicate a reference to another file/date
    REFERENCE_PATTERN = r'\[?([A-Za-z0-9_\-]+\.md)\]?|\[?(\d{4}-\d{2}-\d{2})\.md\]?'

    # Contradiction patterns (simplified for agents)
    CONTRADICTION_PATTERNS = [
        (r'(\w+) is true', r'\1 is false'),
        (r'(\w+) works', r'\1 does not work'),
        (r'(\w+) is possible', r'\1 is impossible'),
        (r'(\w+) should', r'\1 should not'),
        (r'(\w+) can', r'\1 cannot'),
        (r'(\w+) is safe', r'\1 is not safe'),
        (r'(\w+) is secure', r'\1 is not secure'),
    ]

    def __init__(self, memory_dir=None):
        """Initialize consistency checker with memory directory."""
        if memory_dir is None:
            from config import MEMORY_DIR
            self.memory_dir = str(MEMORY_DIR)
        else:
            self.memory_dir = memory_dir

        # Ensure memory directory exists
        os.makedirs(self.memory_dir, exist_ok=True)

    def _extract_references(self, content):
        """Extract file references from content."""
        references = []
        # Look for date-based references (e.g., [2026-02-04.md] or just 2026-02-04)
        date_refs = re.findall(r'(\d{4}-\d{2}-\d{2})', content)
        for date in date_refs:
            references.append(f"{date}.md")

        # Look for explicit file references
        file_refs = re.findall(r'([A-Za-z0-9_\-]+\.md)', content)
        references.extend(file_refs)

        return list(set(references))

    def _find_contradictions(self, content):
        """Find potential contradictions in content."""
        contradictions = []

        # This is a simplified detection - real contradiction detection
        # would require semantic analysis, but we can catch obvious cases
        # by looking for adjacent opposing statements

        lines = content.split('\n')
        for i in range(len(lines) - 1):
            line1 = lines[i].lower()
            line2 = lines[i + 1].lower()

            # Check for quick backtracks (saying something then immediately contradicting)
            positive_words = ['is true', 'works', 'is possible', 'is safe', 'is secure', 'can', 'should']
            negative_words = ['is false', 'does not work', 'is impossible', 'is not safe', 'is not secure', 'cannot', 'should not']

            for pos in positive_words:
                if pos in line1:
                    for neg in negative_words:
                        # Check if the same subject is mentioned
                        pos_parts = pos.split()
                        neg_parts = neg.split()

                        # Need at least 2 parts for both
                        if len(pos_parts) < 2 or len(neg_parts) < 2:
                            continue

                        subject_match = re.search(r'(\w+) ' + pos_parts[1], line1)
                        if subject_match:
                            subject = subject_match.group(1)
                            neg_keyword = neg_parts[1]
                            if re.search(r'(\w+) ' + neg_keyword, line2) and subject in line2:
                                contradictions.append({
                                    'line': i + 1,
                                    'positive': lines[i].strip(),
                                    'negative': lines[i + 1].strip(),
                                    'subject': subject
                                })

        return contradictions

    def _find_orphaned_entries(self, curated_content):
        """Find entries in curated memory that might be orphaned."""
        # An "orphan" is something mentioned in curated memory
        # but never expanded upon in daily logs

        # This is a heuristic: look for capitalized terms in curated
        # that don't appear in recent logs

        curated_terms = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', curated_content)

        # Filter common words
        common_words = {'Important', 'Key', 'Remember', 'Insight', 'Curated', 'Memory', 'File', 'Agent', 'Test', 'Note'}
        curated_terms = [t for t in curated_terms if t not in common_words and len(t) > 3]

        return list(set(curated_terms))

    def check_all_memories(self):
        """
        Run consistency check on all memory files.

        Returns:
            Dictionary with issues found (broken_links, contradictions, orphans)
        """
        issues = {
            'broken_links': [],
            'contradictions': [],
            'orphans': [],
            'warnings': []
        }

        if not os.path.exists(self.memory_dir):
            issues['warnings'].append(f"Memory directory {self.memory_dir} does not exist")
            return issues

        # Get list of existing files
        existing_files = set(os.listdir(self.memory_dir))

        # Check curated memory specifically
        curated_file = os.path.join(self.memory_dir, "MEMORY.md")
        curated_content = ""
        if os.path.exists(curated_file):
            with open(curated_file, 'r') as f:
                curated_content = f.read()

            # Check for contradictions in curated memory
            contradictions = self._find_contradictions(curated_content)
            if contradictions:
                issues['contradictions'].extend([{
                    'file': 'MEMORY.md',
                    'type': 'possible_backtrack',
                    'description': f'Possible contradiction around "{c["subject"]}"',
                    'line_1': c['positive'],
                    'line_2': c['negative']
                } for c in contradictions])

        # Check each daily log
        for filename in os.listdir(self.memory_dir):
            if not filename.endswith('.md'):
                continue

            filepath = os.path.join(self.memory_dir, filename)
            if not os.path.isfile(filepath):
                continue

            with open(filepath, 'r') as f:
                content = f.read()

            # Check for broken references
            references = self._extract_references(content)
            for ref in references:
                # Only check if it's not the current file
                if ref != filename and ref not in existing_files:
                    issues['broken_links'].append({
                        'file': filename,
                        'broken_reference': ref
                    })

            # Check for contradictions
            contradictions = self._find_contradictions(content)
            if contradictions:
                issues['contradictions'].extend([{
                    'file': filename,
                    'type': 'possible_backtrack',
                    'description': f'Possible contradiction around "{c["subject"]}"',
                    'line_1': c['positive'],
                    'line_2': c['negative']
                } for c in contradictions])

        # Find orphaned entries
        if curated_content:
            potential_orphans = self._find_orphaned_entries(curated_content)
            # These are just "terms to watch" not actual orphans
            # Real orphan detection would need semantic understanding
            if potential_orphans:
                issues['orphans'] = potential_orphans[:10]  # Limit to 10 for display

        return issues

    def print_diagnostic_report(self):
        """Print a formatted diagnostic report."""
        issues = self.check_all_memories()

        print("🩺 Memory Consistency Diagnostic Report")
        print("=" * 50)

        if not issues['broken_links'] and not issues['contradictions'] and not issues['orphans']:
            print("✅ All checks passed! Memory appears consistent.")
            return

        # Broken links
        if issues['broken_links']:
            print(f"\n🔗 Broken Internal Links ({len(issues['broken_links'])} found):")
            for link in issues['broken_links']:
                print(f"  📄 {link['file']} → {link['broken_reference']}")

        # Contradictions
        if issues['contradictions']:
            print(f"\n⚠️  Potential Contradictions ({len(issues['contradictions'])} found):")
            for c in issues['contradictions']:
                print(f"  📄 {c['file']}: {c['description']}")
                print(f"     + {c['line_1'][:60]}...")
                print(f"     - {c['line_2'][:60]}...")

        # Orphans
        if issues['orphans']:
            print(f"\n📌 Terms in Curated Memory Not Seen Recently:")
            for term in issues['orphans'][:5]:
                print(f"  • {term}")

        # Summary
        total = len(issues['broken_links']) + len(issues['contradictions'])
        print(f"\n📊 Total Issues: {total}")

        return issues


class MemoryCuration:
    """Manage memory curation for the agent."""

    def __init__(self, memory_dir=None):
        """Initialize memory curation with a memory directory."""
        if memory_dir is None:
            from config import MEMORY_DIR
            self.memory_dir = str(MEMORY_DIR)
        else:
            self.memory_dir = memory_dir

        # Ensure memory directory exists
        os.makedirs(self.memory_dir, exist_ok=True)

        # Path to curated memory file
        self.curated_memory_file = os.path.join(self.memory_dir, "MEMORY.md")

    def _get_daily_logs(self, days=7):
        """Get list of daily log files from the last N days."""
        logs = []
        today = datetime.now()

        for i in range(days):
            date = today - timedelta(days=i)
            log_file = os.path.join(self.memory_dir, f"{date.strftime('%Y-%m-%d')}.md")
            if os.path.exists(log_file):
                logs.append(log_file)

        return logs

    def extract_insights_from_logs(self, days=7):
        """
        Extract potential insights from daily logs.

        Looks for lines starting with:
        - Important:
        - Key learning:
        - Note:
        - Remember:
        - Insight:
        """
        logs = self._get_daily_logs(days)
        insights = []

        # Patterns that indicate an insight
        insight_patterns = [
            r'^\s*[-*]?\s*(Important|Key learning|Note|Remember|Insight):\s*(.+)',
            r'^\s*##\s+(Important|Learnings|Notes|Insights)',
        ]

        for log_file in logs:
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for line in lines:
                        for pattern in insight_patterns:
                            match = re.search(pattern, line, re.IGNORECASE)
                            if match:
                                # Extract the insight text
                                if len(match.groups()) >= 2:
                                    insight = match.group(2).strip()
                                    if insight and len(insight) > 3:
                                        insights.append({
                                            'text': insight,
                                            'source': os.path.basename(log_file)
                                        })
                                break
            except Exception as e:
                print(f"Error reading {log_file}: {e}")

        return insights

    def promote_insight(self, insight_text, category="General"):
        """
        Promote an insight to long-term curated memory.

        Args:
            insight_text: The insight to add
            category: Category tag for the insight

        Returns:
            Tuple of (success, warning_message)
        """
        # Check for sensitive data before promoting
        detector = SensitiveDataDetector()
        is_safe, detected_types = detector.is_safe_to_promote(insight_text)

        warning_message = None
        if not is_safe:
            warning_message = f"⚠️ Warning: Insight contains potentially sensitive data ({', '.join(detected_types)}). Consider redacting before promoting."
            print(warning_message)

        # Ensure curated memory file exists with frontmatter
        if not os.path.exists(self.curated_memory_file):
            self._create_curated_memory_file()

        # Read current content
        with open(self.curated_memory_file, 'r') as f:
            content = f.read()

        # Add the new insight
        timestamp = datetime.now().strftime('%Y-%m-%d')

        # Redact sensitive data before saving
        redacted_text = detector.redact_text(insight_text)

        new_entry = f"- **{timestamp}** [{category}]: {redacted_text}\n"

        # Find the end of the insights list and insert
        if '# Curated Insights' in content:
            # Split and insert before the list ends (before --- at end)
            parts = content.rsplit('---', 1)
            if len(parts) == 2:
                content = parts[0] + new_entry + '---\n' + parts[1]
            else:
                content += new_entry + '---\n'
        else:
            content += new_entry + '---\n'

        with open(self.curated_memory_file, 'w') as f:
            f.write(content)

        return True, warning_message

    def _create_curated_memory_file(self):
        """Create the curated memory file with proper frontmatter."""
        content = """---
title: Clawgotchi Long-Term Memory
description: Curated insights and learnings across wake cycles
curated_insights:
---

# Curated Insights

"""
        with open(self.curated_memory_file, 'w') as f:
            f.write(content)

    def show_curated_memory(self):
        """Show the curated long-term memory."""
        if not os.path.exists(self.curated_memory_file):
            return "No curated memory yet. Use `promote_insight()` to add insights."

        with open(self.curated_memory_file, 'r') as f:
            return f.read()

    def search_memories(self, query):
        """
        Search through curated memories.

        Args:
            query: Search term

        Returns:
            List of matching memory entries
        """
        if not os.path.exists(self.curated_memory_file):
            return []

        results = []
        with open(self.curated_memory_file, 'r') as f:
            content = f.read()

        lines = content.split('\n')
        for line in lines:
            if query.lower() in line.lower():
                if line.strip() and not line.startswith('---'):
                    results.append(line.strip())

        return results

    def get_memory_stats(self):
        """Get statistics about memory curation."""
        stats = {
            'curated_entries': 0,
            'daily_logs': 0,
            'last_curated': None
        }

        # Count daily logs
        if os.path.exists(self.memory_dir):
            logs = [f for f in os.listdir(self.memory_dir) if f.endswith('.md')]
            stats['daily_logs'] = len(logs)

        # Count curated entries
        if os.path.exists(self.curated_memory_file):
            with open(self.curated_memory_file, 'r') as f:
                content = f.read()
            # Count lines that look like entries (contain dates)
            entries = re.findall(r'\d{4}-\d{2}-\d{2}', content)
            stats['curated_entries'] = len(entries)
            if entries:
                stats['last_curated'] = max(entries)

        return stats


# CLI interface
def main():
    """CLI entry point for memory curation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clawgotchi Memory Curation System"
    )
    parser.add_argument(
        'command',
        choices=['summarize', 'promote', 'show', 'search', 'stats', 'security', 'diagnose'],
        help='Command to run'
    )

    # Parse arguments based on command
    if len(sys.argv) < 2:
        parser.print_help()
        return

    args = parser.parse_args([sys.argv[1]])

    curation = MemoryCuration()

    if args.command == 'summarize':
        # Extract and show insights from recent logs
        insights = curation.extract_insights_from_logs(days=7)
        if insights:
            print("📚 Insights from recent logs:")
            print("-" * 40)
            for i, insight in enumerate(insights, 1):
                print(f"{i}. [{insight['source']}] {insight['text']}")
        else:
            print("No insights found in recent logs.")

    elif args.command == 'promote':
        # Promote an insight
        if len(sys.argv) < 3:
            print("Usage: clawgotchi memory promote \"Your insight here\"")
        else:
            insight = ' '.join(sys.argv[2:])
            curation.promote_insight(insight)
            print(f"✓ Promoted: {insight}")

    elif args.command == 'show':
        # Show curated memory
        print(curation.show_curated_memory())

    elif args.command == 'search':
        # Search memories
        if len(sys.argv) < 3:
            print("Usage: clawgotchi memory search <query>")
        else:
            query = ' '.join(sys.argv[2:])
            results = curation.search_memories(query)
            if results:
                print(f"🔍 Results for '{query}':")
                for r in results:
                    print(f"  {r}")
            else:
                print(f"No results found for '{query}'")

    elif args.command == 'stats':
        # Show memory stats
        stats = curation.get_memory_stats()
        print("📊 Memory Stats:")
        print(f"  Daily logs: {stats['daily_logs']}")
        print(f"  Curated entries: {stats['curated_entries']}")
        print(f"  Last curated: {stats['last_curated'] or 'Never'}")

    elif args.command == 'security':
        # Security audit for memory files
        detector = SensitiveDataDetector()
        matches = detector.scan_memory_directory(curation.memory_dir)

        if matches:
            print("🔒 Security Audit Results:")
            print("=" * 50)
            print(f"⚠️  Found {len(matches)} potential issue(s):\n")

            for m in matches:
                print(f"📄 {os.path.basename(m['file'])} (line {m['line']})")
                print(f"   Type: {m['type']}")
                print(f"   Content: {m['redacted_content'][:100]}")
                print()
        else:
            print("✅ Security Audit: No sensitive data detected in memory files!")

    elif args.command == 'diagnose':
        # Run consistency diagnostics
        from memory_curation import MemoryConsistencyChecker
        checker = MemoryConsistencyChecker(memory_dir=curation.memory_dir)
        checker.print_diagnostic_report()


if __name__ == '__main__':
    main()
