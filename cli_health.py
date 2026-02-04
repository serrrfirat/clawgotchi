#!/usr/bin/env python3
"""
CLI commands for Clawgotchi health monitoring.

Usage:
    clawgotchi health              # Show full health report
    clawgotchi health --json       # JSON output for scripts
    clawgotchi health --watch     # Watch mode (refresh every 5s)
    clawgotchi health quick       # Quick status check
    clawgotchi health diagnose    # Full diagnostic with fixes
"""

import sys
import argparse
import time
from health_checker import HealthChecker


def run_health_command(args):
    """Execute health command."""
    checker = HealthChecker()
    
    if args.command == 'quick':
        # Quick status - just show score and status
        results = checker.run_all_checks()
        emoji = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}
        print(f"{emoji.get(results['status'], '⚪')} Clawgotchi: {results['status'].upper()} ({results['score']}/100)")
        if results['issues']:
            print(f"   Issues: {len(results['issues'])}")
        return
    
    if args.json:
        import json
        results = checker.run_all_checks()
        print(json.dumps(results, indent=2))
        return
    
    if args.watch:
        import os
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(checker.get_health_summary())
                print("\n[Press Ctrl+C to exit]")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopping health watch...")
        return
    
    if args.command == 'diagnose':
        # Full diagnostic with auto-fix suggestions
        results = checker.run_all_checks()
        
        print("🔍 Full Diagnostic Report")
        print("=" * 50)
        print(checker.get_health_summary())
        print("=" * 50)
        print("\n📋 Recommendations:")
        
        issues_found = False
        
        if results['status'] in ['critical', 'degraded']:
            issues_found = True
            print("\n   Priority Actions:")
            for i, issue in enumerate(results['issues'], 1):
                print(f"   {i}. {issue}")
        
        if results['warnings']:
            issues_found = True
            print("\n   Warnings to Address:")
            for w in results['warnings']:
                print(f"   - {w}")
        
        if not issues_found:
            print("   ✅ No issues found! System is healthy.")
        
        return
    
    # Default: full health report
    print(checker.get_health_summary())


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clawgotchi Health Monitoring System"
    )
    
    subparsers = parser.add_subparsers(
        dest='command',
        help='Command to run'
    )
    
    # Main health command
    health_parser = subparsers.add_parser(
        'health',
        help='Show health status'
    )
    health_parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output as JSON'
    )
    health_parser.add_argument(
        '--watch', '-w',
        action='store_true',
        help='Watch mode (continuous monitoring)'
    )
    
    # Quick status
    subparsers.add_parser(
        'quick',
        help='Quick status check (score + status)'
    )
    
    # Full diagnostic
    diagnose_parser = subparsers.add_parser(
        'diagnose',
        help='Full diagnostic with recommendations'
    )
    
    # Default: show help
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n💡 Quick: Check health status")
        print("   clawgotchi health")
        print("💡 Quick: JSON output for scripts")
        print("   clawgotchi health --json")
        print("💡 Quick: Watch mode")
        print("   clawgotchi health --watch")
        print("💡 Quick: Full diagnostic")
        print("   clawgotchi health diagnose")
        sys.exit(0)
    
    args = parser.parse_args()
    
    if hasattr(args, 'command') and args.command:
        run_health_command(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
