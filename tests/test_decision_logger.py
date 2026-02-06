"""
Test for Decision Logger - captures rationale behind heartbeat choices.
"""

import pytest
import json
import os
from datetime import datetime, timedelta


class DecisionLogger:
    """Captures and queries decision rationale for heartbeat sessions."""
    
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.decisions = []
        self._load_existing()
    
    def _load_existing(self):
        """Load existing decisions from file."""
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        self.decisions.append(json.loads(line))
    
    def log(self, trigger: str, options_considered: list, chosen: str, 
            rationale: str, context: dict):
        """Log a decision with full context."""
        decision = {
            "timestamp": datetime.utcnow().isoformat(),
            "trigger": trigger,
            "options_considered": options_considered,
            "chosen": chosen,
            "rationale": rationale,
            "context": context
        }
        self.decisions.append(decision)
    
    def flush(self):
        """Persist decisions to file."""
        with open(self.log_file, 'a') as f:
            for decision in self.decisions:
                f.write(json.dumps(decision) + '\n')
    
    def query(self, **filters) -> list:
        """Query decisions by context fields."""
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
    
    def get_last_rationale(self) -> str:
        """Get the rationale from the most recent decision."""
        if not self.decisions:
            return None
        return self.decisions[-1]["rationale"]


@pytest.fixture
def decision_logger(tmp_path):
    """Create a decision logger with a temporary file."""
    log_file = tmp_path / "decisions.jsonl"
    return DecisionLogger(log_file=str(log_file))


def test_log_decision_structure(decision_logger):
    """Test that a logged decision has all required fields."""
    decision_logger.log(
        trigger="heartbeat",
        options_considered=["option_a", "option_b", "option_c"],
        chosen="option_a",
        rationale="Option A was selected because it aligned with the current priority of memory management.",
        context={"session": 700, "theme": "memory"}
    )
    
    assert len(decision_logger.decisions) == 1
    decision = decision_logger.decisions[0]
    assert "timestamp" in decision
    assert decision["trigger"] == "heartbeat"
    assert decision["options_considered"] == ["option_a", "option_b", "option_c"]
    assert decision["chosen"] == "option_a"
    assert "rationale" in decision
    assert decision["context"]["session"] == 700


def test_query_decisions_by_context(decision_logger):
    """Test querying decisions by context fields."""
    # Log several decisions
    decision_logger.log("heartbeat", ["a", "b"], "a", "reason a", {"theme": "memory"})
    decision_logger.log("heartbeat", ["c", "d"], "c", "reason c", {"theme": "memory"})
    decision_logger.log("heartbeat", ["e", "f"], "f", "reason f", {"theme": "exploration"})
    
    memory_decisions = decision_logger.query(theme="memory")
    assert len(memory_decisions) == 2
    
    exploration_decisions = decision_logger.query(theme="exploration")
    assert len(exploration_decisions) == 1


def test_persistence(decision_logger):
    """Test that decisions persist to file."""
    decision_logger.log("test", ["x", "y"], "x", "test rationale", {})
    decision_logger.flush()
    
    # Create new logger instance (simulating new session)
    new_logger = DecisionLogger(log_file=decision_logger.log_file)
    
    assert len(new_logger.decisions) == 1
    assert new_logger.decisions[0]["chosen"] == "x"
    assert new_logger.decisions[0]["rationale"] == "test rationale"


def test_get_last_rationale(decision_logger):
    """Test retrieving the rationale from the most recent decision."""
    decision_logger.log("first", ["a"], "a", "first reason", {})
    decision_logger.log("second", ["b"], "b", "second reason", {})
    
    last_rationale = decision_logger.get_last_rationale()
    assert "second reason" == last_rationale


def test_reasoning_preserved_across_sessions(decision_logger):
    """Test that reasoning survives simulated context compression."""
    # Simulate the original rationale being preserved
    decision_logger.log(
        trigger="inspiration",
        options_considered=["build_feature_x", "build_feature_y", "rest"],
        chosen="build_feature_x",
        rationale="Chose feature_x because it addresses the memory compression problem observed in Moltbook posts",
        context={"source": "moltbook_feed", "posts_analyzed": 20}
    )
    
    # Query and verify the full reasoning is intact
    decisions = decision_logger.query(source="moltbook_feed")
    assert len(decisions) == 1
    assert "memory compression" in decisions[0]["rationale"]
