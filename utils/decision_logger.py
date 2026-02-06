"""
Decision Logger - Captures rationale behind heartbeat choices.

Addresses the memory/compression problem by explicitly logging decision rationale.
Each heartbeat records: trigger, options considered, chosen option, and WHY.
"""

import json
import os
from datetime import datetime
from typing import Optional


class DecisionLogger:
    """Captures and queries decision rationale for heartbeat sessions."""
    
    def __init__(self, log_file: str = "memory/decisions.jsonl"):
        self.log_file = log_file
        self.decisions = []
        self._load_existing()
    
    def _load_existing(self):
        """Load existing decisions from file."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            self.decisions.append(json.loads(line))
            except (json.JSONDecodeError, IOError):
                self.decisions = []
    
    def log(self, trigger: str, options_considered: list, chosen: str, 
            rationale: str, context: dict = None) -> dict:
        """Log a decision with full context.
        
        Args:
            trigger: What triggered this decision (e.g., "heartbeat", "inspiration")
            options_considered: List of options that were evaluated
            chosen: The option that was selected
            rationale: The reasoning behind the choice
            context: Additional context (session, theme, source, etc.)
            
        Returns:
            The logged decision dict
        """
        decision = {
            "timestamp": datetime.utcnow().isoformat(),
            "trigger": trigger,
            "options_considered": options_considered,
            "chosen": chosen,
            "rationale": rationale,
            "context": context or {}
        }
        self.decisions.append(decision)
        return decision
    
    def flush(self):
        """Persist decisions to file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        with open(self.log_file, 'a') as f:
            for decision in self.decisions:
                f.write(json.dumps(decision) + '\n')
    
    def query(self, **filters) -> list:
        """Query decisions by context fields.
        
        Example:
            decisions = logger.query(theme="memory", source="moltbook")
        """
        results = []
        for decision in self.decisions:
            match = True
            for key, value in filters.items():
                if decision.get("context", {}).get(key) != value:
                    match = False
                    break
            if match:
                results.append(decision)
        return results
    
    def get_last_rationale(self) -> Optional[str]:
        """Get the rationale from the most recent decision."""
        if not self.decisions:
            return None
        return self.decisions[-1]["rationale"]
    
    def get_history(self, limit: int = 10) -> list:
        """Get recent decisions."""
        return self.decisions[-limit:]
