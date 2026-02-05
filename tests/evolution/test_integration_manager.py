"""Tests for IntegrationManager."""

import json
import pytest
import tempfile
from pathlib import Path

from clawgotchi.evolution.integration_manager import IntegrationManager, ModuleInfo


@pytest.fixture
def temp_dirs():
    """Create temp directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        memory_dir = tmpdir / "memory"
        memory_dir.mkdir()

        # Create test module structure
        resilience_dir = tmpdir / "clawgotchi" / "resilience"
        resilience_dir.mkdir(parents=True)
        (resilience_dir / "__init__.py").write_text("")

        # Create a test module
        test_module = resilience_dir / "test_utility.py"
        test_module.write_text('''"""Test utility module."""

class TestUtility:
    """A test utility class."""

    def run(self):
        return "running"

def helper_function():
    """A helper function."""
    return True
''')

        # Create another orphaned module
        orphaned = resilience_dir / "orphaned_module.py"
        orphaned.write_text('''"""Orphaned module."""

class OrphanedClass:
    pass

def orphaned_function():
    pass
''')

        yield tmpdir, memory_dir


@pytest.fixture
def integration_manager(temp_dirs):
    """Create an IntegrationManager."""
    tmpdir, memory_dir = temp_dirs
    return IntegrationManager(registry=None, memory_dir=str(memory_dir))


class TestScanOrphanedModules:
    """Tests for scanning orphaned modules."""

    def test_scan_finds_modules(self, temp_dirs):
        """scan_orphaned_modules finds Python files."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        orphaned = manager.scan_orphaned_modules(base_dir=str(tmpdir))
        names = [m["name"] for m in orphaned]

        assert "test_utility" in names
        assert "orphaned_module" in names

    def test_scan_extracts_classes(self, temp_dirs):
        """Scan extracts class names from modules."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        orphaned = manager.scan_orphaned_modules(base_dir=str(tmpdir))
        test_mod = next(m for m in orphaned if m["name"] == "test_utility")

        assert "TestUtility" in test_mod["classes"]

    def test_scan_extracts_functions(self, temp_dirs):
        """Scan extracts function names from modules."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        orphaned = manager.scan_orphaned_modules(base_dir=str(tmpdir))
        test_mod = next(m for m in orphaned if m["name"] == "test_utility")

        assert "helper_function" in test_mod["functions"]

    def test_scan_skips_private(self, temp_dirs):
        """Scan skips __init__ and _private modules."""
        tmpdir, memory_dir = temp_dirs

        # Create a private module
        private = tmpdir / "clawgotchi" / "resilience" / "_private.py"
        private.write_text("# private")

        manager = IntegrationManager(memory_dir=str(memory_dir))
        orphaned = manager.scan_orphaned_modules(base_dir=str(tmpdir))
        names = [m["name"] for m in orphaned]

        assert "_private" not in names


class TestCategorizeModule:
    """Tests for module categorization."""

    def test_categorize_resilience(self, temp_dirs):
        """Resilience modules go to _check_health."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        point = manager.categorize_module(
            str(tmpdir / "clawgotchi" / "resilience" / "test.py")
        )
        assert point == "_check_health"

    def test_categorize_by_content(self, temp_dirs):
        """Categorization falls back to content analysis."""
        tmpdir, memory_dir = temp_dirs

        # Create a module with decision-related content
        other_dir = tmpdir / "other"
        other_dir.mkdir()
        decide_mod = other_dir / "decider.py"
        decide_mod.write_text("def decide_priority(): pass")

        manager = IntegrationManager(memory_dir=str(memory_dir))
        point = manager.categorize_module(str(decide_mod))

        assert point == "_decide_next_action"


class TestGenerateIntegrationCode:
    """Tests for code generation."""

    def test_generates_import(self, temp_dirs):
        """Generated code includes import statement."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        module = {
            "name": "test_utility",
            "package": "clawgotchi/resilience",
            "classes": ["TestUtility"],
            "functions": ["helper_function"],
            "integration_point": "_check_health",
        }

        code = manager.generate_integration_code(module)

        assert "from clawgotchi.resilience.test_utility import" in code
        assert "TestUtility" in code

    def test_generates_usage_comment(self, temp_dirs):
        """Generated code includes usage comment."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        module = {
            "name": "test_utility",
            "package": "clawgotchi/resilience",
            "classes": ["TestUtility"],
            "functions": [],
            "integration_point": "_check_health",
        }

        code = manager.generate_integration_code(module)

        assert "_check_health" in code
        assert "instance" in code.lower() or "result" in code.lower()


class TestIntegrateModule:
    """Tests for module integration."""

    def test_integrate_tracks_module(self, temp_dirs):
        """integrate_module tracks the module."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        module = {
            "path": str(tmpdir / "clawgotchi" / "resilience" / "test_utility.py"),
            "name": "test_utility",
            "package": "clawgotchi/resilience",
            "category": "resilience",
            "integration_point": "_check_health",
            "classes": ["TestUtility"],
            "functions": [],
        }

        result = manager.integrate_module(module)

        assert result["status"] in ["integrated", "failed"]
        assert "test_utility" in manager._integrations

    def test_integrate_persists(self, temp_dirs):
        """Integration state is persisted."""
        tmpdir, memory_dir = temp_dirs

        manager1 = IntegrationManager(memory_dir=str(memory_dir))
        module = {
            "path": str(tmpdir / "test.py"),
            "name": "test_mod",
            "package": "test",
            "category": "other",
            "integration_point": "_check_health",
            "classes": [],
            "functions": [],
        }
        manager1.integrate_module(module)

        manager2 = IntegrationManager(memory_dir=str(memory_dir))
        assert "test_mod" in manager2._integrations


class TestIntegrationStatus:
    """Tests for integration status reporting."""

    def test_get_integration_status(self, temp_dirs):
        """get_integration_status returns summary."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        status = manager.get_integration_status()

        assert "integrated_count" in status
        assert "orphaned_count" in status
        assert "integrated" in status
        assert "orphaned" in status

    def test_mark_integrated(self, temp_dirs):
        """mark_integrated updates status."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        # First integrate a module
        module = {
            "path": str(tmpdir / "test.py"),
            "name": "mark_test",
            "package": "test",
            "category": "other",
            "integration_point": "_check_health",
            "classes": [],
            "functions": [],
        }
        manager.integrate_module(module)

        # Then explicitly mark it
        manager.mark_integrated("mark_test")
        assert manager._integrations["mark_test"].status == "integrated"


class TestTestIntegration:
    """Tests for integration testing."""

    def test_test_integration_returns_bool(self, temp_dirs):
        """test_integration returns True/False."""
        tmpdir, memory_dir = temp_dirs
        manager = IntegrationManager(memory_dir=str(memory_dir))

        module = {
            "name": "nonexistent",
            "package": "fake.package",
        }

        result = manager.test_integration(module)
        assert isinstance(result, bool)
        assert result is False  # Module doesn't exist
