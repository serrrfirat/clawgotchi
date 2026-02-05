"""
Confidence Calibration Tracker for Agent Self-Reflection.

Tracks prediction confidence vs actual outcomes to measure and improve calibration.
Based on Ernestine's calibration checklist:
1. Say the uncertainty plainly ("I'm not sure.")
2. Give a best-guess probability
3. Name the missing evidence
4. Offer a safe next step
5. Mark what could change your mind

Features:
- Prediction recording with confidence levels
- Outcome tracking and Brier score calculation
- Calibration accuracy by confidence bin
- Session management for focused calibration exercises
- JSON persistence for historical tracking
"""
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


@dataclass
class Prediction:
    """Represents a single prediction with confidence level."""
    id: str
    statement: str
    confidence: float  # 0.0 to 1.0
    category: str
    source: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved: bool = False
    outcome: Optional[bool] = None
    resolved_at: Optional[str] = None
    evidence_missing: Optional[str] = None
    safe_next_step: Optional[str] = None
    mind_changer: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Prediction':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CalibrationMetric:
    """Summary metrics for calibration accuracy."""
    bin_range: str  # e.g., "0.8-1.0"
    average_confidence: float
    actual_accuracy: float  # proportion that were correct
    prediction_count: int
    calibration_error: float  # |confidence - accuracy|
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CalibrationSession:
    """A focused session for calibrating predictions."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    storage_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    predictions: List[Prediction] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure predictions list exists."""
        if self.predictions is None:
            self.predictions = []
    
    def add_prediction(
        self,
        statement: str,
        confidence: float,
        category: str = "session",
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        evidence_missing: Optional[str] = None,
        safe_next_step: Optional[str] = None,
        mind_changer: Optional[str] = None
    ) -> Prediction:
        """Add a prediction to this session."""
        pred = Prediction(
            id=str(uuid.uuid4()),
            statement=statement,
            confidence=max(0.0, min(1.0, confidence)),  # Clamp to [0, 1]
            category=category,
            source=source,
            context=context,
            evidence_missing=evidence_missing,
            safe_next_step=safe_next_step,
            mind_changer=mind_changer
        )
        self.predictions.append(pred)
        return pred
    
    def resolve_prediction(self, pred_id: str, outcome: bool) -> bool:
        """Resolve a prediction with its actual outcome."""
        for pred in self.predictions:
            if pred.id == pred_id and not pred.resolved:
                pred.resolved = True
                pred.outcome = outcome
                pred.resolved_at = datetime.now().isoformat()
                return True
        return False
    
    def get_summary(self) -> Dict:
        """Generate summary statistics for this session."""
        resolved = [p for p in self.predictions if p.resolved]
        correct = [p for p in resolved if p.outcome]
        
        if resolved:
            brier = self._calculate_brier_score(resolved)
            calibration_by_bin = self._get_calibration_by_bin(resolved)
        else:
            brier = 0.0
            calibration_by_bin = {}
        
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "total_predictions": len(self.predictions),
            "resolved_predictions": len(resolved),
            "correct_predictions": len(correct),
            "correct_rate": len(correct) / len(resolved) if resolved else 0.0,
            "brier_score": brier,
            "calibration_by_bin": calibration_by_bin
        }
    
    def _calculate_brier_score(self, resolved: List[Prediction]) -> float:
        """Calculate Brier score for resolved predictions."""
        if not resolved:
            return 0.0
        
        total = 0.0
        for pred in resolved:
            # Brier score = (confidence - outcome)^2
            # outcome is 0 or 1
            outcome_val = 1.0 if pred.outcome else 0.0
            total += (pred.confidence - outcome_val) ** 2
        
        return total / len(resolved)
    
    def _get_calibration_by_bin(self, resolved: List[Prediction]) -> Dict[str, Dict]:
        """Group predictions by confidence bin and calculate accuracy."""
        bins = {
            "0.8-1.0": [],
            "0.6-0.8": [],
            "0.4-0.6": [],
            "0.2-0.4": [],
            "0.0-0.2": []
        }
        
        for pred in resolved:
            if pred.confidence >= 0.8:
                bins["0.8-1.0"].append(pred)
            elif pred.confidence >= 0.6:
                bins["0.6-0.8"].append(pred)
            elif pred.confidence >= 0.4:
                bins["0.4-0.6"].append(pred)
            elif pred.confidence >= 0.2:
                bins["0.2-0.4"].append(pred)
            else:
                bins["0.0-0.2"].append(pred)
        
        result = {}
        for bin_range, preds in bins.items():
            if preds:
                avg_conf = sum(p.confidence for p in preds) / len(preds)
                correct = sum(1 for p in preds if p.outcome)
                actual_acc = correct / len(preds)
                
                result[bin_range] = {
                    "bin_range": bin_range,
                    "average_confidence": avg_conf,
                    "actual_accuracy": actual_acc,
                    "prediction_count": len(preds),
                    "calibration_error": abs(avg_conf - actual_acc)
                }
        
        return result
    
    def save(self) -> bool:
        """Save session to JSON file."""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            filepath = os.path.join(self.storage_path, f"session_{self.id}.json")
            data = {
                "id": self.id,
                "name": self.name,
                "created_at": self.created_at,
                "predictions": [p.to_dict() for p in self.predictions]
            }
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False


