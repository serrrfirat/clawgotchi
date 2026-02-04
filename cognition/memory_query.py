#!/usr/bin/env python3
"""
Memory Query System for Clawgotchi.

Provides semantic search and relationship mapping across memories:
- Full-text search across all memory files
- Entity extraction (people, concepts, projects)
- Concept relationship tracking over time
- Temporal queries (what did I learn on date X?)
- CLI for querying

Inspired by herbert_clawd's memory architecture question on Moltbook.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict


class MemoryQuery:
    """Query and analyze Clawgotchi's memory system."""

    def __init__(self, memory_dir=None):
        """Initialize query system."""
        self.memory_dir = memory_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'memory'
        )
        self._cache = {}
        
    def _get_memory_files(self):
        """Get all memory files to index."""
        files = []
        for f in Path(self.memory_dir).iterdir():
            if f.is_file() and not f.name.startswith('.'):
                # Skip JSONL taste rejections and non-markdown files
                if f.suffix == '.jsonl' or f.suffix not in ['.md', '.txt']:
                    continue
                files.append(f)
        return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def _read_file(self, filepath):
        """Read file contents with caching."""
        if filepath not in self._cache:
            with open(filepath, 'r', errors='ignore') as f:
                self._cache[filepath] = f.read()
        return self._cache[filepath]
    
    def search(self, query, max_results=10):
        """
        Full-text search across all memories.
        
        Args:
            query: Search term (supports regex)
            max_results: Maximum results to return
            
        Returns:
            List of dicts with {file, line, content, relevance}
        """
        results = []
        query_lower = query.lower()
        
        for filepath in self._get_memory_files():
            content = self._read_file(filepath)
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                if query_lower in line.lower():
                    # Calculate simple relevance score
                    score = 0
                    # Exact match in title/header
                    if line.strip().startswith('#'):
                        score += 3
                    # Title case match
                    if query in line:
                        score += 1
                    
                    results.append({
                        'file': filepath.name,
                        'line': line_num,
                        'content': line.strip()[:200],
                        'score': score,
                        'date': filepath.name.replace('.md', '')[:10]
                    })
        
        # Sort by score descending, then by file date
        results.sort(key=lambda x: (-x['score'], x['file']))
        return results[:max_results]
    
    def extract_entities(self):
        """
        Extract named entities (people, concepts, projects) from memories.
        
        Returns:
            Dict with {entities, projects, concepts}
        """
        entities = defaultdict(int)
        projects = set()
        concepts = set()
        
        # Project indicators
        project_patterns = [
            r'(?:built|created|made|shipped|launched)\s+(?:a|the|my)\s+(\w+(?:\s+\w+)?)',
            r'(?:project|feature|system|module)[:\s]+(\w+(?:\s+\w+)?)',
        ]
        
        # Concept indicators
        concept_patterns = [
            r'(?:learned|discovered|understood|explored)\s+(?:that|about)\s+(\w+(?:\s+\w+)?)',
            r'(?:principle|idea|pattern|approach)[:\s]+(\w+(?:\s+\w+)?)',
        ]
        
        for filepath in self._get_memory_files():
            content = self._read_file(filepath)
            lines = content.split('\n')
            
            for line in lines:
                # Extract potential entities (capitalized words or specific patterns)
                caps = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', line)
                for cap in caps:
                    if len(cap) > 3 and cap not in ['The', 'This', 'That', 'What', 'When', 'Where']:
                        entities[cap] += 1
                
                # Extract projects
                for pattern in project_patterns:
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    for m in matches:
                        if len(m) > 2:
                            projects.add(m.strip())
                
                # Extract concepts
                for pattern in concept_patterns:
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    for m in matches:
                        if len(m) > 2:
                            concepts.add(m.strip())
        
        return {
            'entities': dict(sorted(entities.items(), key=lambda x: -x[1])[:20]),
            'projects': list(sorted(projects)),
            'concepts': list(sorted(concepts))[:20]
        }
    
    def get_timeline(self, days=30):
        """
        Get timeline of activity from daily logs.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of dicts with {date, summary, actions}
        """
        timeline = []
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for filepath in self._get_memory_files():
            if filepath.stat().st_mtime < cutoff:
                break
            if not filepath.name.endswith('.md'):
                continue
                
            content = self._read_file(filepath)
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filepath.name)
            if not date_match:
                continue
            
            # Extract key actions from the log
            actions = []
            for line in content.split('\n'):
                stripped = line.strip()
                # Look for action items (bullets, dashes, numbered lists)
                if re.match(r'^[\-\*\d]+\.?\s', stripped):
                    action = re.sub(r'^[\-\*\d]+\.?\s+', '', stripped)[:100]
                    if action and len(action) > 10:
                        actions.append(action)
            
            # Extract first paragraph as summary
            summary = content.split('\n\n')[0].strip()[:200]
            summary = re.sub(r'^#+\s*', '', summary)
            
            timeline.append({
                'date': date_match.group(1),
                'summary': summary,
                'actions': actions[:5],
                'file': filepath.name
            })
        
        return timeline
    
    def find_related(self, concept, max_results=5):
        """
        Find memories related to a concept.
        
        Args:
            concept: The concept to search for
            max_results: Maximum results
            
        Returns:
            List of related memory entries
        """
        return self.search(concept, max_results=max_results)
    
    def get_concept_frequency(self):
        """
        Track how often concepts appear over time.
        
        Returns:
            Dict of {concept: [dates it appeared]}
        """
        frequency = defaultdict(list)
        
        for filepath in self._get_memory_files():
            if not filepath.name.endswith('.md'):
                continue
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filepath.name)
            if not date_match:
                continue
            date = date_match.group(1)
            
            content = self._read_file(filepath).lower()
            
            # Track key concepts
            concepts = ['taste', 'memory', 'identity', 'test', 'build', 
                       'ship', 'learn', 'feature', 'agent', 'moltbook']
            for concept in concepts:
                if concept in content:
                    frequency[concept].append(date)
        
        return {k: v for k, v in sorted(
            frequency.items(), key=lambda x: -len(x[1])
        ) if len(v) >= 1}


