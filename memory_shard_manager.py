"""MemoryShardManager - Domain-sharded memory for agents

Inspired by BuraluxBot's "Sharding for Agent Memory" concept.
Provides domain-based memory sharding with transaction tracking,
cross-shard references, and persistence.
"""
import json
import uuid
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Transaction:
    """A single memory transaction within a shard"""
    tx_id: str
    content: str
    timestamp: str
    importance: float
    references: list = field(default_factory=list)
    
    @classmethod
    def create(cls, content: str, importance: float):
        return cls(
            tx_id=str(uuid.uuid4())[:8],
            content=content,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            importance=min(max(importance, 0.0), 1.0)  # Clamp to [0, 1]
        )


@dataclass
class MemoryShard:
    """A domain-specific memory shard"""
    shard_id: str
    domain: str
    description: str
    created_at: str
    transactions: list = field(default_factory=list)
    
    def add_transaction(self, content: str, importance: float) -> Transaction:
        """Add a new transaction to this shard"""
        tx = Transaction.create(content, importance)
        self.transactions.append(tx)
        return tx
    
    def query(self, query_text: str) -> list:
        """Search within this shard"""
        query = query_text.lower()
        return [tx for tx in self.transactions if query in tx.content.lower()]
    
    def get_references(self, tx_id: str) -> list:
        """Get cross-shard references for a transaction"""
        for tx in self.transactions:
            if tx.tx_id == tx_id:
                return tx.references
        return []
    
    def add_reference(self, from_tx_id: str, target_shard: str, target_tx_id: str):
        """Add a cross-shard reference"""
        for tx in self.transactions:
            if tx.tx_id == from_tx_id:
                tx.references.append({
                    "target_shard": target_shard,
                    "target_tx": target_tx_id
                })
                return
    
    def get_by_importance(self, threshold: float) -> list:
        """Get transactions above importance threshold"""
        return [tx for tx in self.transactions if tx.importance >= threshold]
    
    def to_dict(self) -> dict:
        """Serialize shard to dictionary"""
        return {
            "shard_id": self.shard_id,
            "domain": self.domain,
            "description": self.description,
            "created_at": self.created_at,
            "transactions": [
                {
                    "tx_id": tx.tx_id,
                    "content": tx.content,
                    "timestamp": tx.timestamp,
                    "importance": tx.importance,
                    "references": tx.references
                }
                for tx in self.transactions
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MemoryShard":
        """Deserialize shard from dictionary"""
        shard = cls(
            shard_id=data["shard_id"],
            domain=data["domain"],
            description=data["description"],
            created_at=data["created_at"]
        )
        for tx_data in data.get("transactions", []):
            tx = Transaction(
                tx_id=tx_data["tx_id"],
                content=tx_data["content"],
                timestamp=tx_data["timestamp"],
                importance=tx_data["importance"],
                references=tx_data.get("references", [])
            )
            shard.transactions.append(tx)
        return shard


class MemoryShardManager:
    """Manager for domain-sharded agent memory"""
    
    def __init__(self):
        self.shards: dict[str, MemoryShard] = {}
    
    def create_shard(self, domain: str, description: str = "") -> MemoryShard:
        """Create a new memory shard for a domain"""
        shard_id = f"{domain}_{str(uuid.uuid4())[:8]}"
        shard = MemoryShard(
            shard_id=shard_id,
            domain=domain,
            description=description,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self.shards[shard_id] = shard
        return shard
    
    def get_shard(self, shard_id: str) -> Optional[MemoryShard]:
        """Get a shard by ID"""
        return self.shards.get(shard_id)
    
    def find_shards_for_domain(self, domain: str) -> list[MemoryShard]:
        """Find all shards for a domain (or all if 'all')"""
        if domain == "all":
            return list(self.shards.values())
        return [s for s in self.shards.values() if s.domain == domain]
    
    def find_shards_for_query(self, query_text: str) -> list[MemoryShard]:
        """Find shards relevant to a query"""
        query = query_text.lower()
        relevant = []
        for shard in self.shards.values():
            if shard.query(query_text):
                relevant.append(shard)
        return relevant
    
    def cross_shard_transfer(self, from_shard_id: str, to_shard_id: str, 
                               from_tx_id: str, to_tx_id: str):
        """Coordinate state transfer between shards"""
        from_shard = self.shards.get(from_shard_id)
        to_shard = self.shards.get(to_shard_id)
        if from_shard and to_shard:
            from_shard.add_reference(from_tx_id, to_shard.domain, to_tx_id)
    
    def save_shards(self, filepath: str):
        """Persist all shards to file"""
        data = {
            "version": "1.0",
            "shards": {k: v.to_dict() for k, v in self.shards.items()}
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_shards(self, filepath: str):
        """Load shards from file"""
        if not os.path.exists(filepath):
            return
        with open(filepath) as f:
            data = json.load(f)
        for shard_data in data.get("shards", {}).values():
            shard = MemoryShard.from_dict(shard_data)
            self.shards[shard.shard_id] = shard
    
    def get_stats(self) -> dict:
        """Get statistics about memory shards"""
        domains = {}
        for shard in self.shards.values():
            if shard.domain not in domains:
                domains[shard.domain] = 0
            domains[shard.domain] += len(shard.transactions)
        
        return {
            "total_shards": len(self.shards),
            "total_transactions": sum(len(s.transactions) for s in self.shards.values()),
            "domains": domains
        }
