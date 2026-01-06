"""
Benchmark size configurations for ECM evaluation.

Supports mini (development/quick validation) and full (paper) modes.
"""

from dataclasses import dataclass
from typing import Literal

BenchmarkSize = Literal["mini", "full"]


@dataclass
class BenchmarkConfig:
    """Configuration for a specific benchmark size."""
    max_tasks: int = 10
    max_chunks: int = 10
    sub_datasets: list[str] | None = None
    environments: list[str] | None = None
    repos: list[str] | None = None
    max_sessions: int = 10
    max_samples: int = 20
    datasets_count: int = 3


# Mini configurations - for quick development and validation
MINI_CONFIGS = {
    "memoryagentbench": BenchmarkConfig(
        max_chunks=10,
        # TTL (Test_Time_Learning) - tests learning during execution, not just retrieval
        sub_datasets=["TTL"],
    ),
    "swe_bench_cl": BenchmarkConfig(
        max_tasks=5,
        repos=["django"],
    ),
    "locomo": BenchmarkConfig(
        max_sessions=5,
    ),
    "memorybench": BenchmarkConfig(
        max_samples=20,
        datasets_count=3,
    ),
    "lifelong_agent_bench": BenchmarkConfig(
        max_tasks=10,
        environments=["db"],
    ),
    "ltm_benchmark": BenchmarkConfig(
        max_sessions=5,
    ),
    "appworld": BenchmarkConfig(
        max_tasks=5,
    ),
    "osworld": BenchmarkConfig(
        max_tasks=5,
    ),
    "agentcompany": BenchmarkConfig(
        max_tasks=5,
    ),
}

# Full configurations - for paper benchmarks
FULL_CONFIGS = {
    "memoryagentbench": BenchmarkConfig(
        max_chunks=100,
        # TTL, LRU, CR - focus on learning, understanding, and reasoning
        # AR excluded: it's retrieval-oriented (book QA), not continual learning
        sub_datasets=["TTL", "LRU", "CR"],
    ),
    "swe_bench_cl": BenchmarkConfig(
        max_tasks=50,
        repos=["django", "flask", "requests", "tornado"],
    ),
    "locomo": BenchmarkConfig(
        max_sessions=100,
    ),
    "memorybench": BenchmarkConfig(
        max_samples=500,
        datasets_count=11,
    ),
    "lifelong_agent_bench": BenchmarkConfig(
        max_tasks=100,
        environments=["db", "os", "kg"],
    ),
    "ltm_benchmark": BenchmarkConfig(
        max_sessions=50,
    ),
    "appworld": BenchmarkConfig(
        max_tasks=50,
    ),
    "osworld": BenchmarkConfig(
        max_tasks=50,
    ),
    "agentcompany": BenchmarkConfig(
        max_tasks=50,
    ),
}


def get_config(benchmark: str, size: BenchmarkSize = "mini") -> BenchmarkConfig:
    """
    Get benchmark configuration for the specified size.
    
    Args:
        benchmark: Benchmark name (e.g., "memoryagentbench", "swe_bench_cl")
        size: "mini" for quick runs, "full" for paper benchmarks
        
    Returns:
        BenchmarkConfig with appropriate settings
    """
    configs = MINI_CONFIGS if size == "mini" else FULL_CONFIGS
    
    if benchmark not in configs:
        available = ", ".join(configs.keys())
        raise ValueError(f"Unknown benchmark: {benchmark}. Available: {available}")
    
    return configs[benchmark]


def list_benchmarks() -> list[str]:
    """List all available benchmarks."""
    return list(MINI_CONFIGS.keys())


def get_all_configs(size: BenchmarkSize = "mini") -> dict[str, BenchmarkConfig]:
    """Get all configurations for a size."""
    return MINI_CONFIGS.copy() if size == "mini" else FULL_CONFIGS.copy()
