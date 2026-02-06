"""
Context Compressor - Implements the Context Compression Ladder pattern.

Stages:
1. Trim whitespace and formatting
2. Summarize verbose sections
3. Drop low-relevance history
4. Extract key facts only
5. Reset with handoff document
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class CompressionResult:
    """Result of a compression operation."""
    original_length: int
    compressed_length: int
    compression_ratio: float
    stage: int
    content: str
    removed_elements: List[str]


class ContextCompressor:
    """Systematic context compression through 5 stages."""

    def __init__(self, max_tokens: int = 60000, avg_chars_per_token: int = 4):
        self.max_tokens = max_tokens
        self.avg_chars_per_token = avg_chars_per_token
        self.max_chars = max_tokens * avg_chars_per_token

    def _count_tokens(self, text: str) -> int:
        """Rough token count."""
        return len(text) // self.avg_chars_per_token

    def _detect_stage(self, content: str) -> int:
        """Detect which compression stage we need."""
        token_count = self._count_tokens(content)
        if token_count <= self.max_tokens:
            return 0  # No compression needed
        elif token_count <= self.max_tokens * 1.5:
            return 1  # Stage 1: Trim whitespace
        elif token_count <= self.max_tokens * 3:
            return 2  # Stage 2: Summarize verbose sections
        elif token_count <= self.max_tokens * 5:
            return 3  # Stage 3: Drop low-relevance history
        elif token_count <= self.max_tokens * 10:
            return 4  # Stage 4: Extract key facts
        else:
            return 5  # Stage 5: Handoff document needed

    def compress(self, content: str, target_stage: Optional[int] = None) -> CompressionResult:
        """
        Compress content through the appropriate stage.

        Args:
            content: The text to compress
            target_stage: Specific stage to apply, or auto-detect if None

        Returns:
            CompressionResult with compressed content and metadata
        """
        stage = target_stage if target_stage else self._detect_stage(content)
        original_length = len(content)
        removed_elements = []

        if stage == 0:
            return CompressionResult(
                original_length=original_length,
                compressed_length=original_length,
                compression_ratio=1.0,
                stage=0,
                content=content,
                removed_elements=[]
            )

        # Stage 1: Trim whitespace and formatting
        if stage >= 1:
            # Remove extra blank lines (keep max 1)
            content = re.sub(r'\n{3,}', '\n\n', content)
            # Remove trailing whitespace
            content = '\n'.join(line.rstrip() for line in content.split('\n'))
            # Remove leading whitespace on lines
            content = re.sub(r'^ +', '', content, flags=re.MULTILINE)
            # Collapse multiple spaces to single
            content = re.sub(r' {2,}', ' ', content)
            removed_elements.append("whitespace_trimmed")

        # Stage 2: Summarize verbose sections
        if stage >= 2:
            # Summarize code blocks (replace with placeholder)
            code_block_pattern = r'```[\s\S]*?```'
            code_blocks = re.findall(code_block_pattern, content)
            for i, block in enumerate(code_blocks):
                summary = f"[Code block {i+1} with {block.count(chr(10))+1} lines]"
                content = content.replace(block, summary, 1)
            if code_blocks:
                removed_elements.append(f"summarized_{len(code_blocks)}_code_blocks")

            # Summarize long function outputs/logs
            log_pattern = r'(?:DEBUG|INFO|WARNING|ERROR|TRACE):.*\n{2,}'
            content = re.sub(log_pattern, '[log output]\n', content)

        # Stage 3: Drop low-relevance history
        if stage >= 3:
            # Remove older conversation turns (keep last N)
            # Match patterns like "Human:", "Assistant:", "User:", "Agent:"
            turn_pattern = r'(Human|User|Assistant|Agent): '
            parts = re.split(turn_pattern, content)
            # re.split with capturing group returns: [prefix, "Human", content, "Assistant", content, ...]
            # Build list of actual turn contents
            turn_contents = []
            i = 1  # Start after first prefix
            while i < len(parts):
                # parts[i] is the turn speaker, parts[i+1] is the content
                if i + 1 < len(parts):
                    speaker = parts[i]
                    turn_text = parts[i + 1]
                    turn_contents.append(f"{speaker}: {turn_text}")
                i += 2

            if len(turn_contents) > 10:
                # Keep last 10 turns
                content = ''.join(turn_contents[-10:])
                removed_elements.append("dropped_old_conversation_turns")

        # Stage 4: Extract key facts only
        if stage >= 4:
            # Extract key facts from markdown
            # Keep only: headers, list items, quotes
            # Remove: all prose paragraphs
            lines = content.split('\n')
            key_facts = []
            for line in lines:
                stripped = line.strip()
                # Keep headers
                if stripped.startswith('#'):
                    key_facts.append(line)
                # Keep list items
                elif stripped.startswith(('- ', '*', '1.', '2.', '3.')):
                    key_facts.append(line)
                # Keep quotes
                elif stripped.startswith('>'):
                    key_facts.append(line)
                # Skip prose paragraphs

            content = '\n'.join(key_facts)
            removed_elements.append("extracted_key_facts_only")

        compressed_length = len(content)
        ratio = compressed_length / original_length if original_length > 0 else 1.0

        return CompressionResult(
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=ratio,
            stage=stage,
            content=content,
            removed_elements=removed_elements
        )

    def get_compression_needed(self, content: str) -> int:
        """Get the minimum compression stage needed."""
        return self._detect_stage(content)


def compress_file(path: str, stage: Optional[int] = None) -> CompressionResult:
    """Compress a file and return the result."""
    content = Path(path).read_text()
    compressor = ContextCompressor()
    return compressor.compress(content, stage)


if __name__ == "__main__":
    # Demo
    sample = """
    Human: Hello there!

    Assistant: Hi! How can I help you today?

    Human: I need to understand context compression for my AI agents.

    Assistant: Great question! Context compression is important for managing token limits.
    Let me explain the 5-stage ladder:

    ## Stage 1: Trim Whitespace
    Remove extra blank lines and spaces. Often saves 10-20%.

    ## Stage 2: Summarize Verbose Sections
    Replace detailed logs with summaries. Replace full file contents with relevant excerpts.

    ## Stage 3: Drop Low-Relevance History
    Older turns that are not directly relevant can be dropped.

    ## Stage 4: Extract Key Facts Only
    Replace full context with a bullet list of facts the model needs to know.

    ## Stage 5: Reset with Handoff
    Create a fresh session with a handoff document.

    Human: That's really helpful! Thanks.

    Assistant: You're welcome! Let me know if you need anything else.
    """

    compressor = ContextCompressor()
    result = compressor.compress(sample, stage=3)

    print(f"Original: {result.original_length} chars")
    print(f"Compressed: {result.compressed_length} chars")
    print(f"Ratio: {result.compression_ratio:.2%}")
    print(f"Stage: {result.stage}")
    print(f"Removed: {result.removed_elements}")
    print("\n--- Compressed Content ---")
    print(result.content)
