"""
Memory Decay Simulator

Models and simulates memory decay patterns for agent memory systems.
Based on research showing that memory decay can improve retrieval quality by
reducing noise from outdated or less-relevant information.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class MemoryItem:
    """Represents a single memory item with metadata."""
    content: str
    importance: float  # 0.0 to 1.0
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    decay_rate: float = 0.1  # Custom decay rate for this memory
    tags: List[str] = field(default_factory=list)
    
    def get_age_hours(self, now: Optional[datetime] = None) -> float:
        """Get the age of this memory in hours."""
        if now is None:
            now = datetime.now()
        delta = now - self.created_at
        return delta.total_seconds() / 3600
    
    def get_time_since_access_hours(self, now: Optional[datetime] = None) -> float:
        """Get time since last access in hours."""
        if now is None:
            now = datetime.now()
        delta = now - self.last_accessed
        return delta.total_seconds() / 3600


class DecayFunction(ABC):
    """Abstract base class for memory decay functions."""
    
    @abstractmethod
    def calculate(self, memory: MemoryItem, current_time: Optional[datetime] = None) -> float:
        """
        Calculate the current strength of a memory.
        
        Args:
            memory: The memory item to evaluate
            current_time: Optional custom current time
            
        Returns:
            Strength value between 0.0 (forgotten) and 1.0 (fully remembered)
        """
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Return the name of this decay function."""
        pass


class ExponentialDecay(DecayFunction):
    """
    Exponential decay: strength = e^(-lambda * t)
    Fast initial decay, then slows down.
    """
    
    def __init__(self, lambda_param: float = 0.1):
        """
        Initialize exponential decay.
        
        Args:
            lambda_param: Decay constant (higher = faster decay)
        """
        self.lambda_param = lambda_param
    
    def calculate(self, memory: MemoryItem, current_time: Optional[datetime] = None) -> float:
        age = memory.get_time_since_access_hours(current_time)
        base_strength = math.exp(-self.lambda_param * age)
        # Boost from importance and access count
        importance_boost = memory.importance * 0.5
        access_boost = min(memory.access_count * 0.05, 0.5)
        return min(1.0, base_strength + importance_boost + access_boost)
    
    def name(self) -> str:
        return f"exponential(lambda={self.lambda_param})"


class LogarithmicDecay(DecayFunction):
    """
    Logarithmic decay: strength = 1 - log(1 + t) / log(1 + max_t)
    Slower decay for recent memories, accelerates over time.
    """
    
    def __init__(self, max_hours: float = 168.0):  # 1 week default
        """
        Initialize logarithmic decay.
        
        Args:
            max_hours: Hours until memory reaches near-zero strength
        """
        self.max_hours = max_hours
    
    def calculate(self, memory: MemoryItem, current_time: Optional[datetime] = None) -> float:
        age = memory.get_time_since_access_hours(current_time)
        # Logarithmic decay formula
        log_decay = 1.0 - (math.log(1 + age) / math.log(1 + self.max_hours))
        # Importance modulation
        importance_factor = 0.5 + (memory.importance * 0.5)
        # Access count bonus (logarithmic bonus)
        access_bonus = math.log(1 + memory.access_count) * 0.1
        return min(1.0, max(0.0, log_decay * importance_factor + access_bonus))
    
    def name(self) -> str:
        return f"logarithmic(max_hours={self.max_hours})"


class LinearDecay(DecayFunction):
    """
    Linear decay: strength = max(0, 1 - t / max_t)
    Steady, predictable decay.
    """
    
    def __init__(self, max_hours: float = 720.0):  # 30 days default
        """
        Initialize linear decay.
        
        Args:
            max_hours: Hours until memory reaches zero strength
        """
        self.max_hours = max_hours
    
    def calculate(self, memory: MemoryItem, current_time: Optional[datetime] = None) -> float:
        age = memory.get_time_since_access_hours(current_time)
        linear_component = max(0.0, 1.0 - (age / self.max_hours))
        # Access count extends memory life
        access_extension = min(memory.access_count * 0.02, 0.3)
        importance_factor = 0.3 + (memory.importance * 0.7)
        return min(1.0, linear_component * importance_factor + access_extension)
    
    def name(self) -> str:
        return f"linear(max_hours={self.max_hours})"


class PowerLawDecay(DecayFunction):
    """
    Power law decay: strength = (1 + t)^(-alpha)
    Heavy-tailed, some memories persist much longer than others.
    """
    
    def __init__(self, alpha: float = 0.5):
        """
        Initialize power law decay.
        
        Args:
            alpha: Power law exponent (higher = faster initial decay)
        """
        self.alpha = alpha
    
    def calculate(self, memory: MemoryItem, current_time: Optional[datetime] = None) -> float:
        age = memory.get_time_since_access_hours(current_time)
        # Power law decay
        power_component = (1.0 + age) ** (-self.alpha)
        # Importance significantly affects persistence
        importance_multiplier = 0.5 + (memory.importance * 2.0)
        # Access count has strong effect in power law
        access_multiplier = 1.0 + (math.log(1 + memory.access_count) * 0.2)
        return min(1.0, power_component * importance_multiplier * access_multiplier)
    
    def name(self) -> str:
        return f"power_law(alpha={self.alpha})"


