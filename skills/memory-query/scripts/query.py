#!/usr/bin/env python3
"""Memory semantic search."""

import argparse
import re
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"

def search_memory(query: str, show_files: bool = False, context: int = 3) -> list:
    """Search memory files for query."""
    results = []
    
    for mem_file in MEMORY_DIR.glob("*.md"):
        text = mem_file.read_text()
        if query.lower() in text.lower():
            if show_files:
                results.append(str(mem_file))
            else:
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if query.lower() in line.lower():
                        # Get context
                        start = max(0, i - context)
                        end = min(len(lines), i + context + 1)
                        snippet = "\n".join(lines[start:end])
                        results.append(f"--- {mem_file.name} ---\n{snippet}\n")
    
    # Also check JSON files
    for json_file in MEMORY_DIR.glob("*.json"):
        if "curiosity" in json_file.name or "taste" in json_file.name:
            text = json_file.read_text()
            if query.lower() in text.lower():
                results.append(f"--- {json_file.name} ---\n{text[:500]}...\n")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Search clawgotchi memory")
    parser.add_argument("query", help="Search term")
    parser.add_argument("--files", action="store_true", help="List matching files only")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--context", type=int, default=3, help="Lines of context")
    
    args = parser.parse_args()
    
    results = search_memory(args.query, args.files, args.context)
    
    if args.json:
        import json
        print(json.dumps(results, indent=2))
    elif args.files:
        for f in results:
            print(f)
    else:
        for r in results:
            print(r)
        print(f"\n{len(results)} matches found")

if __name__ == "__main__":
    main()
