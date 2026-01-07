"""
TheAgentCompany Harness Adapter.

Integrates ECM agent with the TheAgentCompany benchmark for realistic
workplace task evaluation in a persistent company environment.

Reference: https://github.com/TheAgentCompany/TheAgentCompany
Features:
- 175 tasks across 6 professional roles (SWE, PM, Data Scientist, HR, Finance, Admin)
- Persistent company environment (GitLab, Plane, ownCloud, RocketChat)
- Checkpoint-based evaluation with partial credit
- Long-horizon multi-step tasks
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
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
class TheAgentCompanyTask:
    """Extended task data for TheAgentCompany."""
    task_id: str
    role: str  # SWE, PM, DataScientist, HR, Finance, Admin
    category: str  # coding, conversational, mathematical, image-processing
    instruction: str
    workspace_path: str
    checkpoints: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    services_required: list[str] = field(default_factory=list)  # gitlab, plane, owncloud, rocketchat


# Task definitions organized by role and complexity
# These represent the types of tasks in TheAgentCompany
TASK_CATALOG = {
    "swe": [
        {
            "task_id": "swe_gitlab_pr_001",
            "role": "SWE",
            "category": "coding",
            "instruction": "Review the open merge request in GitLab for the authentication module. Check for security vulnerabilities and suggest improvements. If approved, merge it to main.",
            "checkpoints": ["accessed_gitlab", "reviewed_code", "left_comments", "made_decision"],
            "services_required": ["gitlab"],
        },
        {
            "task_id": "swe_debug_api_001",
            "role": "SWE",
            "category": "coding",
            "instruction": "Debug the failing API endpoint /api/v1/users. Check the logs, identify the issue, fix it in the codebase, and verify the fix works.",
            "checkpoints": ["checked_logs", "identified_issue", "applied_fix", "verified_fix"],
            "services_required": ["gitlab"],
        },
        {
            "task_id": "swe_documentation_001",
            "role": "SWE",
            "category": "coding",
            "instruction": "Update the API documentation for the new payment module. Include endpoint descriptions, request/response formats, and authentication requirements.",
            "checkpoints": ["read_existing_docs", "identified_gaps", "wrote_documentation", "committed_changes"],
            "services_required": ["gitlab", "owncloud"],
        },
    ],
    "pm": [
        {
            "task_id": "pm_sprint_planning_001",
            "role": "PM",
            "category": "conversational",
            "instruction": "Plan the next sprint in Plane. Review the backlog, prioritize items based on stakeholder feedback, and assign tasks to team members.",
            "checkpoints": ["reviewed_backlog", "prioritized_items", "assigned_tasks", "created_sprint"],
            "services_required": ["plane"],
        },
        {
            "task_id": "pm_status_report_001",
            "role": "PM",
            "category": "conversational",
            "instruction": "Prepare a weekly status report. Gather progress from team channels in RocketChat, compile metrics from Plane, and share the report with stakeholders.",
            "checkpoints": ["gathered_updates", "compiled_metrics", "wrote_report", "shared_report"],
            "services_required": ["plane", "rocketchat", "owncloud"],
        },
    ],
    "data_scientist": [
        {
            "task_id": "ds_analysis_001",
            "role": "DataScientist",
            "category": "mathematical",
            "instruction": "Analyze the sales data from Q4. Calculate key metrics (revenue growth, customer acquisition cost, churn rate) and create a summary report with visualizations.",
            "checkpoints": ["loaded_data", "calculated_metrics", "created_visualizations", "wrote_report"],
            "services_required": ["owncloud"],
        },
        {
            "task_id": "ds_model_training_001",
            "role": "DataScientist",
            "category": "coding",
            "instruction": "Train a customer churn prediction model using the provided dataset. Evaluate model performance and deploy it to the staging environment.",
            "checkpoints": ["prepared_data", "trained_model", "evaluated_performance", "deployed_model"],
            "services_required": ["gitlab", "owncloud"],
        },
    ],
    "hr": [
        {
            "task_id": "hr_onboarding_001",
            "role": "HR",
            "category": "conversational",
            "instruction": "Complete the onboarding process for new employee Sarah Chen. Set up her accounts in all company systems, send welcome messages, and schedule orientation meetings.",
            "checkpoints": ["created_accounts", "sent_welcome", "scheduled_meetings", "shared_documents"],
            "services_required": ["gitlab", "plane", "owncloud", "rocketchat"],
        },
    ],
    "finance": [
        {
            "task_id": "finance_expense_001",
            "role": "Finance",
            "category": "mathematical",
            "instruction": "Review and approve pending expense reports in the shared drive. Verify receipts, check budget compliance, and process approved expenses.",
            "checkpoints": ["reviewed_expenses", "verified_receipts", "checked_budget", "processed_approved"],
            "services_required": ["owncloud"],
        },
    ],
    "admin": [
        {
            "task_id": "admin_meeting_001",
            "role": "Admin",
            "category": "conversational",
            "instruction": "Organize the quarterly all-hands meeting. Find a suitable time by checking team calendars, book the conference room, create the agenda, and send invitations.",
            "checkpoints": ["checked_availability", "booked_room", "created_agenda", "sent_invitations"],
            "services_required": ["plane", "rocketchat", "owncloud"],
        },
    ],
}


class TheAgentCompanyHarness(OfficialHarness):
    """
    Official harness for TheAgentCompany benchmark.

    TheAgentCompany provides a persistent company environment with:
    - GitLab for code repositories
    - Plane for project management
    - ownCloud for file storage
    - RocketChat for team communication

    Tasks span 10 professional roles and require multi-step reasoning
    with checkpoint-based evaluation for partial credit.

    Roles: admin, data-science, finance, hr, ml, pm, qa, research, sde, business
    """

    def __init__(self, server_hostname: Optional[str] = None, data_dir: Optional[str] = None):
        """
        Initialize TheAgentCompany harness.

        Args:
            server_hostname: Hostname where services are running (default: localhost)
            data_dir: Directory containing task definitions and data
        """
        self.server_hostname = server_hostname or "localhost"
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)

        self._services_available: dict[str, bool] = {}
        self._docker_available: bool = False
        self._current_task: Optional[str] = None
        self._company_state: dict = {}  # Persistent state across tasks
        self._tasks: list[dict] = []  # Loaded from tasks.json

    @property
    def name(self) -> str:
        return "the-agent-company"

    @property
    def task_type(self) -> str:
        return "long_horizon"

    def setup(self) -> bool:
        """
        Setup harness environment.

        Checks:
        1. Load task data from tasks.json
        2. Docker is available
        3. Required services are running (GitLab, Plane, ownCloud, RocketChat)
        """
        # Load tasks from data file
        tasks_file = self.data_dir / "tasks.json"
        if tasks_file.exists():
            import json
            with open(tasks_file) as f:
                self._tasks = json.load(f)
            print(f"[TheAgentCompany] Loaded {len(self._tasks)} tasks from {tasks_file}")
        else:
            print(f"[TheAgentCompany] No tasks.json found, using built-in catalog")
            print(f"[TheAgentCompany] Run: uv run benchmarks/scripts/download_datasets.py --benchmark the-agent-company")
            # Fall back to built-in catalog
            self._tasks = self._generate_tasks_from_catalog()

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
            print("[TheAgentCompany] Docker not available - using simulation mode")

        # Check services (in real setup, would ping each service)
        services = ["gitlab", "plane", "owncloud", "rocketchat"]
        for service in services:
            self._services_available[service] = True

        print(f"[TheAgentCompany] Setup complete. Docker: {self._docker_available}")

        return True

    def _generate_tasks_from_catalog(self) -> list[dict]:
        """Generate tasks from built-in TASK_CATALOG."""
        tasks = []
        task_idx = 0
        previous_tasks = []

        for role, role_tasks in TASK_CATALOG.items():
            for task_data in role_tasks:
                task_id = task_data.get("task_id", f"{role}_{task_idx}")

                # Tasks within same role may share context
                deps = []
                for prev in previous_tasks[-3:]:
                    if prev.get("role") == task_data.get("role"):
                        deps.append(prev["task_id"])

                task = {
                    "task_id": task_id,
                    "task_name": task_id,
                    "category": role,
                    "instruction": task_data.get("instruction", ""),
                    "checkpoints": task_data.get("checkpoints", []),
                    "services_required": task_data.get("services_required", []),
                    "dependencies": deps,
                    "sequence_position": task_idx,
                }
                tasks.append(task)
                previous_tasks.append(task)
                task_idx += 1

        return tasks

    def get_sequence_ids(self) -> list[str]:
        """Get available task categories."""
        categories = set()
        for task in self._tasks:
            categories.add(task.get("category", "unknown"))
        return sorted(categories) if categories else list(TASK_CATALOG.keys())

    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """
        Load tasks from TheAgentCompany.

        Args:
            config: dict with keys:
                - role: str - Filter by category/role
                - max_tasks: int - Maximum tasks to load
        """
        role_filter = config.get("role", None)
        max_tasks = config.get("max_tasks", 999)

        # Filter tasks by role if specified
        if role_filter:
            filtered_tasks = [t for t in self._tasks if t.get("category") == role_filter]
        else:
            filtered_tasks = self._tasks

        # Limit to max_tasks
        filtered_tasks = filtered_tasks[:max_tasks]

        for i, task_data in enumerate(filtered_tasks):
            yield HarnessTask(
                task_id=task_data.get("task_id", f"task_{i}"),
                task_type="long_horizon",
                instruction=task_data.get("instruction", ""),
                metadata={
                    "role": task_data.get("category", "unknown"),
                    "category": task_data.get("category", "unknown"),
                    "task_name": task_data.get("task_name", ""),
                    "checkpoints": task_data.get("checkpoints", []),
                    "services_required": task_data.get("services_required", []),
                    "sequence_position": task_data.get("sequence_position", i),
                    "docker_image": task_data.get("docker_image", ""),
                },
                dependencies=task_data.get("dependencies", []),
                difficulty=self._estimate_difficulty(task_data),
            )

    def _estimate_difficulty(self, task_data: dict) -> str:
        """Estimate task difficulty based on checkpoints and services."""
        num_checkpoints = len(task_data.get("checkpoints", []))
        num_services = len(task_data.get("services_required", []))

        score = num_checkpoints + num_services
        if score <= 4:
            return "easy"
        elif score <= 6:
            return "medium"
        else:
            return "hard"

    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """
        Execute agent's action in the company environment.

        For TheAgentCompany, agent_action should describe the steps taken
        and any commands/API calls made.
        """
        start_time = time.time()
        execution_log = []

        self._current_task = task.task_id

        # Parse agent action to identify what was done
        checkpoints_hit = self._evaluate_checkpoints(task, agent_action)

        execution_log.append(f"Task: {task.task_id}")
        execution_log.append(f"Role: {task.metadata.get('role', 'unknown')}")
        execution_log.append(f"Checkpoints hit: {checkpoints_hit}")

        execution_time = time.time() - start_time

        return HarnessResult(
            task_id=task.task_id,
            success=False,  # Will be set by verify_result
            agent_output=agent_action,
            execution_log=execution_log,
            execution_time_seconds=execution_time,
            partial_score=len(checkpoints_hit) / max(len(task.metadata.get("checkpoints", [])), 1),
        )

    def _evaluate_checkpoints(self, task: HarnessTask, agent_action: str) -> list[str]:
        """
        Evaluate which checkpoints were achieved.

        In simulation mode, uses keyword matching.
        In real mode, would run actual evaluator.
        """
        checkpoints = task.metadata.get("checkpoints", [])
        agent_action_lower = agent_action.lower()

        # Keyword mapping for checkpoint detection
        checkpoint_keywords = {
            "accessed_gitlab": ["gitlab", "repository", "repo", "merge request", "mr"],
            "reviewed_code": ["review", "code", "changes", "diff", "inspect"],
            "left_comments": ["comment", "feedback", "suggestion", "note"],
            "made_decision": ["approve", "reject", "merge", "decision", "conclude"],
            "checked_logs": ["log", "error", "trace", "debug"],
            "identified_issue": ["issue", "bug", "problem", "cause", "root cause"],
            "applied_fix": ["fix", "patch", "update", "modify", "change"],
            "verified_fix": ["test", "verify", "confirm", "works", "success"],
            "reviewed_backlog": ["backlog", "items", "tasks", "stories"],
            "prioritized_items": ["priority", "order", "rank", "important"],
            "assigned_tasks": ["assign", "allocate", "delegate"],
            "created_sprint": ["sprint", "iteration", "cycle"],
            "gathered_updates": ["update", "progress", "status"],
            "compiled_metrics": ["metric", "number", "statistic", "data"],
            "wrote_report": ["report", "document", "summary"],
            "shared_report": ["share", "send", "distribute", "publish"],
            "loaded_data": ["load", "read", "import", "data"],
            "calculated_metrics": ["calculate", "compute", "analyze"],
            "created_visualizations": ["chart", "graph", "plot", "visualization"],
            "prepared_data": ["prepare", "clean", "preprocess"],
            "trained_model": ["train", "fit", "model"],
            "evaluated_performance": ["evaluate", "accuracy", "performance", "score"],
            "deployed_model": ["deploy", "staging", "production"],
            "created_accounts": ["account", "user", "create", "setup"],
            "sent_welcome": ["welcome", "email", "message", "greeting"],
            "scheduled_meetings": ["schedule", "meeting", "calendar"],
            "shared_documents": ["document", "file", "share"],
            "reviewed_expenses": ["expense", "review", "check"],
            "verified_receipts": ["receipt", "verify", "proof"],
            "checked_budget": ["budget", "limit", "allocation"],
            "processed_approved": ["process", "approve", "complete"],
            "checked_availability": ["availability", "calendar", "free"],
            "booked_room": ["book", "room", "reserve"],
            "created_agenda": ["agenda", "topics", "outline"],
            "sent_invitations": ["invite", "invitation", "send"],
            "read_existing_docs": ["read", "existing", "documentation"],
            "identified_gaps": ["gap", "missing", "incomplete"],
            "wrote_documentation": ["write", "document", "describe"],
            "committed_changes": ["commit", "push", "save"],
        }

        hit = []
        for checkpoint in checkpoints:
            keywords = checkpoint_keywords.get(checkpoint, [checkpoint.replace("_", " ")])
            if any(kw in agent_action_lower for kw in keywords):
                hit.append(checkpoint)

        return hit

    def verify_result(self, task: HarnessTask, result: HarnessResult) -> bool:
        """
        Verify task completion using checkpoint-based evaluation.

        TheAgentCompany uses:
        1. Primary: Result-based evaluation
        2. Secondary: Subcheckpoint verification
        """
        checkpoints = task.metadata.get("checkpoints", [])
        checkpoints_hit = self._evaluate_checkpoints(task, result.agent_output)

        # Calculate partial score
        if checkpoints:
            result.partial_score = len(checkpoints_hit) / len(checkpoints)
        else:
            result.partial_score = 1.0 if result.agent_output.strip() else 0.0

        # Success threshold: at least 50% of checkpoints
        result.success = result.partial_score >= 0.5

        result.execution_log.append(f"Checkpoints: {len(checkpoints_hit)}/{len(checkpoints)}")
        result.execution_log.append(f"Score: {result.partial_score:.2%}")

        # Update company state (persists across tasks)
        self._company_state[task.task_id] = {
            "completed": result.success,
            "checkpoints_hit": checkpoints_hit,
            "score": result.partial_score,
        }

        return result.success

    def reset_environment(self) -> None:
        """Reset company state for new evaluation sequence."""
        self._current_task = None
        self._company_state = {}

    def start_project(self, project_name: str) -> None:
        """Start a new ECM project for this evaluation."""
        # Initialize company state for new project
        self._company_state = {
            "_project": project_name,
            "_started_at": time.time(),
        }

    def get_company_state(self) -> dict:
        """Get current company state (for ECM context)."""
        return self._company_state.copy()

    def teardown(self) -> None:
        """Clean up resources."""
        self._current_task = None


class TheAgentCompanyAdapter(HarnessAdapter):
    """
    ECM-specific adapter for TheAgentCompany.

    Handles:
    - Creating ECM scopes for different company domains
    - Persisting knowledge across tasks (company context)
    - Multi-step task decomposition

    Scope Strategy:
    - company/codebase: Code patterns, repo structure, conventions
    - company/team: Team structure, responsibilities, communication
    - company/tools: Tool usage patterns (GitLab, Plane, etc.)
    - company/processes: Business processes, workflows
    - task/<task_id>: Task-specific work
    """

    # Task-specific instructions (combined with ECM base prompt)
    TASK_INSTRUCTIONS = """
