"""
SWE-Bench Verified Harness Adapter.

Integrates ECM agent with the official SWE-Bench Verified benchmark.
Uses curated, human-verified GitHub issues for reliable evaluation.

Reference: https://github.com/princeton-nlp/SWE-bench
Paper: https://arxiv.org/abs/2310.06770
Dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench

SWE-Bench Verified is a curated subset of ~500 tasks that have been
manually verified to be solvable and have reliable test suites.
"""

import json
import subprocess
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


class SWEBenchVerifiedHarness(OfficialHarness):
    """
    Official harness for SWE-Bench Verified benchmark.

    SWE-Bench Verified contains ~500 curated tasks that are:
    - Human-verified to be solvable
    - Have reliable test suites
    - Cover diverse repositories and issue types

    Unlike SWE-Bench-CL, tasks are independent (no continual learning).
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize SWE-Bench Verified harness.

        Args:
            data_dir: Directory for caching tasks
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)

        self._tasks: list[dict] = []
        self._docker_available: Optional[bool] = None

    @property
    def name(self) -> str:
        return "swe-bench-verified"

    @property
    def task_type(self) -> str:
        return "long_horizon"  # Independent tasks, not CL

    def setup(self) -> bool:
        """Load SWE-Bench Verified tasks from cache or HuggingFace."""
        tasks_file = self.data_dir / "tasks.json"

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
            print("[SWE-Bench-Verified] Docker not available - test execution will be simulated")

        # Try loading from cache
        if tasks_file.exists():
            try:
                with open(tasks_file) as f:
                    self._tasks = json.load(f)
                print(f"[SWE-Bench-Verified] Loaded {len(self._tasks)} tasks from cache")
                return True
            except json.JSONDecodeError:
                print("[SWE-Bench-Verified] Cache corrupted, reloading from HuggingFace")

        # Load from HuggingFace
        try:
            from datasets import load_dataset

            print("[SWE-Bench-Verified] Loading from HuggingFace...")
            ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

            self._tasks = []
            for record in ds:
                task = {
                    "instance_id": record.get("instance_id", ""),
                    "repo": record.get("repo", ""),
                    "base_commit": record.get("base_commit", ""),
                    "problem_statement": record.get("problem_statement", ""),
                    "hints_text": record.get("hints_text", ""),
                    "created_at": record.get("created_at", ""),
                    "patch": record.get("patch", ""),
                    "test_patch": record.get("test_patch", ""),
                    "version": record.get("version", ""),
                    "environment_setup_commit": record.get("environment_setup_commit", ""),
                    "FAIL_TO_PASS": record.get("FAIL_TO_PASS", ""),
                    "PASS_TO_PASS": record.get("PASS_TO_PASS", ""),
                }
                self._tasks.append(task)

            print(f"[SWE-Bench-Verified] Loaded {len(self._tasks)} tasks from HuggingFace")

            # Cache to disk
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(tasks_file, "w") as f:
                json.dump(self._tasks, f, indent=2)
            print(f"[SWE-Bench-Verified] Cached to {tasks_file}")

            return True

        except ImportError:
            print("[SWE-Bench-Verified] datasets library not installed")
            print("[SWE-Bench-Verified] Run: uv pip install datasets")
            return False
        except Exception as e:
            print(f"[SWE-Bench-Verified] Error loading dataset: {e}")
            return False

    def get_sequence_ids(self) -> list[str]:
        """Get available repositories."""
        if not self._tasks:
            return []
        repos = set(t.get("repo", "unknown") for t in self._tasks)
        return sorted(repos)

    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """
        Load SWE-Bench Verified tasks.

        Args:
            config: dict with keys:
                - max_tasks: int - Maximum tasks to load
                - repo: str - Filter by repository (optional)
                - shuffle: bool - Whether to shuffle tasks
        """
        max_tasks = config.get("max_tasks", len(self._tasks))
        repo_filter = config.get("repo", None)
        shuffle = config.get("shuffle", False)

        tasks = self._tasks

        # Filter by repo if specified
        if repo_filter:
            tasks = [t for t in tasks if repo_filter in t.get("repo", "")]

        # Shuffle if requested
        if shuffle:
            import random
            tasks = random.sample(tasks, len(tasks))

        # Limit tasks
        tasks = tasks[:max_tasks]

        for i, task_data in enumerate(tasks):
            instance_id = task_data.get("instance_id", f"task_{i}")
            repo = task_data.get("repo", "unknown")

            # Estimate difficulty based on patch size
            patch = task_data.get("patch", "")
            patch_lines = len(patch.split('\n'))
            if patch_lines < 20:
                difficulty = "easy"
            elif patch_lines < 50:
                difficulty = "medium"
            else:
                difficulty = "hard"

            yield HarnessTask(
                task_id=instance_id,
                task_type="long_horizon",
                instruction=task_data.get("problem_statement", ""),
                metadata={
                    "repo": repo,
                    "base_commit": task_data.get("base_commit", ""),
                    "hints": task_data.get("hints_text", ""),
                    "created_at": task_data.get("created_at", ""),
                    "version": task_data.get("version", ""),
                    "environment_setup_commit": task_data.get("environment_setup_commit", ""),
                    "FAIL_TO_PASS": task_data.get("FAIL_TO_PASS", ""),
                    "PASS_TO_PASS": task_data.get("PASS_TO_PASS", ""),
                    "sequence_position": i,
                },
                ground_truth=task_data.get("patch", ""),
                repo=repo,
                difficulty=difficulty,
            )

    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """Execute agent's proposed patch."""
        start_time = time.time()
        execution_log = []

        # Parse agent action as patch
        patch = self._extract_patch(agent_action)
        execution_log.append(f"Extracted patch: {len(patch)} bytes")

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
        Run official test suite to verify patch correctness.

        Uses Docker-based evaluation with actual test execution.
        """
        if not self._docker_available:
            # Simulation mode - for development only
            patch = self._extract_patch(result.agent_output)
            gold_patch = task.ground_truth or ""

            if not patch or not gold_patch:
                return False

            # Check if key changes are present
            patch_lines = set(patch.strip().split('\n'))
            gold_lines = set(gold_patch.strip().split('\n'))

            overlap = len(patch_lines & gold_lines)
            similarity = overlap / max(len(gold_lines), 1)

            result.partial_score = similarity
            result.success = similarity > 0.5

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
        """Reset for new evaluation."""
        pass

    def start_project(self, project_name: str) -> None:
        """Start a new ECM project."""
        pass

    def teardown(self) -> None:
        """Clean up resources."""
        pass

    def _extract_patch(self, agent_output: str) -> str:
        """Extract git diff patch from agent output."""
        lines = agent_output.split('\n')
        in_diff = False
        patch_lines = []

        for line in lines:
            if line.startswith('diff --git') or line.startswith('---') or line.startswith('+++'):
                in_diff = True

            if in_diff:
                patch_lines.append(line)

        if not patch_lines:
            return agent_output.strip()

        return '\n'.join(patch_lines)

    def _run_tests_in_docker(self, task: HarnessTask, result: HarnessResult) -> bool:
        """
        Run tests in Docker container using official SWE-bench evaluation.

        Uses the official evaluation harness from princeton-nlp/SWE-bench.
        """
        result.execution_log.append("[Docker] Starting test execution...")

        # Extract patch
        patch = self._extract_patch(result.agent_output)
        if not patch:
            result.execution_log.append("[Docker] No valid patch found")
            return False

        # In full implementation, this would:
        # 1. Save patch to temp file
        # 2. Run: docker run swebench/evaluation:latest \
        #         --predictions_path /path/to/predictions.json \
        #         --swe_bench_tasks princeton-nlp/SWE-bench_Verified \
        #         --log_dir /path/to/logs
        # 3. Parse results from log files

        # For now, placeholder
        result.execution_log.append("[Docker] Full evaluation not yet implemented")
        result.execution_log.append("[Docker] Use swebench CLI for official evaluation")

        return False


class SWEBenchVerifiedAdapter(HarnessAdapter):
    """
    ECM-specific adapter for SWE-Bench Verified.

    Handles:
    - Task prompt formatting with repository context
    - Patch output formatting
    - Memory utilization for patterns across repositories
    """

    TASK_INSTRUCTIONS = """
