"""
GAIA Benchmark Harness Adapter.

Integrates ECM agent with the GAIA benchmark for evaluating
general AI assistant capabilities with multi-step reasoning.

Reference: https://huggingface.co/datasets/gaia-benchmark/GAIA
Paper: https://arxiv.org/abs/2311.12983

Features:
- 450+ questions across 3 difficulty levels
- Multi-modal support (text, images, PDFs, audio)
- Tool use and web browsing required
- Unambiguous, verifiable answers
"""

import json
import time
from pathlib import Path
from typing import Iterator, Optional

# Import official ECM prompts
from prompts import SYSTEM_PROMPT_ECM

from benchmarks.core.harness_protocol import (
    OfficialHarness,
    HarnessTask,
    HarnessResult,
    CorrectnessMetrics,
    HarnessAdapter,
)
from benchmarks.core.metrics import CumulativeTokenReport


class GAIAHarness(OfficialHarness):
    """
    Official harness for GAIA benchmark.

    GAIA tests general AI assistants on real-world tasks requiring:
    - Multi-step reasoning
    - Tool use (web search, code execution, etc.)
    - Multi-modal understanding
    - Factual accuracy with verifiable answers
    """

    LEVELS = [1, 2, 3]  # Difficulty levels

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize GAIA harness.

        Args:
            data_dir: Directory containing tasks.json
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)

        self._tasks: list[dict] = []
        self._current_level: Optional[int] = None

    @property
    def name(self) -> str:
        return "gaia"

    @property
    def task_type(self) -> str:
        return "long_horizon"

    def setup(self) -> bool:
        """Load GAIA tasks from data file."""
        tasks_file = self.data_dir / "tasks.json"

        if tasks_file.exists():
            with open(tasks_file) as f:
                self._tasks = json.load(f)
            print(f"[GAIA] Loaded {len(self._tasks)} tasks from {tasks_file}")

            # Count by level
            levels = {}
            for task in self._tasks:
                level = task.get("level", 0)
                levels[level] = levels.get(level, 0) + 1
            print(f"[GAIA] Tasks by level: {levels}")

            return True
        else:
            print(f"[GAIA] No tasks.json found at {tasks_file}")
            print("[GAIA] Run: uv run benchmarks/scripts/download_datasets.py --benchmark gaia")
            print("[GAIA] Note: GAIA is a gated dataset - accept terms at HuggingFace first")
            return False

    def get_sequence_ids(self) -> list[str]:
        """Get available difficulty levels."""
        return [f"level_{l}" for l in self.LEVELS]

    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """
        Load GAIA tasks.

        Args:
            config: dict with keys:
                - level: int - Filter by level (1, 2, 3)
                - max_tasks: int - Maximum tasks to load
        """
        level_filter = config.get("level", None)
        max_tasks = config.get("max_tasks", 999)

        # Filter by level if specified
        if level_filter:
            filtered_tasks = [t for t in self._tasks if t.get("level") == level_filter]
        else:
            filtered_tasks = self._tasks

        # Sort by level for progressive difficulty
        filtered_tasks = sorted(filtered_tasks, key=lambda t: t.get("level", 0))

        # Limit to max_tasks
        filtered_tasks = filtered_tasks[:max_tasks]

        for i, task_data in enumerate(filtered_tasks):
            yield HarnessTask(
                task_id=task_data.get("task_id", f"gaia_{i:04d}"),
                task_type="long_horizon",
                instruction=task_data.get("question", ""),
                metadata={
                    "level": task_data.get("level", 1),
                    "file_name": task_data.get("file_name", ""),
                    "file_path": task_data.get("file_path", ""),
                    "annotator_metadata": task_data.get("annotator_metadata", {}),
                    "sequence_position": i,
                },
                dependencies=task_data.get("dependencies", []),
                ground_truth=task_data.get("final_answer", ""),
                difficulty=self._level_to_difficulty(task_data.get("level", 1)),
            )

    def _level_to_difficulty(self, level: int) -> str:
        """Convert level to difficulty string."""
        if level == 1:
            return "easy"
        elif level == 2:
            return "medium"
        else:
            return "hard"

    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """Execute agent's action for a GAIA task."""
        start_time = time.time()
        execution_log = []

        execution_log.append(f"Task: {task.task_id}")
        execution_log.append(f"Level: {task.metadata.get('level', 'unknown')}")

        # Check if task requires file
        file_path = task.metadata.get("file_path", "")
        if file_path:
            execution_log.append(f"Required file: {file_path}")

        execution_time = time.time() - start_time

        return HarnessResult(
            task_id=task.task_id,
            success=False,  # Set by verify_result
            agent_output=agent_action,
            execution_log=execution_log,
            execution_time_seconds=execution_time,
        )

    def verify_result(self, task: HarnessTask, result: HarnessResult) -> bool:
        """
        Verify answer correctness.

        GAIA uses exact match evaluation for most tasks.
        """
        expected = task.ground_truth or ""
        actual = result.agent_output.strip()

        # Normalize for comparison
        expected_norm = expected.lower().strip()
        actual_norm = actual.lower().strip()

        # Check for exact match
        if expected_norm == actual_norm:
            result.success = True
            result.partial_score = 1.0
            result.execution_log.append("Exact match!")
        elif expected_norm in actual_norm:
            # Answer contains expected - partial credit
            result.success = True
            result.partial_score = 0.8
            result.execution_log.append("Contains expected answer")
        else:
            result.success = False
            result.partial_score = 0.0
            result.execution_log.append(f"Expected: {expected[:50]}...")

        return result.success

    def reset_environment(self) -> None:
        """Reset for new evaluation."""
        self._current_level = None

    def start_project(self, project_name: str) -> None:
        """Start a new ECM project."""
        pass

    def teardown(self) -> None:
        """Clean up resources."""
        pass


