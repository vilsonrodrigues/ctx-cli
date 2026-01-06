"""
SWE-Bench-CL Harness Integration.

Provides integration with the official SWE-Bench-CL benchmark for
evaluating continual learning in code agents.

Reference: https://github.com/thomasjoshi/agents-never-forget
"""

from benchmarks.harnesses.swe_bench_cl.adapter import SWEBenchCLHarness, SWEBenchCLAdapter

__all__ = ["SWEBenchCLHarness", "SWEBenchCLAdapter"]