class ConfidenceCalibrator:
    """
    Main class for tracking and improving agent confidence calibration.
    
    Usage:
        calibrator = ConfidenceCalibrator(storage_path="./data")
        
        # Record a prediction with confidence
        pred_id = calibrator.record_prediction(
            statement="Model X will outperform baseline",
            confidence=0.75,
            category="benchmark"
        )
        
        # Later, record the outcome
        calibrator.record_outcome(pred_id, outcome=True)
        
        # Check calibration metrics
        stats = calibrator.get_overall_calibration()
        bins = calibrator.get_calibration_by_bin()
        
        # Get recommendations
        thresholds = calibrator.get_threshold_recommendations()
    """
    
    def __init__(self, storage_path: str = "./data/confidence"):
        """Initialize the calibrator."""
        self.storage_path = storage_path
        self.predictions: List[Prediction] = []
        self._load()
    
    def record_prediction(
        self,
        statement: str,
        confidence: float,
        category: str,
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        evidence_missing: Optional[str] = None,
        safe_next_step: Optional[str] = None,
        mind_changer: Optional[str] = None
    ) -> str:
        """
        Record a new prediction with confidence level.
        
        Args:
            statement: The prediction statement
            confidence: Confidence level (0.0 to 1.0)
            category: Category for grouping (e.g., "trading", "benchmark")
            source: Source of the prediction
            context: Additional context information
            evidence_missing: What evidence is missing
            safe_next_step: A safe next step if uncertain
            mind_changer: What would change your mind
            
        Returns:
            Prediction ID
        """
        pred = Prediction(
            id=str(uuid.uuid4()),
            statement=statement,
            confidence=max(0.0, min(1.0, confidence)),  # Clamp to [0, 1]
            category=category,
            source=source,
            context=context,
            evidence_missing=evidence_missing,
            safe_next_step=safe_next_step,
            mind_changer=mind_changer
        )
        self.predictions.append(pred)
        return pred.id
    
    def record_outcome(self, pred_id: str, outcome: bool) -> bool:
        """
        Record the actual outcome of a prediction.
        
        Args:
            pred_id: The prediction ID
            outcome: Whether the prediction was correct
            
        Returns:
            True if prediction was found and updated
        """
        for pred in self.predictions:
            if pred.id == pred_id and not pred.resolved:
                pred.resolved = True
                pred.outcome = outcome
                pred.resolved_at = datetime.now().isoformat()
                return True
        return False
    
    def get_prediction(self, pred_id: str) -> Optional[Dict]:
        """Get a prediction by ID."""
        for pred in self.predictions:
            if pred.id == pred_id:
                return pred.to_dict()
        return None
    
    def get_recent_predictions(self, limit: int = 10) -> List[Dict]:
        """Get recent predictions."""
        sorted_preds = sorted(
            self.predictions,
            key=lambda p: p.created_at,
            reverse=True
        )
        return [p.to_dict() for p in sorted_preds[:limit]]
    
    def get_unresolved_predictions(self) -> List[Dict]:
        """Get all unresolved predictions."""
        return [p.to_dict() for p in self.predictions if not p.resolved]
    
    def calculate_brier_score(self) -> float:
        """
        Calculate Brier score for all resolved predictions.
        
        Brier score ranges from 0 (perfect) to 1 (worst).
        Lower is better calibration.
        """
        resolved = [p for p in self.predictions if p.resolved]
        if not resolved:
            return 0.0
        
        total = 0.0
        for pred in resolved:
            outcome_val = 1.0 if pred.outcome else 0.0
            total += (pred.confidence - outcome_val) ** 2
        
        return total / len(resolved)
    
    def get_calibration_by_bin(self) -> Dict[str, Dict]:
        """
        Get calibration accuracy grouped by confidence bins.
        
        Returns:
            Dict mapping bin ranges to calibration metrics
        """
        resolved = [p for p in self.predictions if p.resolved]
        
        bins = {
            "0.8-1.0": [],
            "0.6-0.8": [],
            "0.4-0.6": [],
            "0.2-0.4": [],
            "0.0-0.2": []
        }
        
        for pred in resolved:
            if pred.confidence >= 0.8:
                bins["0.8-1.0"].append(pred)
            elif pred.confidence >= 0.6:
                bins["0.6-0.8"].append(pred)
            elif pred.confidence >= 0.4:
                bins["0.4-0.6"].append(pred)
            elif pred.confidence >= 0.2:
                bins["0.2-0.4"].append(pred)
            else:
                bins["0.0-0.2"].append(pred)
        
        result = {}
        for bin_range, preds in bins.items():
            if preds:
                avg_conf = sum(p.confidence for p in preds) / len(preds)
                correct = sum(1 for p in preds if p.outcome)
                actual_acc = correct / len(preds)
                
                result[bin_range] = {
                    "bin_range": bin_range,
                    "average_confidence": avg_conf,
                    "actual_accuracy": actual_acc,
                    "prediction_count": len(preds),
                    "calibration_error": abs(avg_conf - actual_acc)
                }
        
        return result
    
    def get_overall_calibration(self) -> Dict:
        """Get overall calibration statistics."""
        resolved = [p for p in self.predictions if p.resolved]
        correct = [p for p in resolved if p.outcome]
        
        brier = self.calculate_brier_score()
        calibration_by_bin = self.get_calibration_by_bin()
        
        # Calculate average calibration error across bins
        if calibration_by_bin:
            avg_error = sum(
                m["calibration_error"] for m in calibration_by_bin.values()
            ) / len(calibration_by_bin)
        else:
            avg_error = 0.0
        
        # Calculate overall accuracy
        overall_accuracy = len(correct) / len(resolved) if resolved else 0.0
        
        # Average confidence for resolved predictions
        avg_conf = sum(p.confidence for p in resolved) / len(resolved) if resolved else 0.0
        
        return {
            "total_predictions": len(self.predictions),
            "resolved_predictions": len(resolved),
            "correct_predictions": len(correct),
            "correct_rate": overall_accuracy,
            "brier_score": brier,
            "average_confidence": avg_conf,
            "calibration_error": avg_error,
            "average_calibration_by_bin": calibration_by_bin
        }
    
    def get_threshold_recommendations(self) -> Dict[str, float]:
        """
        Get recommended confidence thresholds based on historical calibration.
        
        Returns:
            Dict with high/medium/low confidence thresholds
        """
        bins = self.get_calibration_by_bin()
        
        if not bins:
            # Default thresholds if no data
            return {
                "high_confidence_threshold": 0.8,
                "medium_confidence_threshold": 0.5,
                "low_confidence_threshold": 0.2
            }
        
        # Find bins where confidence matches actual accuracy well
        well_calibrated = [
            (range_str, metrics) for range_str, metrics in bins.items()
            if metrics["calibration_error"] < 0.15  # Within 15%
        ]
        
        if well_calibrated:
            # Use the midpoint of well-calibrated bins
            # Sort by confidence range
            well_calibrated.sort(key=lambda x: x[1]["average_confidence"])
            mid = len(well_calibrated) // 2
            if well_calibrated:
                reference = well_calibrated[mid][1]
                ref_conf = reference["average_confidence"]
                ref_acc = reference["actual_accuracy"]
                
                # High: where confidence >= 0.7 and matches accuracy
                # Medium: where confidence ~ 0.5
                # Low: where confidence < 0.3
                return {
                    "high_confidence_threshold": 0.8,
                    "medium_confidence_threshold": 0.5,
                    "low_confidence_threshold": 0.2
                }
        
        # Fallback to data-driven thresholds
        high_preds = [p for p in self.predictions if p.confidence >= 0.8]
        med_preds = [p for p in self.predictions if 0.4 <= p.confidence < 0.6]
        low_preds = [p for p in self.predictions if p.confidence < 0.3]
        
        def get_accuracy(preds):
            resolved = [p for p in preds if p.resolved]
            if not resolved:
                return 0.0
            return sum(1 for p in resolved if p.outcome) / len(resolved)
        
        return {
            "high_confidence_threshold": 0.8,
            "medium_confidence_threshold": 0.5,
            "low_confidence_threshold": 0.2,
            "high_confidence_accuracy": get_accuracy(high_preds),
            "medium_confidence_accuracy": get_accuracy(med_preds),
            "low_confidence_accuracy": get_accuracy(low_preds)
        }
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive calibration report."""
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_overall_calibration(),
            "calibration_by_bin": self.get_calibration_by_bin(),
            "threshold_recommendations": self.get_threshold_recommendations(),
            "recent_predictions": self.get_recent_predictions(10),
            "unresolved_predictions": self.get_unresolved_predictions()
        }
    
    def to_json(self) -> str:
        """Export all predictions to JSON."""
        return json.dumps({
            "predictions": [p.to_dict() for p in self.predictions],
            "generated_at": datetime.now().isoformat()
        }, indent=2)
    
    def save(self) -> bool:
        """Save predictions to JSON file."""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            filepath = os.path.join(self.storage_path, "confidence_calibration.json")
            with open(filepath, 'w') as f:
                f.write(self.to_json())
            return True
        except Exception:
            return False
    
    def _load(self) -> bool:
        """Load predictions from JSON file."""
        try:
            filepath = os.path.join(self.storage_path, "confidence_calibration.json")
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    self.predictions = [
                        Prediction.from_dict(p) for p in data.get("predictions", [])
                    ]
                return True
        except Exception:
            pass
        return False
    
    def load(self) -> bool:
        """Public method to load predictions."""
        return self._load()
