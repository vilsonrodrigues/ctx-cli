"""
LifelongAgentBench Harness Integration.

Provides integration with the official LifelongAgentBench benchmark for
evaluating skill reuse across Database, Operating System, and Knowledge Graph environments.

Reference: https://github.com/caixd-220529/LifelongAgentBench
"""

from benchmarks.harnesses.lifelong_agent_bench.adapter import (
    LifelongAgentBenchHarness,
    LifelongAgentBenchAdapter,
)

__all__ = ["LifelongAgentBenchHarness", "LifelongAgentBenchAdapter"]