# SWE-Bench Verified Context

You are solving verified GitHub issues from real open-source repositories.
Each issue has been confirmed solvable with a working test suite.

## Scope Naming
Use: `task/<instance_id>` (e.g., `task/django__django-12345`)

## What to Note
- Repository patterns: "This repo uses pytest for testing"
- File locations: "Models are in src/models/"
- Error patterns: "ValueError for invalid input, TypeError for type mismatches"
- Common fixes: "Import statements often missing in __init__.py"

## Output Format
Generate a git diff patch that fixes the issue:
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

Focus on minimal, targeted fixes. Avoid unnecessary changes.
"""

    SYSTEM_PROMPT = SYSTEM_PROMPT_ECM + TASK_INSTRUCTIONS

    def __init__(self, harness: SWEBenchVerifiedHarness, agent, model: str = "gpt-4o"):
        super().__init__(harness, agent, model)
        self.harness: SWEBenchVerifiedHarness = harness

    def run_sequence(
        self,
        config: dict,
        reset_between_tasks: bool = False,
    ) -> tuple[CumulativeTokenReport, CorrectnessMetrics]:
        """
        Run SWE-Bench Verified evaluation.

        Args:
            config: Configuration with 'max_tasks', 'repo' filter, etc.
            reset_between_tasks: Whether to reset agent between tasks
                               (False maintains learned patterns)
        """
        project_name = "swe-bench-verified"

        if hasattr(self.agent, 'store'):
            self.agent.store.checkout(
                project_name,
                note="Starting SWE-Bench Verified evaluation",
                create=True
            )

        return super().run_sequence(config, reset_between_tasks=reset_between_tasks)

    def _build_prompt(self, task: HarnessTask) -> str:
        """Build prompt for a SWE-Bench Verified task."""
        parts = [
            f"# Issue: {task.task_id}",
            f"\n## Repository: {task.repo or 'unknown'}",
        ]

        # Add version info if available
        version = task.metadata.get("version", "")
        if version:
            parts.append(f"## Version: {version}")

        parts.append(f"\n## Problem Statement:\n{task.instruction}")

        # Add hints if available
        hints = task.metadata.get("hints", "")
        if hints:
            parts.append(f"\n## Hints:\n{hints}")

        # Add test info if available
        fail_to_pass = task.metadata.get("FAIL_TO_PASS", "")
        if fail_to_pass:
            parts.append(f"\n## Tests to Fix:\n{fail_to_pass}")

        # Add context about other tasks
        position = task.metadata.get("sequence_position", 0)
        if position > 0:
            parts.append(
                f"\n## Context:\nThis is task #{position + 1}. "
                f"Use your memory of previous issues to identify patterns."
            )

        parts.append("\n## Your Task:\nGenerate a git diff patch to resolve this issue.")

        return "\n".join(parts)
