"""
OSWorld Harness Integration.

Provides integration with the official OSWorld benchmark for
evaluating multimodal agents on desktop automation tasks.

Reference: https://github.com/xlang-ai/OSWorld
Note: Requires VM setup (Docker or VMware/VirtualBox)
"""

from benchmarks.harnesses.osworld.adapter import OSWorldHarness, OSWorldAdapter

__all__ = ["OSWorldHarness", "OSWorldAdapter"]