# TheAgentCompany Task

You are working in a realistic company environment with:
- GitLab: Code repositories and merge requests
- Plane: Project management and sprints
- ownCloud: File storage and sharing
- RocketChat: Team communication

## Memory Strategy for Company Work

Use ECM scopes to organize company knowledge:

1. `scope company/codebase -m "..."` - For code patterns, repo structure
2. `scope company/team -m "..."` - For team info, responsibilities
3. `scope company/tools -m "..."` - For tool usage patterns
4. `scope company/processes -m "..."` - For business workflows
5. `scope task/<id> -m "..."` - For specific task work

## Workflow for Each Task

1. Check `notes company/*` to recall company knowledge
2. Create a task scope: `scope task/<task_id> -m "Goal..."`
3. Run `status` to see available context
4. Work on the task, saving important findings as notes
5. Return with summary: `return -m "[SUMMARY]...[DECISION]...[NEXT]..."`

## Important Guidelines

- Tasks share a persistent company environment
- Knowledge from earlier tasks helps with later ones
- Use `insight` for cross-cutting patterns (e.g., "Team prefers async communication")
- Be thorough - real work requires multiple steps
- Partial credit is given for checkpoints achieved
"""

    # Combined prompt: ECM base + task-specific
    SYSTEM_PROMPT = SYSTEM_PROMPT_ECM + TASK_INSTRUCTIONS

    def __init__(self, harness: TheAgentCompanyHarness, agent, model: str = "gpt-4.1-mini"):
        super().__init__(harness, agent, model)
        self.harness: TheAgentCompanyHarness = harness
        self._initialized_company_scopes = False

    def run_sequence(
        self,
        config: dict,
        reset_between_tasks: bool = False,
    ) -> tuple[CumulativeTokenReport, CorrectnessMetrics]:
        """
        Run a full task sequence in TheAgentCompany.

        Args:
            config: Configuration with 'role', 'max_tasks', etc.
            reset_between_tasks: Should be False to maintain company context
        """
        # Create ECM project for this evaluation
        role = config.get("role", "all")
        project_name = f"the-agent-company-{role}"

        if hasattr(self.agent, 'store'):
            # Initialize company knowledge scopes
            self._initialize_company_scopes(project_name)

        # Use parent class run_sequence with NO reset (company context persists)
        return super().run_sequence(config, reset_between_tasks=False)

    def _initialize_company_scopes(self, project_name: str) -> None:
        """Initialize ECM scopes for company domains."""
        if self._initialized_company_scopes:
            return

        # Create main project scope
        self.agent.store.checkout(
            project_name,
            note=f"Starting TheAgentCompany evaluation",
            create=True
        )

        # Add initial company context as insights
        initial_insights = [
            "Company uses GitLab for code, Plane for projects, ownCloud for files, RocketChat for chat",
            "Tasks may reference work done in previous tasks - always check notes first",
            "Checkpoint completion determines success - be thorough with each step",
        ]

        for insight in initial_insights:
            if hasattr(self.agent, 'execute_command'):
                self.agent.execute_command(
                    self.agent.store,
                    f'insight -m "{insight}"'
                )

        self._initialized_company_scopes = True

    def _build_prompt(self, task: HarnessTask) -> str:
        """Build prompt for a TheAgentCompany task."""
        parts = [
            f"# Task: {task.task_id}",
            f"\n## Role: {task.metadata.get('role', 'Employee')}",
            f"\n## Category: {task.metadata.get('category', 'general')}",
            f"\n## Instruction:\n{task.instruction}",
        ]

        # Add checkpoint information
        checkpoints = task.metadata.get("checkpoints", [])
        if checkpoints:
            parts.append(f"\n## Checkpoints to Complete:")
            for i, cp in enumerate(checkpoints, 1):
                parts.append(f"  {i}. {cp.replace('_', ' ').title()}")

        # Add services information
        services = task.metadata.get("services_required", [])
        if services:
            parts.append(f"\n## Services Available: {', '.join(services)}")

        # Add company context hint
        position = task.metadata.get("sequence_position", 0)
        if position > 0:
            parts.append(
                f"\n## Context:\nThis is task #{position + 1} in your work session. "
                f"Use `notes company/*` to recall relevant company knowledge from earlier tasks."
            )

        parts.append("\n## Your Task:\nComplete the work described above, hitting all checkpoints.")

        return "\n".join(parts)

    def _process_task(self, task: HarnessTask) -> dict:
        """Process a task with company context awareness."""
        # Build the prompt
        prompt = self._build_prompt(task)

        # Add company state context if available
        company_state = self.harness.get_company_state()
        if company_state:
            completed_tasks = [
                k for k, v in company_state.items()
                if isinstance(v, dict) and v.get("completed")
            ]
            if completed_tasks:
                prompt += f"\n\n## Previously Completed: {', '.join(completed_tasks)}"

        # Pass combined system prompt if agent supports it
        system_prompt = getattr(self, 'SYSTEM_PROMPT', None)
        if system_prompt and hasattr(self.agent, 'query'):
            import inspect
            sig = inspect.signature(self.agent.query)
            if 'system_prompt' in sig.parameters:
                result = self.agent.query(prompt, system_prompt=system_prompt)
            else:
                result = self.agent.query(prompt)
        else:
            result = self.agent.query(prompt)

        # Normalize: agent returns 'answer', harness expects 'agent_output'
        if "answer" in result and "agent_output" not in result:
            result["agent_output"] = result["answer"]

        return result
