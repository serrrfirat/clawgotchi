"""
Memory Decay Simulator Tests

Tests for validating memory decay patterns and simulation behavior.
"""

import math
import unittest
from datetime import datetime, timedelta


class TestMemoryItem(unittest.TestCase):
    """Test cases for MemoryItem."""
    
    def test_memory_creation(self):
        """Test basic memory item creation."""
        from memory_decay import MemoryItem
        
        now = datetime.now()
        memory = MemoryItem(
            content="Test memory",
            importance=0.8,
            created_at=now,
            last_accessed=now,
            tags=["test", "unit"],
        )
        
        self.assertEqual(memory.content, "Test memory")
        self.assertEqual(memory.importance, 0.8)
        self.assertEqual(memory.access_count, 0)
        self.assertEqual(memory.tags, ["test", "unit"])
    
    def test_get_age_hours(self):
        """Test age calculation in hours."""
        from memory_decay import MemoryItem
        
        now = datetime.now()
        past = now - timedelta(hours=5)
        
        memory = MemoryItem(
            content="Old memory",
            importance=0.5,
            created_at=past,
            last_accessed=past,
        )
        
        age = memory.get_age_hours(now)
        self.assertAlmostEqual(age, 5.0, places=1)
    
    def test_get_time_since_access_hours(self):
        """Test time since last access calculation."""
        from memory_decay import MemoryItem
        
        now = datetime.now()
        recent_access = now - timedelta(hours=2)
        
        memory = MemoryItem(
            content="Recently accessed",
            importance=0.5,
            created_at=now,
            last_accessed=recent_access,
        )
        
        time_since = memory.get_time_since_access_hours(now)
        self.assertAlmostEqual(time_since, 2.0, places=1)


class TestDecayFunctions(unittest.TestCase):
    """Test cases for decay function implementations."""
    
    def setUp(self):
        """Create test memory."""
        from memory_decay import MemoryItem
        self.now = datetime.now()
        self.memory = MemoryItem(
            content="Test memory",
            importance=0.5,
            created_at=self.now,
            last_accessed=self.now,
            access_count=1,
        )
    
    def test_exponential_decay_initial(self):
        """Test exponential decay at time 0."""
        from memory_decay import ExponentialDecay
        
        decay = ExponentialDecay(lambda_param=0.1)
        strength = decay.calculate(self.memory, self.now)
        
        # At time 0, strength should be boosted by importance and access
        self.assertGreater(strength, 0.5)
        self.assertLessEqual(strength, 1.0)
    
    def test_exponential_decay_after_time(self):
        """Test exponential decay after time passes."""
        from memory_decay import ExponentialDecay
        
        decay = ExponentialDecay(lambda_param=0.1)
        future_time = self.now + timedelta(hours=10)
        
        # Memory shouldn't decay too much in 10 hours with lambda=0.1
        strength = decay.calculate(self.memory, future_time)
        self.assertGreater(strength, 0.2)
    
    def test_logarithmic_decay_initial(self):
        """Test logarithmic decay at time 0."""
        from memory_decay import LogarithmicDecay
        
        decay = LogarithmicDecay(max_hours=168)
        strength = decay.calculate(self.memory, self.now)
        
        self.assertGreater(strength, 0.5)
    
    def test_logarithmic_decay_after_time(self):
        """Test logarithmic decay after significant time."""
        from memory_decay import LogarithmicDecay
        
        decay = LogarithmicDecay(max_hours=168)  # 1 week
        future_time = self.now + timedelta(hours=100)  # ~4 days
        
        strength = decay.calculate(self.memory, future_time)
        # Should still have significant strength at 4 days
        self.assertGreater(strength, 0.4)
    
    def test_linear_decay_initial(self):
        """Test linear decay at time 0."""
        from memory_decay import LinearDecay
        
        decay = LinearDecay(max_hours=720)  # 30 days
        strength = decay.calculate(self.memory, self.now)
        
        self.assertGreater(strength, 0.5)
    
    def test_linear_decay_midpoint(self):
        """Test linear decay at midpoint."""
        from memory_decay import LinearDecay
        
        decay = LinearDecay(max_hours=720)
        midpoint = self.now + timedelta(hours=360)  # 15 days
        
        strength = decay.calculate(self.memory, midpoint)
        # At midpoint with no access, should be around 0.5 * importance factor
        self.assertGreater(strength, 0.2)
        self.assertLess(strength, 0.8)
    
    def test_power_law_decay_initial(self):
        """Test power law decay at time 0."""
        from memory_decay import PowerLawDecay
        
        decay = PowerLawDecay(alpha=0.5)
        strength = decay.calculate(self.memory, self.now)
        
        self.assertGreater(strength, 0.5)
    
    def test_power_law_decay_preserves_importance(self):
        """Test that power law decay strongly respects importance."""
        from memory_decay import PowerLawDecay, MemoryItem
        
        decay = PowerLawDecay(alpha=0.5)
        
        high_importance = MemoryItem(
            content="Important",
            importance=1.0,
            created_at=self.now,
            last_accessed=self.now,
            access_count=5,
        )
        
        low_importance = MemoryItem(
            content="Unimportant",
            importance=0.1,
            created_at=self.now,
            last_accessed=self.now,
            access_count=0,
        )
        
        high_strength = decay.calculate(high_importance, self.now)
        low_strength = decay.calculate(low_importance, self.now)
        
        self.assertGreater(high_strength, low_strength)
    
    def test_decay_function_names(self):
        """Test that decay functions have names."""
        from memory_decay import (
            ExponentialDecay,
            LogarithmicDecay,
            LinearDecay,
            PowerLawDecay,
        )
        
        self.assertIn("exponential", ExponentialDecay().name())
        self.assertIn("logarithmic", LogarithmicDecay().name())
        self.assertIn("linear", LinearDecay().name())
        self.assertIn("power", PowerLawDecay().name())


