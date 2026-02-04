"""Pytest configuration and fixtures for Clawgotchi tests."""
import os
import tempfile
import pytest


@pytest.fixture
def temp_memory_dir():
    """Create a temporary memory directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
