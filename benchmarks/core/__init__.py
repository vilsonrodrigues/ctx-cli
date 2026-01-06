"""
ECM Benchmark Core Infrastructure.

Provides shared components for all benchmark harnesses:
- BaseAgent: Abstract agent interface
- HarnessProtocol: Abstract harness interface
- Metrics: Token and correctness tracking
- Agents: ECM, Linear, RAG baselines
"""

from benchmarks.core.base_agent import BaseAgent, AgentResult, ComparisonResult
from benchmarks.core.harness_protocol import (
    OfficialHarness,
    HarnessTask,
    HarnessResult,
    CorrectnessMetrics,
)
from benchmarks.core.metrics import (
    TokenMetrics,
    KnowledgeMetrics,
    NavigationMetrics,
    UtilityMetrics,
    ECMMetrics,
    MetricsCollector,
    TaskTokenRecord,
    CumulativeTokenReport,
    compare_token_reports,
)

__all__ = [
    # Base interfaces
    "BaseAgent",
    "AgentResult",
    "ComparisonResult",
    "OfficialHarness",
    "HarnessTask",
    "HarnessResult",
    "CorrectnessMetrics",
    # Metrics
    "TokenMetrics",
    "KnowledgeMetrics",
    "NavigationMetrics",
    "UtilityMetrics",
    "ECMMetrics",
    "MetricsCollector",
    "TaskTokenRecord",
    "CumulativeTokenReport",
    "compare_token_reports",
]
