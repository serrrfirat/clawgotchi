"""TDD Tests for MemoryShardManager"""
import pytest
import os
import time
from memory_shard_manager import MemoryShardManager, MemoryShard, Transaction


class TestMemoryShardManager:
    """Test suite for MemoryShardManager"""
    
    def setup_method(self):
        """Create fresh manager for each test"""
        self.manager = MemoryShardManager()
    
    def test_create_shard(self):
        """Can create a new memory shard"""
        shard = self.manager.create_shard("technical", "Tech discussions")
        assert shard.domain == "technical"
        assert shard.description == "Tech discussions"
        assert shard.shard_id.startswith("technical_")
    
    def test_add_transaction(self):
        """Can add a transaction to a shard"""
        shard = self.manager.create_shard("philosophical", "Philosophy")
        tx = shard.add_transaction("Consciousness is recursive", 0.9)
        assert tx.content == "Consciousness is recursive"
        assert tx.importance == 0.9
        assert len(shard.transactions) == 1
    
    def test_query_shard(self):
        """Can query within a shard"""
        shard = self.manager.create_shard("technical", "Tech")
        shard.add_transaction("Python is great", 0.8)
        shard.add_transaction("Rust is fast", 0.7)
        shard.add_transaction("Python has great libraries", 0.9)
        
        results = shard.query("Python")
        assert len(results) == 2
    
    def test_find_shards_by_domain(self):
        """Can find shards relevant to a query domain"""
        self.manager.create_shard("technical", "Tech")
        self.manager.create_shard("philosophical", "Philosophy")
        self.manager.create_shard("social", "Social")
        
        tech_shards = self.manager.find_shards_for_domain("technical")
        assert len(tech_shards) == 1
        
        all_shards = self.manager.find_shards_for_domain("all")
        assert len(all_shards) == 3
    
    def test_cross_shard_reference(self):
        """Can create cross-shard references"""
        shard1 = self.manager.create_shard("technical", "Tech")
        shard2 = self.manager.create_shard("philosophical", "Philosophy")
        
        tx1 = shard1.add_transaction("The nature of computation", 0.85)
        tx2 = shard2.add_transaction("And consciousness emerges", 0.9)
        
        shard1.add_reference(tx1.tx_id, "philosophical", tx2.tx_id)
        
        refs = shard1.get_references(tx1.tx_id)
        assert len(refs) == 1
        assert refs[0]["target_shard"] == "philosophical"
    
    def test_persistence(self):
        """Can save and restore shards"""
        shard = self.manager.create_shard("tasks", "Task history")
        shard.add_transaction("Build MemoryShardManager", 0.95)
        shard.add_transaction("Write tests", 0.9)
        
        # Save
        self.manager.save_shards("/tmp/test_shards.json")
        
        # Create new manager and load
        new_manager = MemoryShardManager()
        new_manager.load_shards("/tmp/test_shards.json")
        
        loaded_shard = new_manager.get_shard(shard.shard_id)
        assert len(loaded_shard.transactions) == 2
        
        # Cleanup
        os.remove("/tmp/test_shards.json")
    
    def test_importance_filtering(self):
        """Can filter transactions by importance threshold"""
        shard = self.manager.create_shard("social", "Social")
        shard.add_transaction("Important thought", 0.95)
        shard.add_transaction("Medium thought", 0.6)
        shard.add_transaction("Minor thought", 0.2)
        
        important = shard.get_by_importance(0.7)
        assert len(important) == 1
    
    def test_shard_stats(self):
        """Can get statistics about shards"""
        shard1 = self.manager.create_shard("technical", "Tech")
        self.manager.create_shard("philosophical", "Philosophy")
        
        shard1.add_transaction("Test 1", 0.8)
        shard1.add_transaction("Test 2", 0.7)
        
        stats = self.manager.get_stats()
        assert stats["total_shards"] == 2
        assert stats["total_transactions"] == 2
        assert "technical" in stats["domains"]
