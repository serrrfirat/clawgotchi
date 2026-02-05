"""
Opportunity Radar - Detects buildable opportunities in Moltbook feed
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class OpportunityType(Enum):
    """Types of opportunities that can be detected"""
    TOOL_REQUEST = "tool_request"  # "I wish there was a tool for X"
    PROBLEM_COMPLAINT = "problem_complaint"  # "This is annoying/hard"
    FEATURE_REQUEST = "feature_request"  # "Would be cool if X had Y"
    INTEGRATION_NEED = "integration_need"  # "X should work with Y"
    AUTOMATION_GAP = "automation_gap"  # "I keep having to do X manually"


@dataclass
class OpportunitySignal:
    """A detected opportunity signal from a post"""
    post_id: str
    post_title: str
    opportunity_type: OpportunityType
    confidence: float  # 0.0 to 1.0
    keywords: list[str]
    content_snippet: str
    source_url: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "post_title": self.post_title,
            "opportunity_type": self.opportunity_type.value,
            "confidence": self.confidence,
            "keywords": self.keywords,
            "content_snippet": self.content_snippet,
            "source_url": self.source_url
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "OpportunitySignal":
        return cls(
            post_id=data["post_id"],
            post_title=data["post_title"],
            opportunity_type=OpportunityType(data["opportunity_type"]),
            confidence=data["confidence"],
            keywords=data["keywords"],
            content_snippet=data["content_snippet"],
            source_url=data.get("source_url")
        )


class OpportunityRadar:
    """
    Scans Moltbook posts for buildable opportunities
    """
    
    # Keyword patterns for each opportunity type
    KEYWORDS = {
        OpportunityType.TOOL_REQUEST: [
            "wish there was", "wish someone would", "need a tool",
            "looking for a", "anyone know of", "doesn't exist",
            "why isn't there", "missing a tool", "wish i had"
        ],
        OpportunityType.PROBLEM_COMPLAINT: [
            "annoying", "tired of", "frustrated", "pain point",
            "waste of time", "manual", "repetitive", "keep having to",
            "boring", "tedious", "problem", "issue", "bug"
        ],
        OpportunityType.FEATURE_REQUEST: [
            "would be cool", "would be nice", "wish", "feature",
            "enhancement", "improvement", "add", "support for",
            "should have", "could use"
        ],
        OpportunityType.INTEGRATION_NEED: [
            "integrat", "connect", "bridge", "hook",
            "api", "workflow", "pipeline", "chain"
        ],
        OpportunityType.AUTOMATION_GAP: [
            "automate", "automation", "auto", "bot",
            "script", "cron", "schedule", "background",
            "run in the background", "hands-free"
        ]
    }
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or ".opportunities"
        self._detected_opportunities: list[OpportunitySignal] = []
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)
    
    def scan_feed(self, posts: list[dict]) -> list[OpportunitySignal]:
        """
        Analyze a list of Moltbook posts for opportunities
        
        Args:
            posts: List of post dicts with 'id', 'title', 'content' keys
            
        Returns:
            List of detected OpportunitySignal objects
        """
        signals = []
        
        for post in posts:
            post_id = post.get("id", "")
            title = post.get("title", "")
            content = post.get("content", "")
            source_url = post.get("url")
            
            # Combine title and content for analysis
            full_text = f"{title} {content}".lower()
            
            for opp_type, keywords in self.KEYWORDS.items():
                matches = [kw for kw in keywords if kw.lower() in full_text]
                
                if matches:
                    # Calculate confidence based on:
                    # 1. Number of keyword matches
                    # 2. Position (title matches are stronger)
                    # 3. Specificity (exact phrases > single words)
                    
                    base_confidence = min(len(matches) * 0.15, 0.6)  # Max 0.6 from count
                    
                    # Title matches boost confidence
                    title_boost = any(kw.lower() in title.lower() for kw in matches)
                    if title_boost:
                        base_confidence += 0.25
                    
                    # Cap at 1.0
                    confidence = min(base_confidence, 1.0)
                    
                    # Only include if confidence is meaningful
                    if confidence >= 0.3:
                        signal = OpportunitySignal(
                            post_id=post_id,
                            post_title=title,
                            opportunity_type=opp_type,
                            confidence=confidence,
                            keywords=matches,
                            content_snippet=content[:200] if len(content) > 200 else content,
                            source_url=source_url
                        )
                        signals.append(signal)
        
        self._detected_opportunities.extend(signals)
        return signals
    
    def score_opportunity(self, signal: OpportunitySignal) -> float:
        """
        Score an opportunity for build-worthiness
        
        Factors:
        - Confidence score (from detection)
        - Type relevance (some types are more actionable)
        - Recurring patterns (same keywords in multiple posts)
        """
        base_score = signal.confidence
        
        # Type weighting - tool requests and automation gaps are most actionable
        type_weights = {
            OpportunityType.TOOL_REQUEST: 1.2,
            OpportunityType.AUTOMATION_GAP: 1.15,
            OpportunityType.PROBLEM_COMPLAINT: 1.1,
            OpportunityType.INTEGRATION_NEED: 1.0,
            OpportunityType.FEATURE_REQUEST: 0.9,
        }
        type_weight = type_weights.get(signal.opportunity_type, 1.0)
        
        # Keyword bonus for highly actionable terms
        actionable_bonus = 0.0
        for kw in signal.keywords:
            if kw in ["automate", "wish there was", "tired of", "keep having to"]:
                actionable_bonus += 0.05
        
        final_score = (base_score * type_weight) + actionable_bonus
        return min(final_score, 1.0)
    
    def get_top_opportunities(self, limit: int = 5) -> list[OpportunitySignal]:
        """
        Get the highest-scoring opportunities
        
        Args:
            limit: Maximum number of opportunities to return
            
        Returns:
            Sorted list of OpportunitySignal objects by build-worthiness
        """
        scored = [(s, self.score_opportunity(s)) for s in self._detected_opportunities]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:limit]]
    
    def save_opportunities(self, signals: list[OpportunitySignal] = None) -> str:
        """
        Save detected opportunities to JSON
        
        Args:
            signals: List of signals to save (defaults to all detected)
            
        Returns:
            Path to saved file
        """
        signals = signals or self._detected_opportunities
        if not signals:
            return ""
        
        timestamp = Path().stem
        filename = f"{self.storage_path}/opportunities_{timestamp}.json"
        
        data = {
            "saved_at": str(Path().cwd()),
            "count": len(signals),
            "signals": [s.to_dict() for s in signals]
        }
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        return filename
    
    def load_opportunities(self, filepath: str) -> list[OpportunitySignal]:
        """
        Load opportunities from a JSON file
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            List of OpportunitySignal objects
        """
        with open(filepath, "r") as f:
            data = json.load(f)
        
        return [OpportunitySignal.from_dict(s) for s in data["signals"]]
    
    def get_stats(self) -> dict:
        """
        Get statistics about detected opportunities
        """
        if not self._detected_opportunities:
            return {"total": 0, "by_type": {}}
        
        by_type = {}
        for opp_type in OpportunityType:
            count = sum(1 for s in self._detected_opportunities if s.opportunity_type == opp_type)
            by_type[opp_type.value] = count
        
        avg_confidence = sum(s.confidence for s in self._detected_opportunities) / len(self._detected_opportunities)
        
        return {
            "total": len(self._detected_opportunities),
            "by_type": by_type,
            "avg_confidence": round(avg_confidence, 3)
        }


def quick_scan(posts: list[dict], limit: int = 3) -> list[OpportunitySignal]:
    """
    Convenience function to quickly scan posts and get top opportunities
    """
    radar = OpportunityRadar()
    signals = radar.scan_feed(posts)
    return radar.get_top_opportunities(limit=limit)
