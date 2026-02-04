"""
Test suite for memory_audit.py
Memory Audit Utility - Distills insights from daily memory files
"""

import pytest
import os
import tempfile
from datetime import date, timedelta
from unittest.mock import patch, MagicMock


def test_parse_wake_cycles():
    """Test parsing wake cycle entries from memory content"""
    from memory_audit import parse_wake_cycles
    
    content = """## Wake Cycle #575 (2026-02-04 21:38)
- Action: JSON Escape Utility
- Result: 10 tests, all passing
- Health: 97/100

## Wake Cycle #576 (2026-02-04 21:45)
- Action: Curating memories
- Result: Curated memories: 2 found, 1 promoted
- Health: 95/100
"""
    cycles = parse_wake_cycles(content)
    assert len(cycles) == 2
    assert cycles[0]['cycle'] == '#575'
    assert 'JSON Escape Utility' in cycles[0]['action']
    assert cycles[0]['health'] == '97/100'


def test_extract_key_metrics():
    """Test extraction of key metrics from content"""
    from memory_audit import extract_key_metrics
    
    content = """
- Tests: All json_escape tests passing (10/10)
- Git: 6 commits today (local, remote needs config)
- Health: 97/100
- Total: 82 new tests across 6 features
"""
    metrics = extract_key_metrics(content)
    assert 'tests' in metrics
    assert 'commits' in metrics
    assert metrics['tests'] == '10/10'
    assert metrics['commits'] == '6'


def test_detect_patterns():
    """Test detection of repeating patterns in memory"""
    from memory_audit import detect_patterns
    
    content = """
- Action: Curating memories
- Result: Curated memories: 0 found, 0 promoted

- Action: Curating memories  
- Result: Curated memories: 0 found, 0 promoted

- Action: Verifying assumptions
- Result: Verified assumptions: 2 open, 0 stale, 0 expired
"""
    patterns = detect_patterns(content)
    assert 'curating memories' in patterns
    assert patterns['curating memories']['count'] >= 2


def test_generate_audit_summary():
    """Test generating a full audit summary"""
    from memory_audit import generate_audit_summary
    
    mock_files = {
        'memory/2026-02-04.md': """
# Daily Memory - Feb 4, 2026

## Today's Accomplishments
- JSON Escape Utility (10 tests)
- Permission Manifest Scanner (19 tests)

## Wake Cycles
## Wake Cycle #575 (2026-02-04 21:38)
- Action: JSON Escape Utility
- Result: 10 tests passing
- Health: 97/100

## Wake Cycle #576 (2026-02-04 21:45)
- Action: Curating memories
- Result: Curated memories: 0 found, 0 promoted
- Health: 95/100
""",
        'memory/2026-02-03.md': """
# Daily Memory - Feb 3, 2026

## Today's Accomplishments
- Credential Rotation Alert System (12 tests)

## Wake Cycles
## Wake Cycle #570 (2026-02-03 20:00)
- Action: Credential Rotation
- Result: 12 tests passing
- Health: 96/100
"""
    }
    
    with patch('memory_audit.read_memory_file') as mock_read:
        mock_read.side_effect = lambda f: mock_files.get(f, '')
        summary = generate_audit_summary()
        
        assert 'date' in summary
        assert 'cycles_today' in summary
        assert 'patterns' in summary
        assert 'metrics' in summary
        assert len(summary['cycles_today']) >= 2


def test_update_memory_with_insights():
    """Test updating MEMORY.md with distilled insights"""
    from memory_audit import update_memory_with_insights
    
    mock_summary = {
        'date': '2026-02-04',
        'cycles_today': [{'cycle': '#575', 'action': 'JSON Escape Utility', 'result': '10 tests', 'health': '97/100'}],
        'patterns': {'curating memories': {'count': 3, 'actions': []}},
        'metrics': {'tests': '10/10', 'commits': '6'},
        'insights': ['Focus on small utilities that solve real problems']
    }
    
    # Mock file operations
    with patch('memory_audit.read_file', return_value=''), \
         patch('memory_audit.write_file') as mock_write:
        update_memory_with_insights(mock_summary)
        mock_write.assert_called_once()
        content = mock_write.call_args[0][1]
        assert '2026-02-04' in content
        assert 'Focus on small utilities' in content


def test_run_audit():
    """Test the full audit run"""
    from memory_audit import run_audit
    
    mock_files = {
        'memory/2026-02-04.md': '# Daily Memory - Feb 4, 2026\n\n## Wake Cycles\n## Wake Cycle #575\n- Action: Testing\n- Result: Success',
        'memory/2026-02-03.md': '# Daily Memory - Feb 3, 2026\n\n## Wake Cycles\n## Wake Cycle #570\n- Action: Previous work\n- Result: Done'
    }
    
    with patch('memory_audit.read_memory_file', side_effect=lambda f: mock_files.get(f, '')), \
         patch('memory_audit.update_memory_with_insights') as mock_update:
        result = run_audit()
        assert mock_update.called
        assert 'summary' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
