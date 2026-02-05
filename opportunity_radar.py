"""
Opportunity Radar Module
Detects buildable opportunities from Moltbook feed and community signals.
"""

from enum import Enum
from typing import List, Dict, Optional
import re
from datetime import datetime


class OpportunityType(Enum):
    """Types of buildable opportunities detected from community signals."""
    TOOL_REQUEST = "TOOL_REQUEST"       # "I need a tool to do X"
    PROBLEM_COMPLAINT = "PROBLEM_COMPLAINT"  # "X is broken/broken/doesn't work"
    FEATURE_REQUEST = "FEATURE_REQUEST"  # "It would be great if X had Y"
    INTEGRATION_NEED = "INTEGRATION_NEED"  # "X should work with Y"
    AUTOMATION_GAP = "AUTOMATION_GAP"  # "I have to do X manually"


# Keyword patterns for each opportunity type
TOOL_KEYWORDS = [
    "need a tool", "looking for", "does anyone know", "searching for",
    "wish there was", "want a", "need something to", "tool to",
    "automate", "automation", "script", "helper", "utility"
]

PROBLEM_KEYWORDS = [
    "broken", "doesn't work", "not working", "fails", "crashes",
    "bug", "error", "problem", "issue", "stuck", "frustrated",
    "annoying", "slow", "broken", "fix", "help"
]

FEATURE_KEYWORDS = [
    "would be great", "wish", "could you add", "feature request",
    "would be nice", "need", "should have", "add", "support for",
    "implement", "new feature", "could use", "mode"
]

INTEGRATION_KEYWORDS = [
    "integrate", "integration", "connect", "bridge", "work with",
    "sync with", "import from", "export to", "pair with"
]

AUTOMATION_KEYWORDS = [
    "manually", "by hand", "every time", "repetitive", "tedious",
    "have to do", "repeat", "cron", "schedule", "automate"
]


def extract_keywords(text: str) -> List[str]:
    """Extract relevant keywords from text."""
    text_lower = text.lower()
    found = []
    
    # Check for tool keywords
    for kw in TOOL_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    
    # Check for problem keywords
    for kw in PROBLEM_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    
    # Check for feature keywords
    for kw in FEATURE_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    
    # Check for integration keywords
    for kw in INTEGRATION_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    
    # Check for automation keywords
    for kw in AUTOMATION_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    
    return found


def calculate_confidence(title: str, content: str, keywords: List[str]) -> float:
    """Calculate confidence score (0.0-1.0) for an opportunity."""
    if not keywords:
        return 0.0
    
    score = 0.0
    
    # Base score from keywords
    keyword_count = len(keywords)
    score += min(keyword_count * 0.1, 0.4)  # Max 0.4 from keyword count
    
    # Title match boost
    title_lower = title.lower()
    title_boost = 0.0
    
    if any(kw in title_lower for kw in ["request", "need", "want", "wish"]):
        title_boost += 0.2
    if any(kw in title_lower for kw in ["broken", "bug", "fix", "problem"]):
        title_boost += 0.2
    if any(kw in title_lower for kw in ["feature", "add", "integrate"]):
        title_boost += 0.2
    
    score += min(title_boost, 0.3)  # Max 0.3 boost from title
    
    # Type-specific scoring
    if any(kw in keywords for kw in TOOL_KEYWORDS):
        score += 0.2
    if any(kw in keywords for kw in PROBLEM_KEYWORDS):
        score += 0.2  # Increased from 0.1
    if any(kw in keywords for kw in FEATURE_KEYWORDS):
        score += 0.1
    if any(kw in keywords for kw in INTEGRATION_KEYWORDS):
        score += 0.1
    if any(kw in keywords for kw in AUTOMATION_KEYWORDS):
        score += 0.1
    
    return min(score, 1.0)


def detect_opportunity(title: str, content: str, author: str) -> Optional[Dict]:
    """Detect if a post represents a buildable opportunity."""
    text = f"{title} {content}"
    keywords = extract_keywords(text)
    
    if not keywords:
        return None
    
    # Determine opportunity type based on dominant keywords
    tool_count = sum(1 for kw in keywords if kw in TOOL_KEYWORDS)
    problem_count = sum(1 for kw in keywords if kw in PROBLEM_KEYWORDS)
    feature_count = sum(1 for kw in keywords if kw in FEATURE_KEYWORDS)
    integration_count = sum(1 for kw in keywords if kw in INTEGRATION_KEYWORDS)
    automation_count = sum(1 for kw in keywords if kw in AUTOMATION_KEYWORDS)
    
    counts = [
        (tool_count, OpportunityType.TOOL_REQUEST),
        (problem_count, OpportunityType.PROBLEM_COMPLAINT),
        (feature_count, OpportunityType.FEATURE_REQUEST),
        (integration_count, OpportunityType.INTEGRATION_NEED),
        (automation_count, OpportunityType.AUTOMATION_GAP),
    ]
    
    # Sort by count descending
    counts.sort(key=lambda x: x[0], reverse=True)
    
    # Special case: if "manually" appears, strongly favor AUTOMATION_GAP
    if "manually" in text:
        return {
            'type': OpportunityType.AUTOMATION_GAP.value,
            'confidence': calculate_confidence(title, content, keywords),
            'title': title,
            'author': author,
            'keywords': keywords + ["manually"],
            'detected_at': datetime.now().isoformat()
        }
    
    if counts[0][0] == 0:
        return None
    
    dominant_type = counts[0][1]
    confidence = calculate_confidence(title, content, keywords)
    
    return {
        'type': dominant_type.value,
        'confidence': confidence,
        'title': title,
        'author': author,
        'keywords': keywords,
        'detected_at': datetime.now().isoformat()
    }


def get_top_opportunities(opportunities: List[Dict], limit: int = 5) -> List[Dict]:
    """Get top opportunities ranked by confidence."""
    sorted_opps = sorted(opportunities, key=lambda x: x.get('confidence', 0), reverse=True)
    return sorted_opps[:limit]
