"""Session Memory Extractor

Extracts structured, storable memories from verbose session logs.
Inspired by PuzleReadBot: "Reading is an act of reconstruction" — 
this utility does the inverse: reconstruct atomic facts from session transcripts.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class Fact:
    """An extracted atomic fact from session data"""
    content: str
    importance: float  # 0.0 to 1.0
    category: str  # build, decision, insight, metric, etc.
    source_context: str


class SessionMemoryExtractor:
    """Extracts actionable memories from verbose session logs"""
    
    # Importance indicators
    HIGH_IMPORTANCE_PATTERNS = [
        r"built|created|implemented|deployed",
        r"tests?\s*(passing|pass|failing|fail)",
        r"commit:\s*[a-f0-9]+",
        r"moltbook|posted|published",
        r"health:\s*\d+/\d+",
    ]
    
    MEDIUM_IMPORTANCE_PATTERNS = [
        r"inspired by|based on",
        r"features?:",
        r"wake cycle",
        r"action:|result:",
    ]
    
    LOW_IMPORTANCE_PATTERNS = [
        r"reading|loaded|checked",
        r"sleeping|resting|waiting",
        r"curl|curl",
    ]
    
    CATEGORY_PATTERNS = {
        "build": r"built|created|built|constructed|shipped",
        "decision": r"decided|chose|opted|picked",
        "insight": r"realized|learned|discovered|understood",
        "metric": r"\d+ tests?\s*(passing|failing)|\d+/\d+|commit:",
        "error": r"fail|error|exception|crash|broken",
        "memory": r"memory|stored|remembered|recorded",
    }
    
    def __init__(self):
        self.high_patterns = [re.compile(p, re.IGNORECASE) for p in self.HIGH_IMPORTANCE_PATTERNS]
        self.medium_patterns = [re.compile(p, re.IGNORECASE) for p in self.MEDIUM_IMPORTANCE_PATTERNS]
        self.low_patterns = [re.compile(p, re.IGNORECASE) for p in self.LOW_IMPORTANCE_PATTERNS]
        self.category_patterns = {k: re.compile(v, re.IGNORECASE) for k, v in self.CATEGORY_PATTERNS.items()}
    
    def extract_facts(self, text: str) -> List[str]:
        """Extract atomic facts from session text"""
        facts = []
        
        # Split by common separators
        lines = re.split(r'[\n\r]+|[-–—]+|\.', text)
        
        for line in lines:
            line = line.strip()
            if len(line) < 10:
                continue
            
            # Skip noise
            if any(p.match(line) for p in self.low_patterns):
                continue
            
            # Extract meaningful segments
            if any(p.search(line) for p in self.high_patterns + self.medium_patterns):
                facts.append(line.strip())
        
        # Also extract dates and tools as standalone facts
        dates = self.extract_dates(text)
        for date in dates:
            facts.append(f"Date: {date}")
        
        tools = self.extract_tools(text)
        for tool in tools:
            facts.append(f"Tool: {tool}")
        
        return facts
    
    def _calculate_importance(self, text: str) -> float:
        """Calculate importance score for a fact"""
        score = 0.0
        
        # High importance indicators
        if any(p.search(text) for p in self.high_patterns):
            score += 0.5
        
        # Medium importance
        if any(p.search(text) for p in self.medium_patterns):
            score += 0.2
        
        # Length factor (concise is often more actionable)
        word_count = len(text.split())
        if 3 <= word_count <= 20:
            score += 0.2
        elif word_count > 30:
            score -= 0.1
        
        # Clamp to 0-1
        return max(0.0, min(1.0, score))
    
    def _categorize(self, text: str) -> str:
        """Determine the category of a fact"""
        for category, pattern in self.category_patterns.items():
            if pattern.search(text):
                return category
        return "general"
    
    def extract_and_rank(self, text: str) -> List[Dict[str, Any]]:
        """Extract facts and rank by importance"""
        facts = self.extract_facts(text)
        ranked = []
        
        for fact in facts:
            ranked.append({
                "content": fact,
                "importance": self._calculate_importance(fact),
                "category": self._categorize(fact),
            })
        
        # Sort by importance descending
        ranked.sort(key=lambda x: x["importance"], reverse=True)
        return ranked
    
    def extract_dates(self, text: str) -> List[str]:
        """Extract date patterns from text"""
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # ISO format
            r"\d{2}/\d{2}/\d{4}",  # US format
            r"today|now",
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return list(set(dates))
    
    def extract_tools(self, text: str) -> List[str]:
        """Extract tool/utility/file references"""
        # Match common patterns: utils/foo.py, skills/.../SKILL.md, tests/...
        patterns = [
            r"utils/[a-z_]+\.py",
            r"tests/test_[a-z_]+\.py",
            r"skills/[a-z_-]+/SKILL\.md",
            r"memory/[a-z_-]+\.md",
        ]
        
        tools = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            tools.extend(matches)
        
        return list(set(tools))
    
    def format_for_memory(self, text: str, session_date: str = None) -> Dict[str, Any]:
        """Format extracted facts for memory storage"""
        ranked = self.extract_and_rank(text)
        dates = self.extract_dates(text)
        tools = self.extract_tools(text)
        
        # Auto-detect date if not provided
        if not session_date and dates:
            # Prefer ISO format
            iso_dates = [d for d in dates if re.match(r"\d{4}-\d{2}-\d{2}", d)]
            session_date = iso_dates[0] if iso_dates else dates[0]
        
        # Build memory structure
        memory = {
            "content": text,  # Original content
            "date": session_date or datetime.now().strftime("%Y-%m-%d"),
            "facts": [r["content"] for r in ranked],
            "ranked_facts": ranked,
            "tools": tools,
            "tags": list(set(r["category"] for r in ranked)),  # Categories as tags
            "metadata": {
                "fact_count": len(ranked),
                "high_importance_count": len([r for r in ranked if r["importance"] >= 0.7]),
                "categories": list(set(r["category"] for r in ranked)),
            }
        }
        
        return memory


# Convenience function for quick extraction
def extract_session_memory(text: str) -> Dict[str, Any]:
    """Quick extraction of memories from session text"""
    extractor = SessionMemoryExtractor()
    return extractor.format_for_memory(text)


if __name__ == "__main__":
    # Demo usage
    sample = """Wake Cycle #724:
    - Built Context Compressor - 5-stage compression ladder
    - Inspired by @promptomat's post
    - 8 tests passing
    - Commit: 8d8f1c4
    - Health: 96/100"""
    
    result = extract_session_memory(sample)
    print(f"Extracted {result['metadata']['fact_count']} facts")
    print(f"High importance: {result['metadata']['high_importance_count']}")
    print(f"Categories: {result['metadata']['categories']}")
    print(f"Tools: {result['tools']}")
