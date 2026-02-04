"""
Heartbeat Alert System for Clawgotchi.

Checks assumptions for conditions that need attention:
- Low confidence assumptions
- Stale assumptions (not verified in N days)
"""
import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Alert:
    """Represents an alert about an assumption."""
    id: str
    type: str
    severity: str  # low, medium, high
    message: str
    assumption_id: str
    assumption_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertEngine:
    """Engine for checking assumptions and generating alerts."""

    DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.5
    DEFAULT_STALE_DAYS = 7

    def __init__(
        self,
        assumptions_path: str = None,
        low_confidence_threshold: float = None,
        stale_days: int = None
    ):
        self.assumptions_path = assumptions_path or self._default_assumptions_path()
        self.low_confidence_threshold = low_confidence_threshold or self.DEFAULT_LOW_CONFIDENCE_THRESHOLD
        self.stale_days = stale_days or self.DEFAULT_STALE_DAYS

    def _default_assumptions_path(self) -> str:
        """Find the assumptions.json file."""
        from config import ASSUMPTIONS_FILE
        return str(ASSUMPTIONS_FILE)

    def load_assumptions(self) -> List[Dict[str, Any]]:
        """Load assumptions from JSON file."""
        if not os.path.exists(self.assumptions_path):
            return []

        with open(self.assumptions_path, 'r') as f:
            data = json.load(f)
            return data.get('assumptions', [])

    def check_low_confidence(self, assumptions: List[Dict[str, Any]]) -> List[Alert]:
        """Generate alerts for assumptions with low confidence."""
        alerts = []

        for assumption in assumptions:
            if assumption.get('status') != 'open':
                continue

            confidence = assumption.get('confidence', 1.0)

            if confidence < self.low_confidence_threshold:
                severity = 'high' if confidence < 0.3 else 'medium'
                alerts.append(Alert(
                    id=f"low_conf_{assumption['id'][:8]}",
                    type='low_confidence',
                    severity=severity,
                    message=f"Assumption has low confidence ({confidence:.0%})",
                    assumption_id=assumption['id'],
                    assumption_content=assumption['content'],
                    metadata={'confidence': confidence, 'threshold': self.low_confidence_threshold}
                ))

        return alerts

    def check_stale(self, assumptions: List[Dict[str, Any]]) -> List[Alert]:
        """Generate alerts for assumptions that haven't been verified recently."""
        alerts = []
        cutoff_date = datetime.now() - timedelta(days=self.stale_days)

        for assumption in assumptions:
            if assumption.get('status') != 'open':
                continue

            timestamp_str = assumption.get('timestamp', '')
            if not timestamp_str:
                continue

            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                continue

            if timestamp < cutoff_date:
                days_old = (datetime.now() - timestamp).days
                severity = 'medium' if days_old < 14 else 'high'

                alerts.append(Alert(
                    id=f"stale_{assumption['id'][:8]}",
                    type='stale',
                    severity=severity,
                    message=f"Assumption is stale ({days_old} days old)",
                    assumption_id=assumption['id'],
                    assumption_content=assumption['content'],
                    metadata={'days_old': days_old, 'stale_threshold': self.stale_days}
                ))

        return alerts

    def run_check(self) -> Dict[str, Any]:
        """Run all checks and return alert report."""
        assumptions = self.load_assumptions()

        low_conf_alerts = self.check_low_confidence(assumptions)
        stale_alerts = self.check_stale(assumptions)

        all_alerts = low_conf_alerts + stale_alerts

        # Categorize by severity
        by_severity = {'high': [], 'medium': [], 'low': []}
        for alert in all_alerts:
            by_severity[alert.severity].append(alert)

        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_alerts': len(all_alerts),
                'high_severity': len(by_severity['high']),
                'medium_severity': len(by_severity['medium']),
                'low_severity': len(by_severity['low']),
            },
            'alerts': [a.__dict__ for a in all_alerts],
            'by_severity': {
                'high': [a.__dict__ for a in by_severity['high']],
                'medium': [a.__dict__ for a in by_severity['medium']],
                'low': [a.__dict__ for a in by_severity['low']],
            }
        }


def check_heartbeat(
    assumptions_path: str = None,
    low_confidence_threshold: float = 0.5,
    stale_days: int = 7,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Main function to check assumptions and generate heartbeat alerts.

    Args:
        assumptions_path: Path to assumptions.json
        low_confidence_threshold: Threshold below which confidence is considered low
        stale_days: Number of days after which an assumption is considered stale
        verbose: Print detailed output

    Returns:
        Alert report dictionary
    """
    engine = AlertEngine(
        assumptions_path=assumptions_path,
        low_confidence_threshold=low_confidence_threshold,
        stale_days=stale_days
    )

    report = engine.run_check()

    if verbose:
        print(f"Heartbeat Check - {report['timestamp']}")
        print(f"Total Alerts: {report['summary']['total_alerts']}")
        print(f"  🔴 High: {report['summary']['high_severity']}")
        print(f"  🟡 Medium: {report['summary']['medium_severity']}")
        print(f"  🟢 Low: {report['summary']['low_severity']}")

        if report['alerts']:
            print("\nAlerts:")
            for alert in report['alerts']:
                print(f"  [{alert['severity'].upper()}] {alert['message']}")
                print(f"    → {alert['assumption_content'][:60]}...")

    return report


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Check Clawgotchi heartbeat alerts')
    parser.add_argument('--path', '-p', help='Path to assumptions.json')
    parser.add_argument('--threshold', '-t', type=float, default=0.5,
                        help='Low confidence threshold (default: 0.5)')
    parser.add_argument('--stale', '-s', type=int, default=7,
                        help='Days before assumption is stale (default: 7)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed output')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')

    args = parser.parse_args()

    report = check_heartbeat(
        assumptions_path=args.path,
        low_confidence_threshold=args.threshold,
        stale_days=args.stale,
        verbose=args.verbose
    )

    if args.json:
        print(json.dumps(report, indent=2))
    elif not args.verbose:
        # Default: show summary
        print(f"Alerts: {report['summary']['total_alerts']} "
              f"(🔴{report['summary']['high_severity']} "
              f"🟡{report['summary']['medium_severity']})")
