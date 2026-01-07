"""
SWE-Bench-CL Harness Adapter.

Integrates ECM agent with the official SWE-Bench-CL benchmark.
Uses real GitHub issues organized into chronological sequences
for continual learning evaluation.

Reference: https://github.com/thomasjoshi/agents-never-forget
Paper: https://arxiv.org/abs/2507.00014
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

# Import official ECM prompts
from prompts import SYSTEM_PROMPT_ECM

from benchmarks.core.harness_protocol import (
    OfficialHarness,
    HarnessTask,
    HarnessResult,
    CorrectnessMetrics,
    HarnessAdapter,
)
from benchmarks.core.metrics import CumulativeTokenReport, TaskTokenRecord


@dataclass
class SWEBenchCLTask:
    """Extended task data for SWE-Bench-CL."""
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: str
    created_at: str
    gold_patch: str
    test_patch: str
    difficulty: str
    sequence_position: int
    dependencies: list[str]


class SWEBenchCLHarness(OfficialHarness):
    """
    Official harness for SWE-Bench-CL benchmark.

    SWE-Bench-CL organizes tasks into chronological sequences per repository,
    testing knowledge retention and forward transfer across related issues.
    """

    DATA_FILE = "SWE-Bench-CL-Curriculum.json"

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize SWE-Bench-CL harness.

        Args:
            data_dir: Directory containing SWE-Bench-CL-Curriculum.json
                     Defaults to benchmarks/harnesses/swe_bench_cl/data/
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)
        self.data_path = self.data_dir / self.DATA_FILE

        self._curriculum: Optional[dict] = None
        self._docker_available: Optional[bool] = None
        self._current_sequence: Optional[str] = None

    @property
    def name(self) -> str:
        return "swe-bench-cl"

    @property
    def task_type(self) -> str:
        return "continual_learning"

    def setup(self) -> bool:
        """
        Setup harness environment.

        Checks:
        1. Data file exists
        2. Docker is available for test execution
        """
        # Check data file
        if not self.data_path.exists():
            print(f"[SWE-Bench-CL] Data file not found: {self.data_path}")
            print(f"[SWE-Bench-CL] Run: git clone https://github.com/thomasjoshi/agents-never-forget")
            return False

        # Load curriculum
        try:
            with open(self.data_path) as f:
                self._curriculum = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[SWE-Bench-CL] Invalid JSON in data file: {e}")
            return False

        # Check Docker
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            self._docker_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._docker_available = False

        if not self._docker_available:
            print("[SWE-Bench-CL] Docker not available - test execution will be simulated")

        return True

    def get_sequence_ids(self) -> list[str]:
        """Get available repository sequences."""
        if self._curriculum is None:
            return []
        sequences = self._curriculum.get("sequences", [])
        return [seq.get("id", "") for seq in sequences]

    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """
        Load tasks from a specific sequence.

        Args:
            config: dict with keys:
                - sequence: str - Repository sequence ID (e.g., 'django')
                - max_tasks: int - Maximum tasks to load (default: all)
                - split: str - Dataset split (default: 'test')
        """
        if self._curriculum is None:
            raise RuntimeError("Harness not setup. Call setup() first.")

        sequence_id = config.get("sequence", "django")
        max_tasks = config.get("max_tasks", 999)

        self._current_sequence = sequence_id

        # Handle real data format (list of sequence dicts)
        sequences = self._curriculum.get("sequences", [])

        # Find matching sequence
        sequence_data = None
        available_sequences = []

        for seq in sequences:
            seq_id = seq.get("id", "")
            repo = seq.get("repo", "")
            # Match by sequence id or repo name
            available_sequences.append(seq_id)
            if sequence_id in seq_id or sequence_id in repo or seq_id.startswith(sequence_id):
                sequence_data = seq
                break

        if sequence_data is None:
            available = ", ".join(available_sequences)
            raise ValueError(f"Unknown sequence: {sequence_id}. Available: {available}")

        tasks = sequence_data.get("tasks", [])

        # Sort by creation date for chronological order
        tasks = sorted(tasks, key=lambda t: t.get("metadata", {}).get("created_at", ""))

        # Limit tasks
        tasks = tasks[:max_tasks]

        # Build dependency graph
        task_ids = []
        for t in tasks:
            task_id = t.get("metadata", {}).get("instance_id") or f"task_{len(task_ids)}"
            task_ids.append(task_id)

        for i, task_data in enumerate(tasks):
            # Extract from nested structure
            metadata = task_data.get("metadata", {})
            task_info = task_data.get("task", {})
            evaluation = task_data.get("evaluation", {})
            cl_info = task_data.get("continual_learning", {})

            task_id = metadata.get("instance_id") or f"task_{i}"

            # Dependencies from CL info or all previous tasks
            dependencies = cl_info.get("dependencies", task_ids[:i] if i > 0 else [])

            yield HarnessTask(
                task_id=task_id,
                task_type="continual_learning",
                instruction=task_info.get("problem_statement", ""),
                metadata={
                    "repo": metadata.get("repo", sequence_data.get("repo", "")),
                    "base_commit": metadata.get("base_commit", ""),
                    "hints": task_info.get("hints_text", ""),
                    "created_at": metadata.get("created_at", ""),
                    "difficulty": metadata.get("difficulty", "medium"),
                    "sequence_position": cl_info.get("sequence_position", i),
                    "modified_files": cl_info.get("modified_files", []),
                },
                dependencies=dependencies,
                ground_truth=evaluation.get("patch", ""),
                repo=metadata.get("repo", sequence_data.get("repo", "")),
                difficulty=metadata.get("difficulty", "medium"),
            )

    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """
        Execute agent's proposed patch.

        For SWE-Bench-CL, agent_action should be a git diff patch.
        """
        start_time = time.time()
        execution_log = []

        # Parse agent action as patch
        patch = self._extract_patch(agent_action)
        execution_log.append(f"Extracted patch: {len(patch)} bytes")

        # In a real implementation, this would:
        # 1. Clone the repository at base_commit
        # 2. Apply the patch
        # 3. Run the test suite

        execution_time = time.time() - start_time

        return HarnessResult(
            task_id=task.task_id,
            success=False,  # Will be set by verify_result
            agent_output=agent_action,
            execution_log=execution_log,
            execution_time_seconds=execution_time,
        )

    def verify_result(self, task: HarnessTask, result: HarnessResult) -> bool:
        """
        Run official test suite to verify patch correctness.

        This is the ONLY valid way to verify SWE-Bench-CL results.
        Never use heuristic matching.
        """
        if not self._docker_available:
            # Simulation mode - for development only
            # In production, this should fail or warn loudly
            patch = self._extract_patch(result.agent_output)
            gold_patch = task.ground_truth or ""

            # Very rough similarity check (NOT for real evaluation)
            if not patch or not gold_patch:
                return False

            # Check if key changes are present
            patch_lines = set(patch.strip().split('\n'))
            gold_lines = set(gold_patch.strip().split('\n'))

            overlap = len(patch_lines & gold_lines)
            similarity = overlap / max(len(gold_lines), 1)

            result.partial_score = similarity
            result.success = similarity > 0.5  # Very lenient for dev

            result.execution_log.append(
                f"[SIMULATED] Patch similarity: {similarity:.2%}"
            )
            result.execution_log.append(
                "[WARNING] Real evaluation requires Docker for test execution"
            )

            return result.success

        # Real Docker-based test execution
        try:
            success = self._run_tests_in_docker(task, result)
            result.success = success
            return success
        except Exception as e:
            result.error_message = str(e)
            result.success = False
            return False

    def reset_environment(self) -> None:
        """Reset for new evaluation sequence."""
        self._current_sequence = None

    def start_project(self, project_name: str) -> None:
        """Start a new ECM project for this sequence."""
        # This will be called by the adapter to initialize ECM state
        pass

    def teardown(self) -> None:
        """Clean up Docker containers if any."""
        pass

    def _extract_patch(self, agent_output: str) -> str:
        """Extract git diff patch from agent output."""
        # Look for diff markers
        lines = agent_output.split('\n')
        in_diff = False
        patch_lines = []

        for line in lines:
            if line.startswith('diff --git') or line.startswith('---') or line.startswith('+++'):
                in_diff = True

            if in_diff:
                patch_lines.append(line)

            if line.startswith('@@') or (in_diff and not line.startswith(('+', '-', ' ', '@', 'd', '-', '+'))):
                # Still in diff context
                pass

        # If no diff found, return the whole output
        if not patch_lines:
            return agent_output.strip()

        return '\n'.join(patch_lines)

    def _run_tests_in_docker(self, task: HarnessTask, result: HarnessResult) -> bool:
        """Run tests in Docker container."""
        # This would use the official SWE-bench evaluation harness
        # For now, placeholder implementation

        result.execution_log.append("[Docker] Starting test execution...")

        # In real implementation:
        # 1. docker run swebench/evaluation:latest ...
        # 2. Apply patch to repo
        # 3. Run pytest/unittest
        # 4. Parse results

        result.execution_log.append("[Docker] Test execution not yet implemented")
        return False


class SWEBenchCLAdapter(HarnessAdapter):
    """
    ECM-specific adapter for SWE-Bench-CL.

    Handles:
    - Creating ECM project per sequence
    - Task prompt formatting
    - Memory persistence across sequence tasks
    """

    # Task-specific instructions (combined with ECM base prompt)
    TASK_INSTRUCTIONS = """
