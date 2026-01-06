"""
AppWorld Harness Integration.

Provides integration with the official AppWorld benchmark for
evaluating interactive code generation across 9 simulated applications.

Reference: https://github.com/StonyBrookNLP/appworld
"""

from benchmarks.harnesses.appworld.adapter import AppWorldHarness, AppWorldAdapter

__all__ = ["AppWorldHarness", "AppWorldAdapter"]