class TestMemoryDecaySimulator(unittest.TestCase):
    """Test cases for MemoryDecaySimulator."""
    
    def setUp(self):
        """Create a fresh simulator."""
        from memory_decay import MemoryDecaySimulator, ExponentialDecay
        self.simulator = MemoryDecaySimulator(decay_function=ExponentialDecay(lambda_param=0.1))
    
    def test_add_memory(self):
        """Test adding memories to simulator."""
        mem_id = self.simulator.add_memory(
            content="Test memory",
            importance=0.7,
            tags=["test"],
        )
        
        self.assertIsNotNone(mem_id)
        self.assertTrue(mem_id.startswith("mem_"))
        self.assertEqual(len(self.simulator.memories), 1)
    
    def test_add_multiple_memories(self):
        """Test adding multiple memories."""
        self.simulator.add_memory(content="Memory 1", importance=0.5)
        self.simulator.add_memory(content="Memory 2", importance=0.8)
        self.simulator.add_memory(content="Memory 3", importance=0.3)
        
        self.assertEqual(len(self.memories), 3)
    
    def test_access_memory(self):
        """Test accessing a memory refreshes it."""
        mem_id = self.simulator.add_memory(content="Test", importance=0.5)
        
        # Access the memory
        memory = self.simulator.access_memory(mem_id)
        
        self.assertIsNotNone(memory)
        self.assertEqual(memory.access_count, 1)
    
    def test_access_nonexistent_memory(self):
        """Test accessing non-existent memory returns None."""
        result = self.simulator.access_memory("nonexistent_id")
        self.assertIsNone(result)
    
    def test_get_memory_strength(self):
        """Test getting memory strength."""
        mem_id = self.simulator.add_memory(content="Test", importance=0.9)
        
        strength = self.simulator.get_memory_strength(mem_id)
        
        self.assertIsNotNone(strength)
        self.assertGreater(strength, 0.5)
    
    def test_advance_time(self):
        """Test advancing simulator time."""
        original_time = self.simulator.current_time
        
        self.simulator.advance_time(hours=24)
        
        self.assertGreater(
            self.simulator.current_time.timestamp(),
            original_time.timestamp(),
        )
        # Should have recorded decay state
        self.assertEqual(len(self.simulator.decay_history), 1)
    
    def test_strength_decreases_over_time(self):
        """Test that memory strength decreases as time passes."""
        mem_id = self.simulator.add_memory(content="Test", importance=0.5)
        
        initial_strength = self.simulator.get_memory_strength(mem_id)
        
        self.simulator.advance_time(hours=100)
        
        later_strength = self.simulator.get_memory_strength(mem_id)
        
        self.assertLess(later_strength, initial_strength)
    
    def test_access_refreshes_strength(self):
        """Test that accessing a memory refreshes its strength."""
        mem_id = self.simulator.add_memory(content="Test", importance=0.5)
        
        self.simulator.advance_time(hours=50)
        strength_before = self.simulator.get_memory_strength(mem_id)
        
        self.simulator.access_memory(mem_id)
        strength_after = self.simulator.get_memory_strength(mem_id)
        
        self.assertGreater(strength_after, strength_before)
    
    def test_get_forgotten_memories(self):
        """Test identifying forgotten memories."""
        mem_id = self.simulator.add_memory(content="Old memory", importance=0.1)
        
        # Advance time significantly
        self.simulator.advance_time(hours=1000)
        
        forgotten = self.simulator.get_forgotten_memories(threshold=0.1)
        
        self.assertIn(mem_id, forgotten)
    
    def test_get_strong_memories(self):
        """Test identifying strong memories."""
        mem_id = self.simulator.add_memory(content="Important", importance=1.0)
        
        strong = self.simulator.get_strong_memories(threshold=0.5)
        
        self.assertEqual(len(strong), 1)
        self.assertEqual(strong[0][0], mem_id)
    
    def test_get_decay_stats(self):
        """Test decay statistics."""
        self.simulator.add_memory(content="M1", importance=0.5)
        self.simulator.add_memory(content="M2", importance=0.8)
        
        stats = self.simulator.get_decay_stats()
        
        self.assertEqual(stats["total_memories"], 2)
        self.assertIn("avg_strength", stats)
        self.assertIn("strong_count", stats)
        self.assertIn("weak_count", stats)
    
    def test_simulate_access_pattern(self):
        """Test simulating access patterns."""
        mem_id = self.simulator.add_memory(content="Test", importance=0.7)
        
        strengths = self.simulator.simulate_access_pattern(
            mem_id,
            access_intervals=[10, 20, 30],
        )
        
        self.assertEqual(len(strengths), 3)
        # Each access should refresh strength
        self.assertGreater(strengths[-1], 0.3)
    
    def test_retrieval_quality_score(self):
        """Test retrieval quality calculation."""
        mem_id = self.simulator.add_memory(content="Relevant", importance=0.9)
        
        # Access it recently
        self.simulator.access_memory(mem_id)
        
        score = self.simulator.get_retrieval_quality_score([mem_id])
        
        self.assertGreater(score, 0.5)
    
    def test_retrieval_quality_with_stale_memory(self):
        """Test that stale memories reduce retrieval quality."""
        fresh_id = self.simulator.add_memory(content="Fresh", importance=0.9)
        stale_id = self.simulator.add_memory(content="Stale", importance=0.9)
        
        # Advance time for stale memory
        self.simulator.advance_time(hours=500)
        
        fresh_score = self.simulator.get_retrieval_quality_score([fresh_id])
        stale_score = self.simulator.get_retrieval_quality_score([stale_id])
        
        self.assertGreater(fresh_score, stale_score)
    
    def test_clear(self):
        """Test clearing simulator."""
        self.simulator.add_memory(content="Test", importance=0.5)
        self.simulator.advance_time(10)
        
        self.simulator.clear()
        
        self.assertEqual(len(self.simulator.memories), 0)
        self.assertEqual(len(self.simulator.decay_history), 0)
    
    def test_empty_simulator_stats(self):
        """Test stats with no memories."""
        stats = self.simulator.get_decay_stats()
        
        self.assertEqual(stats["total_memories"], 0)
        self.assertEqual(stats["avg_strength"], 0.0)


