"""
BrowseComp-Plus Benchmark Harness.

A fair and transparent evaluation benchmark for Deep-Research agents.
Uses a fixed corpus of ~100K human-verified documents.

Reference: https://github.com/texttron/BrowseComp-Plus
Paper: https://arxiv.org/abs/2508.06600
Dataset: https://huggingface.co/datasets/Tevatron/browsecomp-plus
"""

from .adapter import BrowseCompPlusHarness, BrowseCompPlusAdapter

__all__ = ["BrowseCompPlusHarness", "BrowseCompPlusAdapter"]
