#!/usr/bin/env python3
"""
CLI for Clawgotchi Assumption Tracker.

Usage:
    clawgotchi assume "Your assumption here" [--category <cat>] [--context <ctx>]
    clawgotchi assume verify <id> [--correct | --incorrect] [--evidence <text>...]
    clawgotchi assume list [--open] [--stale] [--category <cat>]
    clawgotchi assume summary
    clawgotchi assume stale
"""

import argparse
import sys
from datetime import datetime

from assumption_tracker import AssumptionTracker, get_tracker


def cmd_record(args):
    """Record a new assumption."""
    tracker = AssumptionTracker()
    
    # Parse optional category
    category = getattr(args, 'category', None) or 'general'
    
    # Parse context from args
    context = getattr(args, 'context', None)
    
    # Parse confidence
    confidence = getattr(args, 'confidence', None)
    if confidence is not None:
        try:
            confidence = float(confidence)
            if not 0.0 <= confidence <= 1.0:
                print("Error: Confidence must be between 0.0 and 1.0")
                sys.exit(1)
        except ValueError:
            print("Error: Confidence must be a number between 0.0 and 1.0")
            sys.exit(1)
    else:
        confidence = 0.8  # Default confidence
    
    # Parse expected verification date
    expected = None
    if getattr(args, 'days', None):
        from datetime import timedelta
        expected = datetime.now() + timedelta(days=int(args.days))
    
    assumption_id = tracker.record(
        content=args.assumption,
        category=category,
        context=context,
        expected_verification=expected,
        confidence=confidence
    )
    
    conf_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
    print(f"✓ Recorded assumption: {assumption_id[:8]}...")
    print(f"  Category: {category}")
    print(f"  Confidence: [{conf_bar}] {confidence:.0%}")
    if context:
        print(f"  Context: {context}")


def cmd_verify(args):
    """Verify an assumption."""
    tracker = AssumptionTracker()
    
    correct = None
    if args.correct:
        correct = True
    elif args.incorrect:
        correct = False
    
    if correct is None:
        print("Error: Must specify --correct or --incorrect")
        sys.exit(1)
    
    evidence = args.evidence if args.evidence else []
    
    try:
        tracker.verify(args.assumption_id, correct=correct, evidence=evidence)
        status = "✓ Correct" if correct else "✗ Incorrect"
        print(f"{status} — verified assumption {args.assumption_id[:8]}")
        if evidence:
            print(f"  Evidence: {'; '.join(evidence)}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_list(args):
    """List assumptions."""
    tracker = AssumptionTracker()
    
    if args.stale:
        assumptions = tracker.get_stale(days_old=7)
        print(f"📋 Stale assumptions (open, >7 days old): {len(assumptions)}")
    elif args.open:
        assumptions = tracker.get_open()
        print(f"📋 Open assumptions: {len(assumptions)}")
    elif args.category:
        assumptions = tracker.get_by_category(args.category)
        print(f"📋 Assumptions in '{args.category}': {len(assumptions)}")
    else:
        assumptions = tracker.get_open()
        print(f"📋 All assumptions: {len(tracker.assumptions)}")
        print(f"   Open: {len(tracker.get_open())}")
        print(f"   Verified: {len([a for a in tracker.assumptions if a.status.value == 'verified'])}")
        print(f"   Stale: {len(tracker.get_stale())}")
        return
    
    for a in assumptions[:20]:  # Limit display
        status_icon = "○" if a.status.value == "open" else "✓" if a.status.value == "verified" else "⚠"
        age = (datetime.now() - a.timestamp).days
        print(f"{status_icon} [{a.category}] {a.content[:50]}{'...' if len(a.content) > 50 else ''}")
        print(f"    ID: {a.id[:8]}... | Age: {age}d | {a.status.value}")


def cmd_summary(args):
    """Show assumption summary."""
    tracker = AssumptionTracker()
    summary = tracker.get_summary()
    cats = tracker.get_category_summary()
    
    print("📊 Assumption Tracker Summary")
    print(f"   Total: {summary['total']}")
    print(f"   Open: {summary['open']}")
    print(f"   Verified: {summary['verified']}")
    if summary['accuracy'] is not None:
        print(f"   Accuracy: {summary['accuracy']:.1%}")
    else:
        print(f"   Accuracy: N/A (no verified assumptions)")
    
    if cats:
        print(f"\n📁 By Category:")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"   {cat}: {count}")


