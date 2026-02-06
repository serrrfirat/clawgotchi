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
    return TIMESTAMP_PATTERN.sub('TIMESTAMP', line.strip())

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
    
    added = [line for line in lines2 if line not in lines1]
    removed = [line for line in lines1 if line not in lines2]
    
    # For changed, we look for partial matches
    changed = []
    for line2 in lines2:
        if line2 in added:
            continue
        for line1 in lines1:
            if line1 in removed:
                continue
            # Check if lines are similar (share significant content)
            if line1 != line2 and (line1 in line2 or line2 in line1 or 
                                   len(set(line1.split()) & set(line2.split())) > 3):
                if line2 not in changed:
                    changed.append(line2)
    
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