class MemoryDecaySimulator:
    """
    Simulator for agent memory decay patterns.
    
    Provides utilities for:
    - Tracking memory items with decay
    - Simulating memory access and retrieval
    - Analyzing decay patterns
    - Testing memory system behavior
    """
    
    def __init__(self, decay_function: Optional[DecayFunction] = None):
        """
        Initialize the simulator.
        
        Args:
            decay_function: The decay function to use (default: exponential)
        """
        self.decay_function = decay_function or ExponentialDecay(lambda_param=0.1)
        self.memories: Dict[str, MemoryItem] = {}
        self.current_time = datetime.now()
        self.decay_history: List[Dict] = []  # Track decay over time
    
    def add_memory(
        self,
        content: str,
        importance: float,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
    ) -> str:
        """
        Add a new memory to the simulator.
        
        Args:
            content: The memory content
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            created_at: Optional custom creation time
            
        Returns:
            Memory ID
        """
        memory_id = f"mem_{len(self.memories)}_{int(self.current_time.timestamp())}"
        memory = MemoryItem(
            content=content,
            importance=importance,
            created_at=created_at or self.current_time,
            last_accessed=self.current_time,
            access_count=0,
            tags=tags or [],
        )
        self.memories[memory_id] = memory
        return memory_id
    
    def access_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """
        Access a memory, refreshing its strength and access count.
        
        Args:
            memory_id: The ID of the memory to access
            
        Returns:
            The memory item, or None if not found
        """
        if memory_id not in self.memories:
            return None
        
        memory = self.memories[memory_id]
        memory.last_accessed = self.current_time
        memory.access_count += 1
        return memory
    
    def get_memory_strength(self, memory_id: str) -> Optional[float]:
        """
        Get the current strength of a memory.
        
        Args:
            memory_id: The ID of the memory
            
        Returns:
            Strength value, or None if memory not found
        """
        if memory_id not in self.memories:
            return None
        return self.decay_function.calculate(self.memories[memory_id], self.current_time)
    
    def advance_time(self, hours: float) -> None:
        """
        Advance the simulator's current time.
        
        Args:
            hours: Number of hours to advance
        """
        self.current_time = self.current_time + timedelta(hours=hours)
        self._record_decay_state()
    
    def _record_decay_state(self) -> None:
        """Record the current decay state for analysis."""
        state = {
            "timestamp": self.current_time.isoformat(),
            "memories": {},
        }
        for mem_id, memory in self.memories.items():
            state["memories"][mem_id] = {
                "strength": self.decay_function.calculate(memory, self.current_time),
                "content": memory.content[:50],  # Truncate for storage
                "access_count": memory.access_count,
            }
        self.decay_history.append(state)
    
    def get_forgotten_memories(self, threshold: float = 0.1) -> List[str]:
        """
        Get memories that have decayed below a threshold.
        
        Args:
            threshold: Strength threshold (default 0.1)
            
        Returns:
            List of memory IDs that have decayed below threshold
        """
        forgotten = []
        for mem_id in self.memories:
            strength = self.get_memory_strength(mem_id)
            if strength is not None and strength < threshold:
                forgotten.append(mem_id)
        return forgotten
    
    def get_strong_memories(self, threshold: float = 0.5) -> List[Tuple[str, float]]:
        """
        Get memories with strength above a threshold.
        
        Args:
            threshold: Strength threshold (default 0.5)
            
        Returns:
            List of (memory_id, strength) tuples
        """
        strong = []
        for mem_id in self.memories:
            strength = self.get_memory_strength(mem_id)
            if strength is not None and strength >= threshold:
                strong.append((mem_id, strength))
        return sorted(strong, key=lambda x: x[1], reverse=True)
    
    def get_decay_stats(self) -> Dict:
        """
        Get statistics about the current decay state.
        
        Returns:
            Dictionary with decay statistics
        """
        if not self.memories:
            return {
                "total_memories": 0,
                "avg_strength": 0.0,
                "strong_count": 0,
                "weak_count": 0,
                "forgotten_count": 0,
            }
        
        strengths = [self.get_memory_strength(mid) for mid in self.memories]
        return {
            "total_memories": len(self.memories),
            "avg_strength": sum(strengths) / len(strengths),
            "strong_count": sum(1 for s in strengths if s >= 0.5),
            "weak_count": sum(1 for s in strengths if 0.1 <= s < 0.5),
            "forgotten_count": sum(1 for s in strengths if s < 0.1),
        }
    
    def simulate_access_pattern(
        self,
        memory_id: str,
        access_intervals: List[float],
    ) -> List[float]:
        """
        Simulate a pattern of memory accesses.
        
        Args:
            memory_id: The memory to access
            access_intervals: Hours between each access
            
        Returns:
            List of strength values after each access
        """
        strengths = []
        for interval in access_intervals:
            self.advance_time(interval)
            self.access_memory(memory_id)
            strength = self.get_memory_strength(memory_id)
            if strength is not None:
                strengths.append(strength)
        return strengths
    
    def get_retrieval_quality_score(self, relevant_ids: List[str]) -> float:
        """
        Calculate a retrieval quality score based on decay patterns.
        
        The idea: memories that decay appropriately (not too fast, not too slow)
        provide better retrieval quality because they're neither stale nor noisy.
        
        Args:
            relevant_ids: IDs of memories relevant to current task
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not relevant_ids:
            return 0.0
        
        total_score = 0.0
        for mem_id in relevant_ids:
            strength = self.get_memory_strength(mem_id)
            if strength is not None:
                # Ideal strength for retrieval is around 0.5-0.8
                if strength >= 0.5:
                    total_score += strength
                else:
                    total_score += strength * 0.5  # Penalize weak memories
        
        return total_score / len(relevant_ids)
    
    def decay_all(self) -> None:
        """Record decay state for all memories (no time advance)."""
        self._record_decay_state()
    
    def clear(self) -> None:
        """Clear all memories and history."""
        self.memories.clear()
        self.decay_history.clear()
