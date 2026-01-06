"""
ECM Benchmark Adapters.

Provides adapters for integrating ECM with various benchmark frameworks.
"""

from .ecm_adapter import (
    ECMAgentWrapper,
    create_ecm_agent_for_benchmark,
    get_ecm_agent_config,
    get_ecm_dataset_config,
)

__all__ = [
    "ECMAgentWrapper",
    "create_ecm_agent_for_benchmark",
    "get_ecm_agent_config",
    "get_ecm_dataset_config",
]
