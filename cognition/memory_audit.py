"""
Memory Audit Utility

Inspired by @Clawd_Rui's Recursive Audit pattern.
Reads daily memory files, distills patterns, and updates MEMORY.md with insights.
"""

import re
from datetime import date, timedelta
from collections import Counter


def get_today_date():
    """Get today's date string in YYYY-MM-DD format"""
    return date.today().strftime('%Y-%m-%d')


def get_yesterday_date():
    """Get yesterday's date string"""
    return (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')


def read_memory_file(filepath: str) -> str:
    """Read a memory file, return empty string if doesn't exist"""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return ''
    except Exception:
        return ''


def read_file(filepath: str) -> str:
    """General file read with error handling"""
    return read_memory_file(filepath)


def write_file(filepath: str, content: str) -> bool:
    """Write content to file, return success status"""
    try:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False


def parse_wake_cycles(content: str) -> list[dict]:
    """Parse wake cycle entries from memory content"""
    cycles = []
    
    # Match wake cycle headers with various timestamp formats
    # ## Wake Cycle #575 (2026-02-04 21:38)
    pattern = r'## Wake Cycle #(\d+).*?\n(.*?)(?=## Wake Cycle #|\Z)'
    
    matches = re.findall(pattern, content, re.DOTALL)
    
    for cycle_num, body in matches:
        cycle_info = {'cycle': f'#{cycle_num}'}
        
        # Extract action
        action_match = re.search(r'- Action:\s*(.+?)(?:\n|$)', body)
        if action_match:
            cycle_info['action'] = action_match.group(1).strip()
        
        # Extract result
        result_match = re.search(r'- Result:\s*(.+?)(?:\n|$)', body)
        if result_match:
            cycle_info['result'] = result_match.group(1).strip()
        
        # Extract health
        health_match = re.search(r'- Health:\s*(\d+/\d+)', body)
        if health_match:
            cycle_info['health'] = health_match.group(1)
        
        cycles.append(cycle_info)
    
    return cycles


def extract_key_metrics(content: str) -> dict:
    """Extract key metrics from memory content"""
    metrics = {}
    
    # Match patterns with optional leading bullet points
    patterns = [
        (r'\((\d+)/(\d+)\)', 'tests'),  # Match (10/10) pattern
        (r'-?\s*Git[:\s]+(\d+)\s*commits?', 'commits'),
        (r'-?\s*Total[:\s]+(\d+)\s*new\s*tests?', 'total_tests'),
        (r'-?\s*Health[:\s]+(\d+/\d+)', 'health'),
        (r'(\d+)\s*features?', 'features'),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            if key == 'tests' and len(match.groups()) >= 2:
                metrics[key] = f"{match.group(2)}/{match.group(1)}"  # correct order: passed/total
            else:
                metrics[key] = match.group(1)
    
    return metrics


def detect_patterns(content: str) -> dict:
    """Detect repeating patterns in memory content"""
    patterns = {}
    
    # Find recurring actions
    action_pattern = r'- Action:\s*(.+?)(?:\n|$)'
    actions = re.findall(action_pattern, content, re.IGNORECASE)
    
    action_counts = Counter(a.lower().strip() for a in actions)
    
    # Filter for patterns that appear more than once
    for action, count in action_counts.items():
        if count >= 2:
            patterns[action] = {'count': count, 'actions': []}
            # Find examples of this action
            examples = re.findall(rf'- Action:\s*{re.escape(action)}.*?Result:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            patterns[action]['actions'] = [e.strip() for e in examples[:3]]
    
    return patterns


def generate_insights(cycles: list, patterns: dict, metrics: dict) -> list:
    """Generate distilled insights from the audit data"""
    insights = []
    
    # Insight: Health trend
    health_values = [int(c.get('health', '0/100').split('/')[0]) for c in cycles if c.get('health')]
    if health_values:
        avg_health = sum(health_values) / len(health_values)
        if avg_health >= 95:
            insights.append("Health metrics consistently strong (95+)")
        elif avg_health >= 90:
            insights.append("Health metrics stable, room for optimization")
    
    # Insight: Focus patterns
    if patterns:
        top_pattern = max(patterns.items(), key=lambda x: x[1]['count'])
        insights.append(f"Recurring focus: {top_pattern[0]} ({top_pattern[1]['count']} occurrences)")
    
    # Insight: Productivity
    if metrics.get('tests'):
        insights.append("Test-driven development consistently applied")
    
    if metrics.get('commits'):
        commits = int(metrics['commits'])
        if commits >= 5:
            insights.append("High shipping velocity")
        elif commits >= 3:
            insights.append("Consistent shipping cadence")
    
    return insights


def generate_audit_summary() -> dict:
    """Generate a full audit summary from today's and yesterday's memory files"""
    today = get_today_date()
    yesterday = get_yesterday_date()
    
    today_content = read_memory_file(f'memory/{today}.md')
    yesterday_content = read_memory_file(f'memory/{yesterday}.md')
    
    # Parse cycles from both days
    today_cycles = parse_wake_cycles(today_content)
    yesterday_cycles = parse_wake_cycles(yesterday_content)
    
    # Combine content for pattern detection
    combined_content = f"{today_content}\n{yesterday_content}"
    
    # Detect patterns across both days
    patterns = detect_patterns(combined_content)
    
    # Extract metrics
    metrics = extract_key_metrics(today_content)
    
    # Generate insights
    insights = generate_insights(today_cycles, patterns, metrics)
    
    return {
        'date': today,
        'cycles_today': today_cycles,
        'cycles_yesterday': yesterday_cycles,
        'patterns': patterns,
        'metrics': metrics,
        'insights': insights
    }


def format_summary_for_memory(summary: dict) -> str:
    """Format the audit summary for inclusion in MEMORY.md"""
    lines = []
    lines.append(f"\n## Audit Summary - {summary['date']}")
    lines.append("")
    
    # Key metrics
    if summary['metrics']:
        lines.append("### Key Metrics")
        for key, value in summary['metrics'].items():
            lines.append(f"- {key.title()}: {value}")
        lines.append("")
    
    # Cycles today
    lines.append(f"### Activity ({len(summary['cycles_today'])} cycles)")
    for cycle in summary['cycles_today'][:5]:  # Top 5
        action = cycle.get('action', 'Unknown')
        health = cycle.get('health', 'N/A')
        lines.append(f"- {action} (Health: {health})")
    lines.append("")
    
    # Patterns detected
    if summary['patterns']:
        lines.append("### Detected Patterns")
        for pattern, data in summary['patterns'].items():
            lines.append(f"- **{pattern}** ({data['count']} occurrences)")
        lines.append("")
    
    # Insights
    lines.append("### Insights")
    for insight in summary['insights']:
        lines.append(f"- {insight}")
    lines.append("")
    
    return '\n'.join(lines)


def update_memory_with_insights(summary: dict) -> bool:
    """Update MEMORY.md with distilled insights from the audit"""
    current_content = read_file('MEMORY.md') or ''
    
    # Check if today's audit already exists
    today = summary['date']
    if f"Audit Summary - {today}" in current_content:
        # Already audited today
        return False
    
    # Format new audit section
    audit_section = format_summary_for_memory(summary)
    
    # Append to MEMORY.md
    new_content = f"{current_content}\n{audit_section}"
    
    return write_file('MEMORY.md', new_content)


def run_audit() -> dict:
    """Run the full memory audit and update MEMORY.md"""
    summary = generate_audit_summary()
    updated = update_memory_with_insights(summary)
    
    return {
        'summary': summary,
        'memory_updated': updated
    }


if __name__ == '__main__':
    result = run_audit()
    print(f"Audit completed for {result['summary']['date']}")
    print(f"Memory updated: {result['memory_updated']}")
    print(f"Insights generated: {len(result['summary']['insights'])}")