class TestDecayFunctionComparison(unittest.TestCase):
    """Test cases comparing different decay functions."""
    
    def setUp(self):
        """Create memories for comparison."""
        from memory_decay import MemoryItem
        self.now = datetime.now()
        self.base_memory = MemoryItem(
            content="Base",
            importance=0.5,
            created_at=self.now,
            last_accessed=self.now,
            access_count=0,
        )
        self.high_importance_memory = MemoryItem(
            content="Important",
            importance=1.0,
            created_at=self.now,
            last_accessed=self.now,
            access_count=5,
        )
    
    def test_different_decay_speeds(self):
        """Test that different decay functions have different speeds."""
        from memory_decay import (
            ExponentialDecay,
            LogarithmicDecay,
            LinearDecay,
            PowerLawDecay,
        )
        
        future = self.now + timedelta(hours=100)
        
        exp_decay = ExponentialDecay(lambda_param=0.1)
        log_decay = LogarithmicDecay(max_hours=168)
        lin_decay = LinearDecay(max_hours=720)
        pwr_decay = PowerLawDecay(alpha=0.5)
        
        exp_strength = exp_decay.calculate(self.base_memory, future)
        log_strength = log_decay.calculate(self.base_memory, future)
        lin_strength = lin_decay.calculate(self.base_memory, future)
        pwr_strength = pwr_decay.calculate(self.base_memory, future)
        
        # All should be different (not necessarily ordered)
        strengths = [exp_strength, log_strength, lin_strength, pwr_strength]
        # With different formulas, strengths should differ
        self.assertTrue(
            max(strengths) - min(strengths) > 0.1,
            "Decay functions should produce different strengths",
        )
    
    def test_access_count_effect(self):
        """Test that access count affects decay in all functions."""
        from memory_decay import ExponentialDecay, PowerLawDecay
        
        no_access = MemoryItem(
            content="No access",
            importance=0.5,
            created_at=self.now,
            last_accessed=self.now,
            access_count=0,
        )
        frequent_access = MemoryItem(
            content="Frequent",
            importance=0.5,
            created_at=self.now,
            last_accessed=self.now,
            access_count=10,
        )
        
        exp_decay = ExponentialDecay(lambda_param=0.1)
        pwr_decay = PowerLawDecay(alpha=0.5)
        
        exp_no = exp_decay.calculate(no_access, self.now)
        exp_yes = exp_decay.calculate(frequent_access, self.now)
        pwr_no = pwr_decay.calculate(no_access, self.now)
        pwr_yes = pwr_decay.calculate(frequent_access, self.now)
        
        self.assertGreater(exp_yes, exp_no)
        self.assertGreater(pwr_yes, pwr_no)


if __name__ == "__main__":
    unittest.main()
