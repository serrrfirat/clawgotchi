#!/usr/bin/env python3
"""
CLI for Clawgotchi Heartbeat Alerts.

Usage:
    clawgotchi heartbeat check [--verbose] [--json]
    clawgotchi heartbeat status
"""

import argparse
import sys
import json

from cognition.heartbeat_alerts import check_heartbeat


def cmd_check(args):
    """Run heartbeat check."""
    report = check_heartbeat(
        low_confidence_threshold=getattr(args, 'threshold', 0.5),
        stale_days=getattr(args, 'stale', 7),
        verbose=args.verbose
    )

    if args.json:
        print(json.dumps(report, indent=2))
    elif not args.verbose:
        # Default summary output
        summary = report['summary']
        print(f"Heartbeat: {summary['total_alerts']} alerts "
              f"(🔴{summary['high_severity']} "
              f"🟡{summary['medium_severity']} "
              f"🟢{summary['low_severity']})")

        if summary['high_severity'] > 0:
            print("\n⚠️  High severity alerts need attention!")
        elif summary['total_alerts'] == 0:
            print(" ✓ All assumptions healthy")


def cmd_status(args):
    """Quick status check."""
    report = check_heartbeat()

    summary = report['summary']
    status_emoji = "✅" if summary['total_alerts'] == 0 else "⚠️"
    print(f"{status_emoji} Heartbeat: {summary['total_alerts']} alerts")


def main():
    parser = argparse.ArgumentParser(
        description="Clawgotchi Heartbeat Alert System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clawgotchi heartbeat check              # Run heartbeat check
  clawgotchi heartbeat check --verbose   # Detailed output
  clawgotchi heartbeat check --json      # JSON output for scripts
  clawgotchi heartbeat status            # Quick health summary
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Check command
    check_parser = subparsers.add_parser('check', help='Run heartbeat check')
    check_parser.add_argument('--verbose', '-v', action='store_true',
                              help='Show detailed alert information')
    check_parser.add_argument('--json', action='store_true',
                              help='Output as JSON')
    check_parser.add_argument('--threshold', '-t', type=float, default=0.5,
                              help='Low confidence threshold (default: 0.5)')
    check_parser.add_argument('--stale', '-s', type=int, default=7,
                              help='Days before assumption is stale (default: 7)')

    # Status command
    status_parser = subparsers.add_parser('status', help='Quick health check')

    # Default: show help
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n🏥 Quick: Run heartbeat check")
        print("   clawgotchi heartbeat check")
        sys.exit(0)

    args = parser.parse_args()

    if args.command == 'check':
        cmd_check(args)
    elif args.command == 'status':
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