class GAIAAdapter(HarnessAdapter):
    """
    ECM-specific adapter for GAIA.

    Handles:
    - Progressive difficulty (level 1 → 2 → 3)
    - Multi-step reasoning with memory
    - Tool use patterns
    """

    # Task-specific context (appended to ECM base prompt)
    TASK_INSTRUCTIONS = """
# GAIA Context

General AI assistant tasks requiring:
- Web search, code execution, multi-step reasoning
- File analysis (images, PDFs, audio when provided)
- Factual accuracy with verifiable answers

## Scope Naming
Use: `gaia/<task_id>` (e.g., `gaia/q0042`)

## What to Note
- "Strategy: Wikipedia disambiguation for ambiguous names"
- "Pattern: Date questions need multiple source verification"

## Answer Format
GAIA expects exact answers only - no explanation:
- Q: "Capital of France?" → A: "Paris"
- Q: "2+2?" → A: "4"
"""

    SYSTEM_PROMPT = SYSTEM_PROMPT_ECM + TASK_INSTRUCTIONS

    def __init__(self, harness: GAIAHarness, agent, model: str = "gpt-4.1-mini"):
        super().__init__(harness, agent, model)
        self.harness: GAIAHarness = harness

    def run_sequence(
        self,
        config: dict,
        reset_between_tasks: bool = False,
    ) -> tuple[CumulativeTokenReport, CorrectnessMetrics]:
        """
        Run GAIA evaluation.

        Args:
            config: Configuration with 'level', 'max_tasks', etc.
            reset_between_tasks: Should be False to maintain learned patterns
        """
        level = config.get("level", None)
        project_name = f"gaia-level-{level}" if level else "gaia-all"

        if hasattr(self.agent, 'store'):
            self.agent.store.checkout(
                project_name,
                note=f"Starting GAIA evaluation",
                create=True
            )

        return super().run_sequence(config, reset_between_tasks=False)

    def _build_prompt(self, task: HarnessTask) -> str:
        """Build prompt for a GAIA task."""
        parts = [
            f"# Task: {task.task_id}",
            f"\n## Level: {task.metadata.get('level', 'unknown')}",
            f"\n## Question:\n{task.instruction}",
        ]

        # Add file context if present
        file_name = task.metadata.get("file_name", "")
        if file_name:
            parts.append(f"\n## Attached File: {file_name}")
            parts.append("(File content should be analyzed to answer)")

        # Add context from previous tasks
        position = task.metadata.get("sequence_position", 0)
        if position > 0:
            parts.append(
                f"\n## Context:\nThis is question #{position + 1}. "
                f"Use `notes` to recall patterns from earlier questions."
            )

        parts.append("\n## Your Answer:")

        return "\n".join(parts)