# SWE-Bench-CL Task

You are solving GitHub issues in a repository. For each issue:
1. Analyze the problem statement carefully
2. Consider any hints provided
3. Generate a git diff patch to fix the issue

## Memory Strategy
- Use `note -m "..."` to save patterns you discover in this codebase
- Use `insight -m "..."` for cross-cutting patterns (e.g., error handling style)
- Use `notes` before each task to recall what you learned from previous issues

Format your response as a git diff patch:
```diff
diff --git a/path/to/file.py b/path/to/file.py
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context
-removed line
+added line
 context
```
"""

    # Combined prompt: ECM base + task-specific
    SYSTEM_PROMPT = SYSTEM_PROMPT_ECM + TASK_INSTRUCTIONS

    def __init__(self, harness: SWEBenchCLHarness, agent, model: str = "gpt-4o"):
        super().__init__(harness, agent, model)
        self.harness: SWEBenchCLHarness = harness

    def run_sequence(
        self,
        sequence_id: str,
        max_tasks: int = 50,
    ) -> tuple[CumulativeTokenReport, CorrectnessMetrics]:
        """
        Run a full CL sequence.

        Args:
            sequence_id: Repository sequence (e.g., 'django')
            max_tasks: Maximum tasks to evaluate
        """
        # Create ECM project for this sequence
        project_name = f"swe-bench-cl-{sequence_id}"
        if hasattr(self.agent, 'store'):
            # Create new project scope in ECM
            self.agent.store.checkout(
                project_name,
                note=f"Starting SWE-Bench-CL evaluation on {sequence_id}",
                create=True
            )

        config = {
            "sequence": sequence_id,
            "max_tasks": max_tasks,
        }

        # Use parent class run_sequence with NO reset between tasks
        return super().run_sequence(config, reset_between_tasks=False)

    def _build_prompt(self, task: HarnessTask) -> str:
        """Build prompt for a SWE-Bench-CL task."""
        parts = [
            f"# Issue: {task.task_id}",
            f"\n## Repository: {task.repo or 'unknown'}",
            f"\n## Problem Statement:\n{task.instruction}",
        ]

        # Add hints if available
        hints = task.metadata.get("hints", "")
        if hints:
            parts.append(f"\n## Hints:\n{hints}")

        # Add sequence context
        position = task.metadata.get("sequence_position", 0)
        if position > 0:
            parts.append(
                f"\n## Context:\nThis is issue #{position + 1} in the sequence. "
                f"Use your memory of previous issues to identify patterns."
            )

        parts.append("\n## Your Task:\nGenerate a git diff patch to resolve this issue.")

        return "\n".join(parts)
