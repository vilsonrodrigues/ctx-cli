"""
OSWorld Harness Adapter.

Integrates ECM agent with the official OSWorld benchmark.
OSWorld provides real computer environments (Ubuntu, Windows, macOS)
for desktop automation evaluation.

Reference: https://github.com/xlang-ai/OSWorld
Website: https://os-world.github.io/

Note: Full evaluation requires VM infrastructure (Docker/VMware/AWS).
This implementation provides a simulation mode for development.
"""

import time
from typing import Iterator, Optional

# Import official ECM prompts
from prompts import SYSTEM_PROMPT_ECM

from benchmarks.core.harness_protocol import (
    OfficialHarness,
    HarnessTask,
    HarnessResult,
    HarnessAdapter,
)


class OSWorldHarness(OfficialHarness):
    """
    Official harness for OSWorld benchmark.

    OSWorld tests agents on real desktop environments with
    369 tasks across web, desktop, system, and multi-app categories.

    Note: Full implementation requires VM setup. This provides
    simulation mode for development and testing.
    """

    CATEGORIES = ["web", "desktop", "system", "multi_app"]

    def __init__(self, mode: str = "simulation"):
        """
        Initialize OSWorld harness.

        Args:
            mode: 'simulation', 'docker', or 'aws'
        """
        self.mode = mode
        self._vm_available = False

    @property
    def name(self) -> str:
        return "osworld"

    @property
    def task_type(self) -> str:
        return "long_horizon"

    def setup(self) -> bool:
        """Check VM infrastructure availability."""
        if self.mode == "simulation":
            print("[OSWorld] Running in simulation mode")
            return True

        # Check Docker
        if self.mode == "docker":
            import subprocess
            try:
                result = subprocess.run(
                    ["docker", "images", "osworld/ubuntu"],
                    capture_output=True, text=True, timeout=10
                )
                self._vm_available = "osworld" in result.stdout
            except Exception:
                self._vm_available = False

            if not self._vm_available:
                print("[OSWorld] Docker image not found. Run: docker pull osworld/ubuntu:latest")
                print("[OSWorld] Falling back to simulation mode")

        return True

    def get_sequence_ids(self) -> list[str]:
        """Get available task categories."""
        return self.CATEGORIES

    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """Load OSWorld tasks."""
        max_tasks = config.get("max_tasks", 50)
        category = config.get("category", None)

        # Sample tasks for development
        tasks = [
            {
                "task_id": "web_001",
                "category": "web",
                "instruction": "Open Firefox and search for 'weather forecast'",
                "actions": ["click_icon", "type_text", "press_enter"],
            },
            {
                "task_id": "desktop_001",
                "category": "desktop",
                "instruction": "Open the file manager and create a new folder named 'Documents'",
                "actions": ["click_icon", "right_click", "click_menu", "type_text"],
            },
            {
                "task_id": "system_001",
                "category": "system",
                "instruction": "Open Settings and change the desktop background",
                "actions": ["click_icon", "navigate", "select", "apply"],
            },
            {
                "task_id": "multi_app_001",
                "category": "multi_app",
                "instruction": "Copy text from a document and paste it into an email",
                "actions": ["open_app", "select_text", "copy", "open_app", "paste"],
            },
        ]

        if category:
            tasks = [t for t in tasks if t["category"] == category]

        for task_data in tasks[:max_tasks]:
            yield HarnessTask(
                task_id=task_data["task_id"],
                task_type="long_horizon",
                instruction=task_data["instruction"],
                metadata={
                    "category": task_data["category"],
                    "expected_actions": task_data["actions"],
                },
                dependencies=[],
            )

    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """Execute agent's action in VM environment."""
        start_time = time.time()
        execution_log = []

        if self.mode == "simulation" or not self._vm_available:
            # Simulation mode
            execution_log.append(f"[SIMULATED] Action: {agent_action[:100]}...")

            # Check for valid action format
            valid_actions = ["click", "type", "scroll", "drag", "press", "move"]
            has_valid_action = any(a in agent_action.lower() for a in valid_actions)

            if has_valid_action:
                execution_log.append("[SIMULATED] Action format valid")
                success = True
            else:
                execution_log.append("[SIMULATED] Expected mouse/keyboard action")
                success = False
        else:
            # Real VM execution would go here
            execution_log.append("[VM] Execution not yet implemented")
            success = False

        execution_time = time.time() - start_time

        return HarnessResult(
            task_id=task.task_id,
            success=success,
            agent_output=agent_action,
            execution_log=execution_log,
            execution_time_seconds=execution_time,
        )

    def verify_result(self, task: HarnessTask, result: HarnessResult) -> bool:
        """Verify task completion."""
        # In full implementation, this would check VM state
        return result.success

    def reset_environment(self) -> None:
        """Reset VM to clean state."""
        pass

    def start_project(self, project_name: str) -> None:
        """Start a new ECM project."""
        pass

    def teardown(self) -> None:
        """Clean up VM resources."""
        pass


class OSWorldAdapter(HarnessAdapter):
    """ECM-specific adapter for OSWorld."""

    # Task-specific instructions
    TASK_INSTRUCTIONS = """
# Desktop Automation Task

You control a computer through mouse and keyboard actions.

## Action Format
- click(x, y) - Click at coordinates
- type("text") - Type text
- press("key") - Press a key (enter, tab, etc.)
- scroll(direction, amount) - Scroll up/down
- drag(x1, y1, x2, y2) - Drag from point to point

## Memory Strategy
- Use `note -m "app X: button Y at (x,y)"` - Save UI element locations
- Use `note -m "sequence for task: ..."` - Save action sequences
- Use `insight -m "..."` - Save cross-app patterns
- Use `notes` - Recall before similar tasks
"""

    # Combined prompt: ECM base + task-specific
    SYSTEM_PROMPT = SYSTEM_PROMPT_ECM + TASK_INSTRUCTIONS

    def _build_prompt(self, task: HarnessTask) -> str:
        """Build prompt for an OSWorld task."""
        parts = [
            f"# Task: {task.task_id}",
            f"\n## Category: {task.metadata.get('category', 'unknown')}",
            f"\n## Goal:\n{task.instruction}",
            "\n## Generate the next action to take:",
        ]
        return "\n".join(parts)
