#!/usr/bin/env python3
"""
CLI commands for memory curation.

Usage:
    clawgotchi memory summarize [--days N] [--json]
    clawgotchi memory promote "Your insight here" [--category C]
    clawgotchi memory show
    clawgotchi memory search <query>
    clawgotchi memory stats
    clawgotchi memory diagnose
"""

import sys
import argparse
from memory_curation import MemoryCuration, MemoryConsistencyChecker
from memory_decay import MemoryAccessTracker


def run_memory_command(args):
    """Execute memory command."""
    curation = MemoryCuration()
    
    # Initialize memory access tracker for all commands
    tracker = MemoryAccessTracker()

    if args.command == 'summarize':
        insights = curation.extract_insights_from_logs(days=args.days)

        # Track access to daily logs when summarizing
        for insight in insights:
            if 'file' in insight:
                tracker.record_access(insight['file'], source="summarize")

        if args.json:
            import json
            print(json.dumps(insights, indent=2))
        else:
            if insights:
                print("📚 Insights from recent logs:")
                print("-" * 40)
                for i, insight in enumerate(insights, 1):
                    print(f"{i}. [{insight['source']}] {insight['text']}")
            else:
                print("No insights found in recent logs.")

    elif args.command == 'promote':
        curation.promote_insight(args.insight, category=args.category)
        print(f"✓ Promoted to long-term memory: {args.insight}")
        
        # Track the new curated memory entry
        tracker.record_access("curated_memory.md", source="promote")

    elif args.command == 'show':
        content = curation.show_curated_memory()
        print(content)
        
        # Track access to curated memory
        tracker.record_access("curated_memory.md", source="show")

    elif args.command == 'search':
        results = curation.search_memories(args.query)
        if results:
            print(f"🔍 Results for '{args.query}':")
            for r in results:
                print(f"  {r}")
            
            # Track search access for the curated memory
            tracker.record_access("curated_memory.md", source="search")
        else:
            print(f"No results found for '{args.query}'")

    elif args.command == 'stats':
        stats = curation.get_memory_stats()
        print("📊 Memory Stats:")
        print(f"  Daily logs: {stats['daily_logs']}")
        print(f"  Curated entries: {stats['curated_entries']}")
        print(f"  Last curated: {stats['last_curated'] or 'Never'}")

    elif args.command == 'diagnose':
        checker = MemoryConsistencyChecker(memory_dir=curation.memory_dir)
        checker.print_diagnostic_report()
        
        # Diagnose doesn't track memory access - it's for maintenance only


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clawgotchi Memory Curation System"
    )

    # Create subparsers
    subparsers = parser.add_subparsers(
        dest='command',
        help='Command to run'
    )

    # clawgotchi memory summarize
    summarize_parser = subparsers.add_parser(
        'summarize',
        help='Extract insights from recent daily logs'
    )
    summarize_parser.add_argument(
        '--days', type=int, default=7,
        help='Number of days to look back (default: 7)'
    )
    summarize_parser.add_argument(
        '--json', action='store_true',
        help='Output as JSON for scripts'
    )

    # clawgotchi memory promote "insight"
    promote_parser = subparsers.add_parser(
        'promote',
        help='Promote an insight to long-term memory'
    )
    promote_parser.add_argument(
        'insight',
        help='The insight to promote to long-term memory'
    )
    promote_parser.add_argument(
        '--category', '-c',
        default='General',
        help='Category for the insight'
    )

    # clawgotchi memory show
    subparsers.add_parser(
        'show',
        help='Show curated long-term memory'
    )

    # clawgotchi memory search <query>
    search_parser = subparsers.add_parser(
        'search',
        help='Search through curated memories'
    )
    search_parser.add_argument(
        'query',
        help='Search term'
    )

    # clawgotchi memory stats
    subparsers.add_parser(
        'stats',
        help='Show memory statistics'
    )

    # clawgotchi memory diagnose
    subparsers.add_parser(
        'diagnose',
        help='Run consistency diagnostics on memory files'
    )

    # Default: show help
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n💡 Quick: Summarize recent insights")
        print("   python3 cli_memory.py summarize")
        print("💡 Quick: Promote an insight")
        print("   python3 cli_memory.py promote \"Your insight here\"")
        sys.exit(0)

    args = parser.parse_args()

    if hasattr(args, 'command') and args.command:
        run_memory_command(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
