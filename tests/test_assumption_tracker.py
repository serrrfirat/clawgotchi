"""Tests for Assumption Tracker."""

import os
import sys
from datetime import datetime, timedelta

os.environ['CLAWGOTCHI_DATA_DIR'] = '/tmp/clawgotchi_test'
os.environ['CLAWGOTCHI_ASSUMPTIONS_FILE'] = '/tmp/clawgotchi_test/assumptions.json'

sys.path.insert(0, os.getcwd())

from utils.assumption_tracker import (
    add_assumption, verify_assumption, invalidate_assumption,
    list_assumptions, get_assumption, add_note, cleanup_expired,
    check_stale, get_summary, clear_all
)


def test_add_assumption():
    clear_all()
    ass_id = add_assumption("API returns JSON", "src/api.py", expires_hours=24)
    assert ass_id is not None and len(ass_id) == 8
    ass = get_assumption(ass_id)
    assert ass['text'] == "API returns JSON"
    assert ass['status'] == 'open'
    print("✓ test_add_assumption passed")


def test_verify_assumption():
    clear_all()
    ass_id = add_assumption("Database is online", "db_connector.py")
    assert verify_assumption(ass_id) is True
    ass = get_assumption(ass_id)
    assert ass['status'] == 'verified'
    assert ass['verified_at'] is not None
    print("✓ test_verify_assumption passed")


def test_verify_nonexistent():
    clear_all()
    assert verify_assumption("nonexistent") is False
    print("✓ test_verify_nonexistent passed")


def test_invalidate_assumption():
    clear_all()
    ass_id = add_assumption("File exists", "processor.py")
    assert invalidate_assumption(ass_id, "File was deleted") is True
    ass = get_assumption(ass_id)
    assert ass['status'] == 'invalid'
    assert ass['invalidation_reason'] == "File was deleted"
    print("✓ test_invalidate_assumption passed")


def test_list_assumptions():
    clear_all()
    id1 = add_assumption("Assumption 1")
    id2 = add_assumption("Assumption 2")
    id3 = add_assumption("Assumption 3")
    assert len(list_assumptions()) == 3
    verify_assumption(id2)
    assert len(list_assumptions(status='open')) == 2
    assert len(list_assumptions(status='verified')) == 1
    print("✓ test_list_assumptions passed")


def test_add_note():
    clear_all()
    ass_id = add_assumption("User is logged in")
    assert add_note(ass_id, "Checked session cookie") is True
    assert add_note(ass_id, "Verified JWT token") is True
    ass = get_assumption(ass_id)
    assert len(ass['notes']) == 2
    print("✓ test_add_note passed")


def test_cleanup_expired():
    clear_all()
    ass_id = add_assumption("Temporary assumption", expires_hours=0)
    assumptions = list_assumptions()
    for ass in assumptions:
        if ass['id'] == ass_id:
            ass['expires_at'] = datetime.now().isoformat()
    import json
    os.makedirs('/tmp/clawgotchi_test', exist_ok=True)
    with open('/tmp/clawgotchi_test/assumptions.json', 'w') as f:
        json.dump(assumptions, f)
    count = cleanup_expired()
    assert count == 1
    ass = get_assumption(ass_id)
    assert ass['status'] == 'expired'
    print("✓ test_cleanup_expired passed")


def test_check_stale():
    clear_all()
    ass_id = add_assumption("Stale assumption", expires_hours=0)
    assumptions = list_assumptions()
    for ass in assumptions:
        if ass['id'] == ass_id:
            ass['expires_at'] = (datetime.now() - timedelta(hours=10)).isoformat()
    import json
    with open('/tmp/clawgotchi_test/assumptions.json', 'w') as f:
        json.dump(assumptions, f)
    stale = check_stale()
    assert len(stale) == 1
    assert stale[0]['id'] == ass_id
    print("✓ test_check_stale passed")


def test_get_summary():
    clear_all()
    add_assumption("Assumption 1")
    add_assumption("Assumption 2")
    id3 = add_assumption("Assumption 3")
    verify_assumption(id3)
    summary = get_summary()
    assert summary['total'] == 3
    assert summary['open'] == 2
    assert summary['verified'] == 1
    print("✓ test_get_summary passed")


def test_workflow():
    clear_all()
    api_ass_id = add_assumption(
        "API endpoint returns 200 for valid requests",
        "src/integrations/api_client.py",
        expires_hours=48
    )
    add_note(api_ass_id, "Tested with mock server - passed")
    verify_assumption(api_ass_id)
    
    db_ass_id = add_assumption("Database connection uses default port", "config/database.yaml")
    add_note(db_ass_id, "Actually uses port 5433, not 5432")
    invalidate_assumption(db_ass_id, "Port configuration is different than expected")
    
    summary = get_summary()
    assert summary['verified'] == 1
    assert summary['invalid'] == 1
    assert summary['open'] == 0
    print("✓ test_workflow passed")


if __name__ == '__main__':
    test_add_assumption()
    test_verify_assumption()
    test_verify_nonexistent()
    test_invalidate_assumption()
    test_list_assumptions()
    test_add_note()
    test_cleanup_expired()
    test_check_stale()
    test_get_summary()
    test_workflow()
    print("\n✅ All tests passed!")
