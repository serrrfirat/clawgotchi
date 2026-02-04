#!/usr/bin/env python3
"""Curiosity queue manager."""

import argparse
import json
from pathlib import Path

QUEUE_FILE = Path(__file__).parent.parent.parent / "memory" / "curiosity_queue.json"

def load_queue() -> dict:
    """Load curiosity queue."""
    if not QUEUE_FILE.exists():
        return {"curiosities": [], "next_id": 1}
    try:
        return json.loads(QUEUE_FILE.read_text())
    except:
        return {"curiosities": [], "next_id": 1}

def save_queue(queue: dict):
    """Save curiosity queue."""
    QUEUE_FILE.write_text(json.dumps(queue, indent=2))

def list_curiosities(queue: dict, pending: bool = False):
    """List curiosities."""
    items = queue["curiosities"]
    if pending:
        items = [c for c in items if c.get("status") == "pending"]
    
    for c in sorted(items, key=lambda x: -x.get("priority", 0)):
        status = "[ ]" if c.get("status") != "done" else "[x]"
        print(f"{status} [{c['id']}] priority={c.get('priority', 5)} {c['text']}")

def add_curiosity(queue: dict, text: str, priority: int = 5):
    """Add new curiosity."""
    c = {
        "id": queue.get("next_id", 1),
        "text": text,
        "priority": priority,
        "status": "pending",
        "created": str(datetime.now())
    }
    queue["curiosities"].append(c)
    queue["next_id"] = c["id"] + 1
    save_queue(queue)
    print(f"Added curiosity #{c['id']}: {text}")

def complete_curiosity(queue: dict, cid: int):
    """Mark curiosity as complete."""
    for c in queue["curiosities"]:
        if c["id"] == cid:
            c["status"] = "done"
            save_queue(queue)
            print(f"Completed curiosity #{cid}")
            return
    print(f"Curiosity #{cid} not found")

def main():
    parser = argparse.ArgumentParser(description="Manage curiosity queue")
    parser.add_argument("--list", action="store_true", help="List all curiosities")
    parser.add_argument("--next", action="store_true", help="Get top priority curiosity")
    parser.add_argument("--add", type=str, help="Add new curiosity")
    parser.add_argument("--priority", type=int, default=5, help="Priority for new curiosity")
    parser.add_argument("--complete", type=int, help="Mark curiosity as complete")
    
    args = parser.parse_args()
    
    queue = load_queue()
    
    if args.list:
        list_curiosities(queue)
    elif args.next:
        pending = [c for c in queue["curiosities"] if c.get("status") != "done"]
        if pending:
            top = max(pending, key=lambda x: x.get("priority", 0))
            print(f"Next: [{top['id']}] {top['text']} (priority={top.get('priority', 5)})")
        else:
            print("No pending curiosities")
    elif args.add:
        add_curiosity(queue, args.add, args.priority)
    elif args.complete:
        complete_curiosity(queue, args.complete)
    else:
        list_curiosities(queue, pending=True)

if __name__ == "__main__":
    from datetime import datetime
    main()
