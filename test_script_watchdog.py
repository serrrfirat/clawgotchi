"""Tests for Script Watchdog."""

import os
import tempfile
import unittest
from pathlib import Path

from script_watchdog import Watchdog, ScriptNotFoundError, WatchdogError


class TestHashComputation(unittest.TestCase):
    """Tests for hash computation functionality."""
    
    def test_compute_hash_returns_consistent_hash(self):
        """Same content should produce same hash."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
            f.write("#!/bin/bash\necho hello")
            temp_path = f.name
        
        try:
            wd = Watchdog()
            hash1 = wd._compute_hash(temp_path)
            hash2 = wd._compute_hash(temp_path)
            self.assertEqual(hash1, hash2)
        finally:
            os.unlink(temp_path)
    
    def test_compute_hash_detects_changes(self):
        """Different content should produce different hash."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
            f.write("#!/bin/bash\necho hello")
            temp_path = f.name
        
        try:
            wd = Watchdog()
            hash1 = wd._compute_hash(temp_path)
            
            with open(temp_path, 'w') as f:
                f.write("#!/bin/bash\necho goodbye")
            
            hash2 = wd._compute_hash(temp_path)
            self.assertNotEqual(hash1, hash2)
        finally:
            os.unlink(temp_path)
    
    def test_compute_hash_raises_for_missing_file(self):
        """Should raise ScriptNotFoundError for missing file."""
        wd = Watchdog()
        with self.assertRaises(ScriptNotFoundError):
            wd._compute_hash("/nonexistent/script.sh")


class TestScriptRegistration(unittest.TestCase):
    """Tests for script registration."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "watchdog.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_register_creates_config(self):
        """Registering a script should create config file."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho test")
        
        wd = Watchdog(str(self.config_path))
        wd.register("test_script", str(script_path))
        
        self.assertTrue(self.config_path.exists())
    
    def test_register_stores_script_info(self):
        """Registered script should be retrievable."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho test")
        
        wd = Watchdog(str(self.config_path))
        wd.register("test_script", str(script_path))
        
        self.assertIn("test_script", wd.scripts)
        self.assertEqual(wd.scripts["test_script"]["path"], str(script_path))
    
    def test_unregister_removes_script(self):
        """Unregister should remove script from config."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho test")
        
        wd = Watchdog(str(self.config_path))
        wd.register("test_script", str(script_path))
        wd.unregister("test_script")
        
        self.assertNotIn("test_script", wd.scripts)
    
    def test_register_raises_for_missing_script(self):
        """Registering missing script should raise error."""
        wd = Watchdog(str(self.config_path))
        with self.assertRaises(ScriptNotFoundError):
            wd.register("missing", "/nonexistent/script.sh")


class TestChangeDetection(unittest.TestCase):
    """Tests for change detection."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "watchdog.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_check_for_changes_detects_modification(self):
        """Change detection should notice file modifications."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho original")
        
        wd = Watchdog(str(self.config_path))
        wd.register("test_script", str(script_path))
        
        # First check - should detect initial state
        changed = wd.check_for_changes("test_script")
        self.assertFalse(changed)  # Already registered with this hash
        
        # Modify file
        script_path.write_text("#!/bin/bash\necho modified")
        
        # Second check - should detect change
        changed = wd.check_for_changes("test_script")
        self.assertTrue(changed)
    
    def test_check_for_changes_raises_for_unregistered(self):
        """Checking unregistered script should raise error."""
        wd = Watchdog(str(self.config_path))
        with self.assertRaises(WatchdogError):
            wd.check_for_changes("nonexistent")


class TestScriptExecution(unittest.TestCase):
    """Tests for script execution."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "watchdog.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_run_executes_script(self):
        """Running script should execute and return output."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Hello World'")
        os.chmod(str(script_path), 0o755)
        
        wd = Watchdog(str(self.config_path))
        wd.register("test_script", str(script_path))
        
        exit_code, output = wd.run("test_script")
        
        self.assertEqual(exit_code, 0)
        self.assertIn("Hello World", output)
    
    def test_run_returns_nonzero_for_failure(self):
        """Failing script should return non-zero exit code."""
        script_path = Path(self.temp_dir) / "fail_script.sh"
        script_path.write_text("#!/bin/bash\nexit 1")
        os.chmod(str(script_path), 0o755)
        
        wd = Watchdog(str(self.config_path))
        wd.register("fail_script", str(script_path))
        
        exit_code, output = wd.run("fail_script")
        
        self.assertEqual(exit_code, 1)
    
    def test_run_if_changed_only_runs_on_change(self):
        """run_if_changed should only run when script changed."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Hello'")
        os.chmod(str(script_path), 0o755)
        
        wd = Watchdog(str(self.config_path))
        # Register with initial hash
        wd.register("test_script", str(script_path))
        
        # Reset - simulate fresh check
        wd.scripts["test_script"]["last_hash"] = "old_hash"
        
        # First run - should detect change and run
        ran, code, output = wd.run_if_changed("test_script")
        self.assertTrue(ran)
        
        # Second run - no change, shouldn't run
        ran, code, output = wd.run_if_changed("test_script")
        self.assertFalse(ran)


class TestStatus(unittest.TestCase):
    """Tests for status reporting."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "watchdog.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_status_returns_script_info(self):
        """Status should return dictionary with script info."""
        script_path = Path(self.temp_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho test")
        
        wd = Watchdog(str(self.config_path))
        wd.register("test_script", str(script_path))
        
        status = wd.status("test_script")
        
        self.assertEqual(status["name"], "test_script")
        self.assertTrue(status["exists"])
        self.assertIn("last_changed", status)
        self.assertIn("hash", status)
    
    def test_status_raises_for_unregistered(self):
        """Status for unregistered script should raise error."""
        wd = Watchdog(str(self.config_path))
        with self.assertRaises(WatchdogError):
            wd.status("nonexistent")


class TestListRegistered(unittest.TestCase):
    """Tests for listing registered scripts."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "watchdog.json"
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_list_returns_registered_names(self):
        """List should return all registered script names."""
        for i in range(3):
            script_path = Path(self.temp_dir) / f"script_{i}.sh"
            script_path.write_text("#!/bin/bash\necho test")
            
            wd = Watchdog(str(self.config_path))
            wd.register(f"script_{i}", str(script_path))
        
        registered = wd.list_registered()
        
        self.assertEqual(len(registered), 3)
        for i in range(3):
            self.assertIn(f"script_{i}", registered)


if __name__ == "__main__":
    unittest.main()
