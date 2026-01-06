"""
Common utilities for ECM benchmarks.

This module provides shared components:
- BaseAgent: Abstract base class for all benchmark agents
- Metrics: Scoring and evaluation utilities
- DatasetLoaders: Functions to load benchmark datasets
"""

from .base_agent import BaseAgent, AgentResult, ComparisonResult
from .metrics import compute_f1, compute_exact_match, compute_contains_match
from .dataset_loaders import (
    load_memoryagentbench,
    chunk_context,
    MEMORYAGENTBENCH_SPLITS,
)

__all__ = [
    "BaseAgent",
    "AgentResult",
    "ComparisonResult",
    "compute_f1",
    "compute_exact_match",
    "compute_contains_match",
    "load_memoryagentbench",
    "chunk_context",
    "MEMORYAGENTBENCH_SPLITS",
]
