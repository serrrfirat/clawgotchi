"""
Tests for Context Compressor.
"""

import unittest
from utils.context_compressor import ContextCompressor, CompressionResult


class TestContextCompressor(unittest.TestCase):
    def setUp(self):
        self.compressor = ContextCompressor(max_tokens=500, avg_chars_per_token=4)

    def test_no_compression_needed(self):
        """Small content under limit needs no compression."""
        content = "Hello world"
        result = self.compressor.compress(content)

        self.assertEqual(result.stage, 0)
        self.assertEqual(result.compression_ratio, 1.0)
        self.assertEqual(result.content, content)

    def test_stage1_trims_whitespace(self):
        """Stage 1 removes extra whitespace."""
        content = "Hello\n\n\n\nWorld\n\n"
        result = self.compressor.compress(content, target_stage=1)

        self.assertIn("whitespace_trimmed", result.removed_elements)
        self.assertNotIn("\n\n\n", result.content)

    def test_stage2_summarizes_code_blocks(self):
        """Stage 2 replaces code blocks with summaries."""
        content = "```python\ndef hello():\n    print('hi')\n```\nSome text"
        result = self.compressor.compress(content, target_stage=2)

        self.assertIn("summarized_1_code_blocks", result.removed_elements)
        self.assertNotIn("def hello", result.content)
        self.assertIn("Code block", result.content)

    def test_stage3_drops_old_turns(self):
        """Stage 3 drops old conversation turns."""
        content = """
        Human: Turn 1
        Assistant: Response 1
        Human: Turn 2
        Assistant: Response 2
        Human: Turn 3
        Assistant: Response 3
        Human: Turn 4
        Assistant: Response 4
        Human: Turn 5
        Assistant: Response 5
        Human: Turn 6
        Assistant: Response 6
        Human: Turn 7
        Assistant: Response 7
        Human: Turn 8
        Assistant: Response 8
        Human: Turn 9
        Assistant: Response 9
        Human: Turn 10
        Assistant: Response 10
        Human: Turn 11
        Assistant: Response 11
        """
        result = self.compressor.compress(content, target_stage=3)

        self.assertIn("dropped_old_conversation_turns", result.removed_elements)
        # Should keep last 10 turns (roughly)
        self.assertIn("Turn 11", result.content)
        self.assertNotIn("Turn 1", result.content)

    def test_stage4_extracts_key_facts(self):
        """Stage 4 keeps only key facts (headers, lists)."""
        content = """
        # Header 1
        This is a very long paragraph that contains a lot of verbose text that
        should be removed because it doesn't contain essential information.
        We are just filling space here to test the compression logic.

        - Important point 1
        - Important point 2

        Another long paragraph that should be removed because we only care about
        the key facts and important details.

        ## Subheader
        More verbose text that doesn't matter.
        """
        result = self.compressor.compress(content, target_stage=4)

        self.assertIn("extracted_key_facts_only", result.removed_elements)
        self.assertIn("# Header 1", result.content)
        self.assertIn("Important point 1", result.content)
        self.assertNotIn("verbose text", result.content)

    def test_compression_ratio_calculates_correctly(self):
        """Compression ratio is calculated correctly."""
        content = "Hello\n\n\nWorld"  # Will be trimmed
        result = self.compressor.compress(content, target_stage=1)

        self.assertLessEqual(result.compression_ratio, 1.0)
        self.assertGreater(result.compression_ratio, 0.0)

    def test_max_tokens_detection(self):
        """Auto-detects correct compression stage."""
        # Small content
        small = "Hi"
        self.assertEqual(self.compressor.get_compression_needed(small), 0)

        # Content under 500 tokens (2000 chars)
        medium = "x" * 1000
        self.assertEqual(self.compressor.get_compression_needed(medium), 0)

    def test_empty_content_handled(self):
        """Empty content is handled gracefully."""
        result = self.compressor.compress("")
        self.assertEqual(result.stage, 0)
        self.assertEqual(result.compressed_length, 0)


if __name__ == "__main__":
    unittest.main()
