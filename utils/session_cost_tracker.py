"""Session Cost Tracker - Track API costs, tokens, and resource usage per session."""
import json
import os
from datetime import datetime
from typing import Optional
from pathlib import Path

COST_DATA_DIR = Path.home() / ".clawgotchi" / "costs"
COST_DATA_DIR.mkdir(parents=True, exist_ok=True)
COST_FILE = COST_DATA_DIR / "session_costs.json"

# Cost per 1M tokens (USD) - can be updated
MODEL_COSTS = {
    "openai/gpt-4o": {"input": 5.00, "output": 15.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "anthropic/claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "google/gemini-2-pro-flash": {"input": 0.10, "output": 0.40},
    "google/gemini-3-pro": {"input": 0.50, "output": 1.50},
    "default": {"input": 1.00, "output": 5.00},
}

DEFAULT_COSTS = MODEL_COSTS["default"]


def _load_costs() -> dict:
    """Load cost data from file."""
    if COST_FILE.exists():
        try:
            with open(COST_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"sessions": {}, "total_calls": 0, "total_cost_usd": 0.0}


def _save_costs(data: dict) -> None:
    """Save cost data to file."""
    with open(COST_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_api_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    session_id: str,
    feature: Optional[str] = None,
) -> float:
    """Record an API call and return the estimated cost in USD.
    
    Args:
        model: The model used (e.g., "openai/gpt-4o")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        session_id: Unique session identifier
        feature: Optional feature name for attribution
    
    Returns:
        Estimated cost in USD
    """
    costs = MODEL_COSTS.get(model, DEFAULT_COSTS)
    
    # Calculate cost: (tokens / 1M) * price
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    total_cost = input_cost + output_cost
    
    data = _load_costs()
    
    if session_id not in data["sessions"]:
        data["sessions"][session_id] = {
            "started_at": datetime.now().isoformat(),
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "features": {},
        }
    
    session = data["sessions"][session_id]
    session["calls"] += 1
    session["input_tokens"] += input_tokens
    session["output_tokens"] += output_tokens
    session["cost_usd"] += total_cost
    
    if feature:
        if feature not in session["features"]:
            session["features"][feature] = {"calls": 0, "cost_usd": 0.0}
        session["features"][feature]["calls"] += 1
        session["features"][feature]["cost_usd"] += total_cost
    
    data["total_calls"] += 1
    data["total_cost_usd"] += total_cost
    
    _save_costs(data)
    
    return total_cost


def get_session_summary(session_id: str) -> Optional[dict]:
    """Get cost summary for a specific session."""
    data = _load_costs()
    if session_id in data["sessions"]:
        return data["sessions"][session_id]
    return None


def get_all_time_stats() -> dict:
    """Get all-time cost statistics."""
    data = _load_costs()
    return {
        "total_calls": data["total_calls"],
        "total_cost_usd": data["total_cost_usd"],
        "session_count": len(data["sessions"]),
    }


def get_feature_costs(session_id: str) -> dict:
    """Get cost breakdown by feature for a session."""
    session = get_session_summary(session_id)
    if session:
        return session.get("features", {})
    return {}


def reset_session(session_id: str) -> bool:
    """Delete a session's cost data."""
    data = _load_costs()
    if session_id in data["sessions"]:
        # Subtract from totals
        session = data["sessions"][session_id]
        data["total_calls"] -= session["calls"]
        data["total_cost_usd"] -= session["cost_usd"]
        del data["sessions"][session_id]
        _save_costs(data)
        return True
    return False


def set_model_costs(model: str, input_cost: float, output_cost: float) -> None:
    """Update cost rates for a model."""
    MODEL_COSTS[model] = {"input": input_cost, "output": output_cost}
