"""Memory Quality Scorer - Analyzes memory files for quality signals."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import json
import re
from collections import Counter


class QualityDimension(Enum):
    """Quality dimensions for memory analysis."""
    RECENCY = "recency"
    ENTROPY = "entropy"
    ACTIONABILITY = "actionability"
    COHERENCE = "coherence"
    DUPLICATION = "duplication"


@dataclass
class QualityScore:
    """Score for a single quality dimension."""
    dimension: QualityDimension
    value: float  # 0.0 to 1.0
    weight: float = 1.0
    finding: str = ""
    
    @property
    def weighted_value(self) -> float:
        """Calculate weighted value."""
        return self.value * self.weight


@dataclass
class QualityFinding:
    """A finding from quality analysis."""
    dimension: QualityDimension
    score: float
    description: str
    recommendation: str


@dataclass
class QualityResult:
    """Result of quality analysis."""
    file_path: Path
    overall_score: float
    dimension_scores: List[QualityScore]
    findings: List[QualityFinding] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)


@dataclass
class QualityReport:
    """Formatted quality report."""
    title: str
    overall_score: float
    dimension_breakdown: Dict[str, float]
    top_findings: List[str]
    recommendations: List[str]
    
    def summary(self) -> str:
        """Generate summary text."""
        score_label = "Excellent" if self.overall_score >= 0.8 else \
                      "Good" if self.overall_score >= 0.6 else \
                      "Fair" if self.overall_score >= 0.4 else \
                      "Poor"
        
        lines = [
            f"Quality Analysis Report: {score_label} ({self.overall_score:.1%})",
            "",
            "Dimensions:",
        ]
        for dim, score in self.dimension_breakdown.items():
            lines.append(f"  - {dim}: {score:.1%}")
        
        if self.top_findings:
            lines.extend(["", "Key Findings:"])
            for finding in self.top_findings[:3]:
                lines.append(f"  • {finding}")
        
        if self.recommendations:
            lines.extend(["", "Recommendations:"])
            for rec in self.recommendations[:3]:
                lines.append(f"  → {rec}")
        
        return "\n".join(lines)


class MemoryQualityAnalyzer:
    """Analyzes memory files for quality signals."""
    
    # Weights for each dimension in overall score
    WEIGHTS = {
        QualityDimension.RECENCY: 0.25,
        QualityDimension.ENTROPY: 0.20,
        QualityDimension.ACTIONABILITY: 0.25,
        QualityDimension.COHERENCE: 0.15,
        QualityDimension.DUPLICATION: 0.15,
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize analyzer with optional configuration."""
        self.config = config or {}
        self.history: List[QualityResult] = []
        self._patterns = self._init_patterns()
    
    def _init_patterns(self) -> Dict:
        """Initialize regex patterns for analysis."""
        return {
            "date_iso": re.compile(r'\d{4}-\d{2}-\d{2}'),
            "date_human": re.compile(
                r'(today|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
                re.IGNORECASE
            ),
            "todo_checkbox": re.compile(r'^[\s]*[-*+]\s*\[\s*[xX ]?\s*\]\s*'),
            "todo_brackets": re.compile(r'\[\s*[xX ]?\s*\]'),
            "todo_dash": re.compile(r'^[\s]*[-*+]\s*(TODO|FIX|XXX|BUG|NOTE):?'),
            "action_verbs": re.compile(
                r'\b(built|created|fixed|added|implemented|designed|wrote|shipped|tested|'
                r'deployed|reviewed|analyzed|planned|decided|learned|refactored|'
                r'optimized|debugged|integrated|verified)\b',
                re.IGNORECASE
            ),
            "header": re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE),
            "bullet": re.compile(r'^[\s]*[-*+]\s+'),
            "number_bullet": re.compile(r'^[\s]*\d+[\.\)]\s+'),
        }
    
    def analyze(self, file_path: Path) -> QualityResult:
        """Analyze a memory file for quality signals."""
        content = file_path.read_text() if file_path.exists() else ""
        
        scores = [
            self._score_recency(content),
            self._score_entropy(content),
            self._score_actionability(content),
            self._score_coherence(content),
            self._score_duplication(content),
        ]
        
        # Calculate weighted overall score
        total_weight = sum(self.WEIGHTS.get(s.dimension, 0.5) for s in scores)
        overall = sum(s.weighted_value for s in scores) / total_weight if total_weight > 0 else 0
        
        # Generate findings
        findings = self._generate_findings(scores)
        
        result = QualityResult(
            file_path=file_path,
            overall_score=overall,
            dimension_scores=scores,
            findings=findings,
        )
        
        self.history.append(result)
        return result
    
    def _score_recency(self, content: str) -> QualityScore:
        """Score based on content recency."""
        dates = self._patterns["date_iso"].findall(content)
        if not dates:
            # Try human-readable dates
            human_dates = self._patterns["date_human"].findall(content.lower())
            if "today" in human_dates or "yesterday" in human_dates:
                return QualityScore(
                    dimension=QualityDimension.RECENCY,
                    value=0.9,
                    weight=self.WEIGHTS[QualityDimension.RECENCY],
                    finding="Recent human-readable date detected"
                )
            return QualityScore(
                dimension=QualityDimension.RECENCY,
                value=0.1,
                weight=self.WEIGHTS[QualityDimension.RECENCY],
                finding="No recent date found"
            )
        
        # Find most recent date
        try:
            most_recent = max(dates)
            date_obj = datetime.strptime(most_recent, "%Y-%m-%d")
            days_ago = (datetime.now() - date_obj).days
            
            if days_ago <= 1:
                value = 1.0
            elif days_ago <= 7:
                value = 0.9 - (days_ago - 1) * 0.1
            elif days_ago <= 30:
                value = 0.5 - (days_ago - 7) * 0.02
            else:
                value = max(0.0, 0.3 - (days_ago - 30) * 0.01)
            
            return QualityScore(
                dimension=QualityDimension.RECENCY,
                value=max(0.0, min(1.0, value)),
                weight=self.WEIGHTS[QualityDimension.RECENCY],
                finding=f"Most recent date: {most_recent} ({days_ago} days ago)"
            )
        except (ValueError, TypeError):
            return QualityScore(
                dimension=QualityDimension.RECENCY,
                value=0.3,
                weight=self.WEIGHTS[QualityDimension.RECENCY],
                finding="Could not parse dates"
            )
    
    def _score_entropy(self, content: str) -> QualityScore:
        """Score based on content diversity/entropy."""
        if not content.strip():
            return QualityScore(
                dimension=QualityDimension.ENTROPY,
                value=0.0,
                weight=self.WEIGHTS[QualityDimension.ENTROPY],
                finding="Empty content"
            )
        
        words = re.findall(r'\b\w+\b', content.lower())
        if len(words) < 10:
            return QualityScore(
                dimension=QualityDimension.ENTROPY,
                value=0.2,
                weight=self.WEIGHTS[QualityDimension.ENTROPY],
                finding="Content too short for entropy analysis"
            )
        
        # Calculate vocabulary diversity
        unique_words = len(set(words))
        total_words = len(words)
        diversity = unique_words / total_words if total_words > 0 else 0
        
        # Check for topic variety (unique bigrams)
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        unique_bigrams = len(set(bigrams))
        bigram_diversity = unique_bigrams / len(bigrams) if bigrams else 0
        
        # Combine measures
        combined = (diversity * 0.6 + bigram_diversity * 0.4)
        
        return QualityScore(
            dimension=QualityDimension.ENTROPY,
            value=min(1.0, combined * 2),  # Boost for display
            weight=self.WEIGHTS[QualityDimension.ENTROPY],
            finding=f"Vocabulary diversity: {diversity:.1%}"
        )
    
    def _score_actionability(self, content: str) -> QualityScore:
        """Score based on action items and tasks."""
        lines = content.split('\n')
        action_count = 0
        completed_count = 0
        total_lines = len(lines)
        
        for line in lines:
            # Check for checkbox items: - [ ] or - [x]
            if self._patterns["todo_brackets"].search(line):
                action_count += 1
                if '[x]' in line.lower() or '[X]' in line:
                    completed_count += 1
            
            # Check for TODO-style items
            elif self._patterns["todo_dash"].search(line):
                action_count += 1
            
            # Check for action verbs
            elif self._patterns["action_verbs"].search(line):
                action_count += 1
        
        if total_lines == 0:
            return QualityScore(
                dimension=QualityDimension.ACTIONABILITY,
                value=0.0,
                weight=self.WEIGHTS[QualityDimension.ACTIONABILITY],
                finding="No content to analyze"
            )
        
        # Score based on action density and completion
        action_density = action_count / min(total_lines, 20)  # Cap at 20 lines
        completion_rate = completed_count / action_count if action_count > 0 else 0
        
        # Balance between having actions and completing them
        value = (action_density * 0.6 + completion_rate * 0.4)
        
        return QualityScore(
            dimension=QualityDimension.ACTIONABILITY,
            value=min(1.0, value * 2),
            weight=self.WEIGHTS[QualityDimension.ACTIONABILITY],
            finding=f"Found {action_count} action items ({completed_count} completed)"
        )
    
    def _score_coherence(self, content: str) -> QualityScore:
        """Score based on content structure and coherence."""
        if not content.strip():
            return QualityScore(
                dimension=QualityDimension.COHERENCE,
                value=0.0,
                weight=self.WEIGHTS[QualityDimension.COHERENCE],
                finding="Empty content"
            )
        
        # Check for structure (headers, lists)
        header_count = len(self._patterns["header"].findall(content))
        bullet_count = len(self._patterns["bullet"].findall(content))
        number_count = len(self._patterns["number_bullet"].findall(content))
        
        lines = content.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        
        if not non_empty_lines:
            return QualityScore(
                dimension=QualityDimension.COHERENCE,
                value=0.0,
                weight=self.WEIGHTS[QualityDimension.COHERENCE],
                finding="No content lines"
            )
        
        # Structure score
        structure_score = min(1.0, (header_count + bullet_count + number_count) / 5)
        
        # Line length variance (reasonable variance suggests different content types)
        avg_length = sum(len(l) for l in non_empty_lines) / len(non_empty_lines)
        if avg_length > 0:
            variance = sum((len(l) - avg_length) ** 2 for l in non_empty_lines) / len(non_empty_lines)
            length_variance = min(1.0, variance / (avg_length ** 2))
        else:
            length_variance = 0
        
        # Section headers suggest organized thought
        header_ratio = header_count / len(non_empty_lines)
        
        combined = (structure_score * 0.5 + length_variance * 0.3 + header_ratio * 0.2)
        
        return QualityScore(
            dimension=QualityDimension.COHERENCE,
            value=min(1.0, combined * 2),
            weight=self.WEIGHTS[QualityDimension.COHERENCE],
            finding=f"Structure: {header_count} headers, {bullet_count} lists"
        )
    
    def _score_duplication(self, content: str) -> QualityScore:
        """Score based on content duplication."""
        if not content.strip():
            return QualityScore(
                dimension=QualityDimension.DUPLICATION,
                value=1.0,  # No duplication in empty content
                weight=self.WEIGHTS[QualityDimension.DUPLICATION],
                finding="No content to check"
            )
        
        # Check for repeated phrases (3+ word sequences)
        words = re.findall(r'\b\w+\b', content.lower())
        if len(words) < 10:
            return QualityScore(
                dimension=QualityDimension.DUPLICATION,
                value=0.8,
                weight=self.WEIGHTS[QualityDimension.DUPLICATION],
                finding="Short content, low duplication risk"
            )
        
        # Check repeated n-grams
        n = 3
        ngrams = [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
        ngram_counts = Counter(ngrams)
        
        repeats = sum(1 for ngram, count in ngram_counts.items() if count > 1)
        repeat_ratio = repeats / len(ngram_counts) if ngram_counts else 0
        
        # Also check for repeated bullet items (similar starts)
        bullet_lines = [l.strip() for l in content.split('\n') 
                       if self._patterns["bullet"].search(l)]
        if len(bullet_lines) >= 3:
            bullet_starts = [self._patterns["bullet"].sub('', l).split()[0] if l.split() else '' 
                           for l in bullet_lines]
            bullet_counts = Counter(bullet_starts)
            bullet_repeats = sum(1 for count in bullet_counts.values() if count > 1)
            bullet_repeat_ratio = bullet_repeats / len(bullet_lines)
        else:
            bullet_repeat_ratio = 0
        
        # Combined duplication score (lower = more duplication)
        avg_repeat = (repeat_ratio + bullet_repeat_ratio) / 2
        uniqueness = 1.0 - min(1.0, avg_repeat * 2)
        
        return QualityScore(
            dimension=QualityDimension.DUPLICATION,
            value=uniqueness,
            weight=self.WEIGHTS[QualityDimension.DUPLICATION],
            finding=f"Uniqueness: {uniqueness:.1%}"
        )
    
    def _generate_findings(self, scores: List[QualityScore]) -> List[QualityFinding]:
        """Generate actionable findings from scores."""
        findings = []
        
        for score in scores:
            if score.value < 0.4:
                finding = self._create_finding(score)
                if finding:
                    findings.append(finding)
        
        return findings
    
    def _create_finding(self, score: QualityScore) -> Optional[QualityFinding]:
        """Create a finding from a low-scoring dimension."""
        recs = {
            QualityDimension.RECENCY: "Add recent dates or timestamps to show current context",
            QualityDimension.ENTROPY: "Add more diverse topics and unique content",
            QualityDimension.ACTIONABILITY: "Include action items, todos, or completed tasks",
            QualityDimension.COHERENCE: "Use headers, lists, and structured sections",
            QualityDimension.DUPLICATION: "Remove repeated phrases and consolidate similar items",
        }
        
        descs = {
            QualityDimension.RECENCY: "Content appears stale or lacks recent timestamps",
            QualityDimension.ENTROPY: "Content shows low diversity or repetitive topics",
            QualityDimension.ACTIONABILITY: "Missing action items or task tracking",
            QualityDimension.COHERENCE: "Content lacks clear structure or organization",
            QualityDimension.DUPLICATION: "Content contains repeated or duplicated phrases",
        }
        
        return QualityFinding(
            dimension=score.dimension,
            score=score.value,
            description=descs.get(score.dimension, "Quality issue detected"),
            recommendation=recs.get(score.dimension, "Review and improve content"),
        )
    
    def get_report(self, result: QualityResult) -> QualityReport:
        """Generate a formatted report from analysis result."""
        breakdown = {
            s.dimension.value: s.value for s in result.dimension_scores
        }
        
        top_findings = [f.description for f in result.findings[:3]]
        recommendations = [f.recommendation for f in result.findings[:3]]
        
        return QualityReport(
            title="Quality Analysis Report",
            overall_score=result.overall_score,
            dimension_breakdown=breakdown,
            top_findings=top_findings,
            recommendations=recommendations,
        )
    
    def save_state(self, path: Path) -> None:
        """Save analyzer state to file."""
        state = {
            "history": [
                {
                    "file_path": str(r.file_path),
                    "overall_score": r.overall_score,
                    "dimension_scores": [
                        {
                            "dimension": s.dimension.value,
                            "value": s.value,
                            "weight": s.weight,
                            "finding": s.finding,
                        }
                        for s in r.dimension_scores
                    ],
                    "analyzed_at": r.analyzed_at.isoformat(),
                }
                for r in self.history
            ],
            "config": self.config,
        }
        path.write_text(json.dumps(state, indent=2))
    
    @classmethod
    def load_state(cls, path: Path) -> "MemoryQualityAnalyzer":
        """Load analyzer state from file."""
        state = json.loads(path.read_text())
        analyzer = cls(config=state.get("config", {}))
        # History is read-only for now
        return analyzer
    
    def get_statistics(self) -> Dict:
        """Get analysis statistics."""
        if not self.history:
            return {"total_analyses": 0}
        
        scores = [r.overall_score for r in self.history]
        dim_scores = {dim.value: [] for dim in QualityDimension}
        
        for r in self.history:
            for s in r.dimension_scores:
                dim_scores[s.dimension.value].append(s.value)
        
        return {
            "total_analyses": len(self.history),
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "dimension_averages": {
                dim: sum(vals) / len(vals) if vals else 0
                for dim, vals in dim_scores.items()
            },
        }


def analyze_memory_quality(file_path: str) -> QualityResult:
    """Convenience function to analyze a memory file."""
    return MemoryQualityAnalyzer().analyze(Path(file_path))