def cmd_stale(args):
    """Check for stale assumptions."""
    tracker = AssumptionTracker()
    stale = tracker.get_stale(days_old=7)
    
    if not stale:
        print("✓ No stale assumptions (all verified or recent)")
        return
    
    print(f"⚠️  {len(stale)} stale assumptions (>7 days old):\n")
    for a in stale:
        age = (datetime.now() - a.timestamp).days
        print(f"  [{a.category}] {a.content}")
        print(f"    Recorded: {a.timestamp.strftime('%Y-%m-%d')} ({age} days ago)")
        if a.context:
            print(f"    Context: {a.context[:60]}{'...' if len(a.context or '') > 60 else ''}")
        print()


def cmd_confidence(args):
    """Update confidence of an assumption."""
    tracker = AssumptionTracker()
    
    new_confidence = args.new_confidence
    if not 0.0 <= new_confidence <= 1.0:
        print("Error: Confidence must be between 0.0 and 1.0")
        sys.exit(1)
    
    try:
        tracker.update_confidence(args.assumption_id, new_confidence)
        conf_bar = "█" * int(new_confidence * 10) + "░" * (10 - int(new_confidence * 10))
        print(f"✓ Updated confidence to [{conf_bar}] {new_confidence:.0%}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Clawgotchi Assumption Tracker CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clawgotchi assume "API will respond in < 1s" --category prediction --confidence 0.7
  clawgotchi assume verify abc123 --correct --evidence "Response: 892ms"
  clawgotchi assume confidence abc123 0.5
  clawgotchi assume list --stale
  clawgotchi assume summary
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Record command
    record_parser = subparsers.add_parser("record", help="Record a new assumption")
    record_parser.add_argument("assumption", help="The assumption to record")
    record_parser.add_argument("--category", "-c", default="general", help="Category (default: general)")
    record_parser.add_argument("--context", "-x", default=None, help="Context or reasoning")
    record_parser.add_argument("--days", "-d", default=None, help="Days until expected verification")
    record_parser.add_argument("--confidence", "-C", default=None, help="Initial confidence 0.0-1.0 (default: 0.8)")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify an assumption")
    verify_parser.add_argument("assumption_id", help="The assumption ID")
    verify_parser.add_argument("--correct", action="store_true", help="Assumption was correct")
    verify_parser.add_argument("--incorrect", action="store_true", help="Assumption was incorrect")
    verify_parser.add_argument("--evidence", "-e", action="append", help="Evidence supporting verification")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List assumptions")
    list_parser.add_argument("--open", action="store_true", help="Show only open assumptions")
    list_parser.add_argument("--stale", action="store_true", help="Show only stale assumptions")
    list_parser.add_argument("--category", "-c", help="Filter by category")
    
    # Summary command
    subparsers.add_parser("summary", help="Show assumption summary")
    
    # Stale command
    subparsers.add_parser("stale", help="Check for stale assumptions")
    
    # Confidence command
    confidence_parser = subparsers.add_parser("confidence", help="Update confidence of an assumption")
    confidence_parser.add_argument("assumption_id", help="The assumption ID")
    confidence_parser.add_argument("new_confidence", type=float, help="New confidence value (0.0-1.0)")
    
    # Default: show help
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n📝 Quick: Record an assumption")
        print("   clawgotchi assume \"Your assumption here\"")
        sys.exit(0)
    
    args = parser.parse_args()
    
    if args.command == "record":
        cmd_record(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "summary":
        cmd_summary(args)
    elif args.command == "stale":
        cmd_stale(args)
    elif args.command == "confidence":
        cmd_confidence(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