def run_query_command(args):
    """Execute query command from CLI."""
    query = MemoryQuery()
    
    if args.action == 'search':
        results = query.search(args.query, max_results=args.limit)
        if results:
            print(f"Found {len(results)} results for '{args.query}':\n")
            for r in results:
                print(f"  [{r['date']}] {r['file']}:{r['line']}")
                print(f"    {r['content'][:100]}...")
                print()
        else:
            print(f"No results found for '{args.query}'")
            
    elif args.action == 'entities':
        entities = query.extract_entities()
        print("Extracted Entities:\n")
        
        print("Top entities:")
        for entity, count in list(entities['entities'].items())[:10]:
            print(f"  {entity}: {count}")
        
        print("\nProjects mentioned:")
        for proj in entities['projects'][:10]:
            print(f"  -> {proj}")
        
        print("\nConcepts explored:")
        for conc in entities['concepts'][:10]:
            print(f"  * {conc}")
            
    elif args.action == 'timeline':
        timeline = query.get_timeline(days=args.days)
        print(f"Activity Timeline (last {args.days} days):\n")
        for entry in timeline[:15]:
            print(f"  {entry['date']}: {entry['summary'][:60]}...")
            for action in entry['actions'][:3]:
                print(f"    -> {action[:70]}")
            print()
            
    elif args.action == 'frequency':
        freq = query.get_concept_frequency()
        print("Concept Frequency:\n")
        for concept, dates in list(freq.items())[:10]:
            print(f"  {concept.capitalize()}: {len(dates)} entries")
            
    elif args.action == 'related':
        results = query.find_related(args.concept, max_results=args.limit)
        print(f"Memories related to '{args.concept}':\n")
        for r in results:
            print(f"  {r['date']} {r['file']}:{r['line']} - {r['content'][:50]}...")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Query and analyze Clawgotchi's memory system"
    )
    subparsers = parser.add_subparsers(dest='action', help='Query action')
    
    # search
    search_p = subparsers.add_parser('search', help='Search memories')
    search_p.add_argument('query', help='Search term')
    search_p.add_argument('--limit', type=int, default=10, help='Max results')
    
    # entities
    subparsers.add_parser('entities', help='Extract entities from memories')
    
    # timeline
    timeline_p = subparsers.add_parser('timeline', help='Show activity timeline')
    timeline_p.add_argument('--days', type=int, default=30)
    
    # frequency
    subparsers.add_parser('frequency', help='Show concept frequency')
    
    # related
    related_p = subparsers.add_parser('related', help='Find related memories')
    related_p.add_argument('concept', help='Concept to find')
    related_p.add_argument('--limit', type=int, default=5)
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        print("\nExamples:")
        print("   python3 memory_query.py search taste")
        print("   python3 memory_query.py entities")
        print("   python3 memory_query.py timeline --days 7")
        sys.exit(0)
    
    run_query_command(args)


if __name__ == '__main__':
    import sys
    main()
