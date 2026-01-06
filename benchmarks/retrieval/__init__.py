"""
Retrieval Benchmarks.

These benchmarks evaluate memory retrieval capabilities but are NOT
continual learning benchmarks. They test single-session QA over
accumulated knowledge (like book comprehension).

Included:
- LOCOMO: Long-context memory evaluation
- MemoryAgentBench: Book QA and adaptive retrieval

Note: These are useful baselines but should NOT be the primary
evaluation for ECM's continual learning claims.
"""

from benchmarks.retrieval.run_locomo_semantic import *
from benchmarks.retrieval.run_locomo_style import *
