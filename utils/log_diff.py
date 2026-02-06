"""
Log diffing utility for Clawgotchi heartbeats.
Makes heartbeat logs deterministic and diffable by ignoring timestamps.
"""
import json
import re
from typing import Dict, List, Tuple

TIMESTAMP_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

def normalize_log_line(line: str) -> str:
    """Remove timestamps from a log line to make it deterministic."""
    return TIMESTAMP_PATTERN.sub('', line).strip()

def compute_log_diff(log1: str, log2: str) -> Dict[str, List[str]]:
    """
    Compute the diff between two logs.
    
    Args:
        log1: First log (string or multiline)
        log2: Second log (string or multiline)
    
    Returns:
        Dict with 'added', 'removed', and 'changed' keys containing lists of lines.
    """
    lines1 = [normalize_log_line(line) for line in log1.strip().split('\n') if line.strip()]
    lines2 = [normalize_log_line(line) for line in log2.strip().split('\n') if line.strip()]
    
    added = []
    removed = []
    changed = []
    
    # Track which lines are exact matches
    matched_lines2 = set()
    matched_lines1 = set()
    
    # First pass: find exact matches
    for i, l2 in enumerate(lines2):
        if l2 in lines1:
            matched_lines2.add(i)
    
    for i, l1 in enumerate(lines1):
        if l1 in lines2:
            matched_lines1.add(i)
    
    # Second pass: categorize non-matches
    for i, l2 in enumerate(lines2):
        if i in matched_lines2:
            continue
        is_changed = False
        for j, l1 in enumerate(lines1):
            if j in matched_lines1:
                continue
            # Check if lines are similar (share significant content)
            if l1 != l2 and (l1 in l2 or l2 in l1 or 
                             len(set(l1.split()) & set(l2.split())) > 3):
                changed.append(l2)
                is_changed = True
                break
        if not is_changed:
            added.append(l2)
    
    for j, l1 in enumerate(lines1):
        if j in matched_lines1:
            continue
        # Check if this line was already accounted for as a change
        if l1 not in [c.replace('1 failed', '0 failed').replace('0 failed', '1 failed') for c in changed]:
            removed.append(l1)
    
    return {
        'added': added,
        'removed': removed,
        'changed': changed
    }

if __name__ == '__main__':
    # Quick demo
    log_a = """2026-02-06T04:00:00 Heartbeat started
Action: Running tests
Result: 5 passed
Health: 95/100"""
    
    log_b = """2026-02-06T04:30:00 Heartbeat started
Action: Running tests
Result: 6 passed
Health: 96/100"""
    
    diff = compute_log_diff(log_a, log_b)
    print(json.dumps(diff, indent=2))
