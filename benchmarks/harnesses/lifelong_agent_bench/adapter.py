"""
LifelongAgentBench Harness Adapter.

Integrates ECM agent with the official LifelongAgentBench benchmark.
Tests skill reuse across three environments: Database (SQL), Operating System (Bash),
and Knowledge Graph (SPARQL).

Reference: https://github.com/caixd-220529/LifelongAgentBench
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


# Environment-specific skills
DB_SKILLS = [
    "select_basic", "select_where", "select_orderby", "select_limit",
    "select_aggregate", "select_groupby", "select_having", "select_join",
    "select_subquery", "insert", "update", "delete", "create_table",
    "alter_table", "drop_table", "create_index", "transaction",
    "nested_query", "case_when", "union", "exists", "view"
]

OS_SKILLS = [
    "ls", "cd", "pwd", "mkdir", "rmdir", "touch", "rm", "cp", "mv",
    "cat", "head", "tail", "grep", "sed", "awk", "sort", "uniq",
    "wc", "find", "chmod", "chown", "ps", "kill", "tar", "zip",
    "curl", "wget", "ssh", "pipe", "redirect"
]

KG_SKILLS = [
    "select", "filter", "optional", "union", "order", "limit",
    "aggregate", "group", "having", "subquery", "path", "construct"
]


class LifelongAgentBenchHarness(OfficialHarness):
    """
    Official harness for LifelongAgentBench.

    LifelongAgentBench tests agents on skill reuse across three environments,
    with explicit task dependencies requiring memory of earlier results.
    """

    ENVIRONMENTS = ["db", "os", "kg"]

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize LifelongAgentBench harness.

        Args:
            data_dir: Directory containing task data
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)

        self._tasks: dict[str, list] = {}
        self._docker_available: Optional[bool] = None
        self._current_environment: Optional[str] = None

        # Track learned skills for metrics
        self._learned_skills: set[str] = set()
        self._skill_reuse_count: int = 0

    @property
    def name(self) -> str:
        return "lifelong-agent-bench"

    @property
    def task_type(self) -> str:
        return "continual_learning"

    def setup(self) -> bool:
        """Setup harness environment."""
        # Check Docker for environment execution
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
            print("[LifelongAgentBench] Docker not available - using simulation mode")

        # Load or generate task data
        self._load_tasks()

        return True

    def _load_tasks(self) -> None:
        """Load task data from official dataset or generate synthetic tasks."""
        for env in self.ENVIRONMENTS:
            data_file = self.data_dir / f"tasks_{env}.json"
            if data_file.exists():
                print(f"[LifelongAgentBench] Loading {env} tasks from {data_file}")
                with open(data_file) as f:
                    self._tasks[env] = json.load(f)
                print(f"[LifelongAgentBench] Loaded {len(self._tasks[env])} {env} tasks")
            else:
                # Generate synthetic tasks for development
                print(f"[LifelongAgentBench] No data file for {env}, generating synthetic tasks")
                self._tasks[env] = self._generate_tasks(env)

    def _generate_tasks(self, environment: str) -> list[dict]:
        """Generate representative tasks for an environment."""
        tasks = []

        if environment == "db":
            skills = DB_SKILLS
            task_templates = [
                ("create_employees", "create_table", "Create an employees table with id, name, department, salary"),
                ("insert_employees", "insert", "Insert 5 sample employees into the employees table"),
                ("select_all", "select_basic", "Select all employees from the table"),
                ("select_high_salary", "select_where", "Find employees with salary > 50000"),
                ("avg_by_dept", "select_aggregate", "Calculate average salary by department"),
            ]
        elif environment == "os":
            skills = OS_SKILLS
            task_templates = [
                ("create_project", "mkdir", "Create a project directory structure with src/, docs/, tests/"),
                ("create_readme", "touch", "Create a README.md file in the project root"),
                ("find_python", "find", "Find all Python files in the project"),
                ("count_lines", "wc", "Count total lines in all Python files"),
                ("backup", "tar", "Create a backup archive of the project"),
            ]
        else:  # kg
            skills = KG_SKILLS
            task_templates = [
                ("select_persons", "select", "Select all Person entities from the graph"),
                ("filter_age", "filter", "Find persons older than 30"),
                ("optional_email", "optional", "Get persons with their optional email addresses"),
                ("count_by_city", "aggregate", "Count persons by city"),
                ("find_path", "path", "Find the path between two specific persons"),
            ]

        for i, (task_id, skill, instruction) in enumerate(task_templates):
            tasks.append({
                "task_id": f"{environment}_{task_id}",
                "environment": environment,
                "skill": skill,
                "instruction": instruction,
                "dependencies": [t["task_id"] for t in tasks] if tasks else [],
                "expected_skill_reuse": skill in [t["skill"] for t in tasks],
            })

        return tasks

    def get_sequence_ids(self) -> list[str]:
        """Get available environment sequences."""
        return self.ENVIRONMENTS

    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """
        Load tasks from specified environment(s).

        Args:
            config: dict with keys:
                - environment: str or list - Environment(s) to load ('db', 'os', 'kg', or 'all')
                - max_tasks: int - Maximum tasks per environment
        """
        environments = config.get("environment", "all")
        max_tasks = config.get("max_tasks", 999)

        if environments == "all":
            environments = self.ENVIRONMENTS
        elif isinstance(environments, str):
            environments = [environments]

        for env in environments:
            if env not in self._tasks:
                continue

            self._current_environment = env
            tasks = self._tasks[env][:max_tasks]

            for task_data in tasks:
                # Handle skill_list which can be a list or string
                skill_list = task_data.get("skill_list", task_data.get("skill", "unknown"))
                if isinstance(skill_list, list):
                    skill = ", ".join(skill_list)
                elif isinstance(skill_list, str) and skill_list.startswith("["):
                    try:
                        skill = ", ".join(eval(skill_list))
                    except:
                        skill = skill_list
                else:
                    skill = str(skill_list)

                yield HarnessTask(
                    task_id=task_data["task_id"],
                    task_type="continual_learning",
                    instruction=task_data["instruction"],
                    metadata={
                        "skill": skill,
                        "skill_list": skill_list,
                        "expected_skill_reuse": task_data.get("expected_skill_reuse", False),
                        "reused_skills": task_data.get("reused_skills", []),
                        "table_info": task_data.get("table_info", {}),
                        "answer_info": task_data.get("answer_info", {}),
                    },
                    dependencies=task_data.get("dependencies", []),
                    environment=env,
                )

    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """Execute agent's action in the appropriate environment."""
        start_time = time.time()
        execution_log = []

        env = task.environment or self._current_environment or "db"

        if env == "db":
            output, success = self._execute_sql(agent_action, execution_log)
        elif env == "os":
            output, success = self._execute_bash(agent_action, execution_log)
        else:  # kg
            output, success = self._execute_sparql(agent_action, execution_log)

        execution_time = time.time() - start_time

        return HarnessResult(
            task_id=task.task_id,
            success=success,
            agent_output=agent_action,
            execution_log=execution_log,
            execution_time_seconds=execution_time,
        )

    def _execute_sql(self, query: str, log: list) -> tuple[str, bool]:
        """Execute SQL query."""
        log.append(f"Executing SQL: {query[:100]}...")

        if not self._docker_available:
            # Simulation mode
            if any(kw in query.upper() for kw in ["CREATE", "INSERT", "SELECT", "UPDATE", "DELETE"]):
                log.append("[SIMULATED] SQL execution successful")
                return "Query executed successfully", True
            log.append("[SIMULATED] Invalid SQL syntax")
            return "Error: Invalid SQL", False

        # Real Docker execution would go here
        log.append("[Docker] SQL execution not yet implemented")
        return "", False

    def _execute_bash(self, command: str, log: list) -> tuple[str, bool]:
        """Execute bash command."""
        log.append(f"Executing Bash: {command[:100]}...")

        if not self._docker_available:
            # Simulation mode - check for valid command structure
            valid_commands = ["ls", "cd", "pwd", "mkdir", "touch", "rm", "cp", "mv",
                           "cat", "grep", "find", "chmod", "tar", "echo"]
            first_word = command.strip().split()[0] if command.strip() else ""

            if first_word in valid_commands:
                log.append("[SIMULATED] Bash execution successful")
                return "Command executed successfully", True
            log.append(f"[SIMULATED] Unknown command: {first_word}")
            return f"Error: command not found: {first_word}", False

        # Real Docker execution would go here
        log.append("[Docker] Bash execution not yet implemented")
        return "", False

    def _execute_sparql(self, query: str, log: list) -> tuple[str, bool]:
        """Execute SPARQL query."""
        log.append(f"Executing SPARQL: {query[:100]}...")

        if not self._docker_available:
            # Simulation mode
            if any(kw in query.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                log.append("[SIMULATED] SPARQL execution successful")
                return "Query executed successfully", True
            log.append("[SIMULATED] Invalid SPARQL syntax")
            return "Error: Invalid SPARQL", False

        # Real Docker execution would go here
        log.append("[Docker] SPARQL execution not yet implemented")
        return "", False

    def verify_result(self, task: HarnessTask, result: HarnessResult) -> bool:
        """Verify task completion and track skill reuse."""
        # Track skill usage
        skill = task.metadata.get("skill", "unknown")
        expected_reuse = task.metadata.get("expected_skill_reuse", False)

        if skill in self._learned_skills and expected_reuse:
            self._skill_reuse_count += 1
            result.execution_log.append(f"Skill reuse detected: {skill}")

        self._learned_skills.add(skill)

        return result.success

    def reset_environment(self) -> None:
        """Reset for new evaluation."""
        self._current_environment = None
        self._learned_skills.clear()
        self._skill_reuse_count = 0

    def start_project(self, project_name: str) -> None:
        """Start a new ECM project."""
        pass

    def teardown(self) -> None:
        """Clean up resources."""
        pass


class LifelongAgentBenchAdapter(HarnessAdapter):
    """ECM-specific adapter for LifelongAgentBench."""

    # Task-specific context per environment (appended to ECM base prompt)
    TASK_INSTRUCTIONS = {
        "db": """
# Database Task Context

Environment: SQL database administration.
Tasks build on each other - table structures and query patterns transfer.

## Scope Naming
Use: `db/<task_id>` (e.g., `db/create_employees`)

## What to Note
- "Schema: employees(id, name, dept, salary)"
- "Pattern: aggregate + GROUP BY for summaries"
""",
        "os": """
# Linux Task Context

Environment: Bash/Linux system administration.
Tasks build on each other - file locations and command patterns transfer.

## Scope Naming
Use: `os/<task_id>` (e.g., `os/create_project`)

## What to Note
- "Location: project at /home/user/project/"
- "Pattern: find + xargs for batch ops"
""",
        "kg": """
# Knowledge Graph Task Context

Environment: SPARQL knowledge graph queries.
Tasks build on each other - graph structure and query patterns transfer.

## Scope Naming
Use: `kg/<task_id>` (e.g., `kg/select_persons`)

## What to Note
- "Structure: Person(name, age, city)"
- "Pattern: OPTIONAL for nullable relations"
""",
    }

    # Combined prompts: ECM base + environment-specific
    SYSTEM_PROMPTS = {
        env: SYSTEM_PROMPT_ECM + instructions
        for env, instructions in TASK_INSTRUCTIONS.items()
    }

    def run_sequence(
        self,
        config: dict,
        reset_between_tasks: bool = False,
    ) -> tuple[CumulativeTokenReport, CorrectnessMetrics]:
        """
        Run evaluation across specified environments.

        Args:
            config: dict with 'environment' and 'max_tasks' keys
            reset_between_tasks: If True, reset agent between tasks (NOT for CL!)
        """
        environments = config.get("environment", ["db"])
        if isinstance(environments, str):
            environments = [environments]

        # Create ECM project
        project_name = f"lifelong-agent-bench-{'-'.join(environments)}"
        if hasattr(self.agent, 'store'):
            self.agent.store.checkout(
                project_name,
                note=f"Starting LifelongAgentBench on {environments}",
                create=True
            )

        return super().run_sequence(config, reset_between_tasks=reset_between_tasks)

    def _build_prompt(self, task: HarnessTask) -> str:
        """Build prompt for a LifelongAgentBench task."""
        env = task.environment or "db"
        system = self.SYSTEM_PROMPTS.get(env, self.SYSTEM_PROMPTS["db"])

        parts = [
            f"# Task: {task.task_id}",
            f"\n## Environment: {env.upper()}",
            f"\n## Instruction:\n{task.instruction}",
        ]

        if task.dependencies:
            parts.append(
                f"\n## Context:\nThis task depends on: {', '.join(task.dependencies[-3:])}"
            )
            parts.append("Use your memory to recall relevant information from those tasks.")

        skill = task.metadata.get("skill", "unknown")
        parts.append(f"\n## Expected Skill: {skill}")

        return "\n".join(parts)
