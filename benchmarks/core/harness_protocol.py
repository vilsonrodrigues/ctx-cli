"""
Official Harness Protocol for ECM Benchmarks.

Defines the abstract interface that all official benchmark harnesses must implement.
This ensures consistent integration across SWE-Bench-CL, LifelongAgentBench, AppWorld, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional


@dataclass
class HarnessTask:
    """
    Standard task format across all harnesses.

    Each harness adapter converts its native task format to this common structure.
    """
    task_id: str
    task_type: str  # "continual_learning" | "long_horizon" | "retrieval"
    instruction: str
    metadata: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # Prior task IDs this depends on
    ground_truth: Any = None  # For correctness verification

    # Optional fields for specific harnesses
    repo: Optional[str] = None  # For SWE-Bench-CL
    environment: Optional[str] = None  # For LifelongAgentBench (db/os/kg)
    difficulty: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class HarnessResult:
    """
    Standard result format from harness execution.
    """
    task_id: str
    success: bool
    agent_output: str
    execution_log: list[str] = field(default_factory=list)

    # Legacy metrics (includes system prompt)
    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    execution_time_seconds: float = 0.0
    context_at_start: int = 0
    context_at_end: int = 0

    # Working context metrics (excludes system prompt - the real metrics)
    prompt_tokens_start: int = 0     # Working context at START of task
    prompt_tokens: int = 0           # Working context at END of task
    peak_prompt_tokens: int = 0      # Maximum working context during task
    completion_tokens: int = 0       # Output tokens

    # Harness-specific results
    tests_passed: int = 0
    tests_failed: int = 0
    partial_score: float = 0.0  # For partial credit tasks
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.execution_log is None:
            self.execution_log = []


@dataclass
class CorrectnessMetrics:
    """
    Per-benchmark correctness tracking.

    Different harnesses populate different fields based on their evaluation methodology.
    """
    # Generic metrics
    tasks_attempted: int = 0
    tasks_succeeded: int = 0
    success_rate: float = 0.0

    # SWE-Bench-CL specific
    tests_passed: int = 0
    tests_failed: int = 0
    patches_applied: int = 0
    patches_rejected: int = 0

    # LifelongAgentBench specific
    skill_reuse_count: int = 0
    cross_env_transfer_success: int = 0

    # AppWorld specific
    api_calls_correct: int = 0
    api_calls_total: int = 0
    state_consistency: float = 0.0

    # Continual Learning metrics
    forward_transfer_score: float = 0.0  # FWT: improvement from prior knowledge
    backward_transfer_score: float = 0.0  # BWT: impact on earlier task performance
    retention_score: float = 0.0  # KRT: knowledge retention over time

    def update_success_rate(self):
        """Recalculate success rate from counts."""
        if self.tasks_attempted > 0:
            self.success_rate = self.tasks_succeeded / self.tasks_attempted

    def to_dict(self) -> dict:
        return {
            "tasks_attempted": self.tasks_attempted,
            "tasks_succeeded": self.tasks_succeeded,
            "success_rate": round(self.success_rate, 3),
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "forward_transfer": round(self.forward_transfer_score, 3),
            "backward_transfer": round(self.backward_transfer_score, 3),
            "retention": round(self.retention_score, 3),
        }


class OfficialHarness(ABC):
    """
    Abstract interface for official benchmark harnesses.

    Each benchmark (SWE-Bench-CL, LifelongAgentBench, AppWorld, etc.) implements
    this interface to provide consistent integration with ECM evaluation.

    Key Principles:
    1. Use OFFICIAL datasets - never synthetic
    2. Run OFFICIAL verification - real tests, not heuristics
    3. Preserve state for CL - don't reset between sequence tasks
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Harness name (e.g., 'swe-bench-cl', 'lifelong-agent-bench')."""
        pass

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Primary task type: 'continual_learning' | 'long_horizon' | 'retrieval'."""
        pass

    @abstractmethod
    def setup(self) -> bool:
        """
        Setup harness environment.

        This may involve:
        - Checking dependencies are installed
        - Downloading datasets
        - Starting Docker containers
        - Initializing VMs (for OSWorld)

        Returns:
            True if harness is ready to use, False otherwise.
        """
        pass

    @abstractmethod
    def load_tasks(self, config: dict) -> Iterator[HarnessTask]:
        """
        Load tasks from official dataset.

        Args:
            config: Configuration dict with keys like:
                - sequence: str - Task sequence ID (for CL benchmarks)
                - max_tasks: int - Maximum tasks to load
                - split: str - Dataset split (train/dev/test)
                - environment: str - For LifelongAgentBench (db/os/kg)

        Yields:
            HarnessTask objects in execution order.
        """
        pass

    @abstractmethod
    def execute_task(self, task: HarnessTask, agent_action: str) -> HarnessResult:
        """
        Execute agent action in harness environment.

        Args:
            task: The task being executed
            agent_action: The agent's response/action (code, command, etc.)

        Returns:
            HarnessResult with execution details.
        """
        pass

    @abstractmethod
    def verify_result(self, task: HarnessTask, result: HarnessResult) -> bool:
        """
        Run official correctness check.

        This MUST use the official verification method:
        - SWE-Bench-CL: Run actual test suite
        - LifelongAgentBench: Execute SQL/Bash/SPARQL
        - AppWorld: Run unit tests

        Args:
            task: The original task
            result: The execution result

        Returns:
            True if task was completed correctly, False otherwise.
        """
        pass

    @abstractmethod
    def reset_environment(self) -> None:
        """
        Reset environment state between episodes (NOT between CL tasks!).

        Call this when starting a new evaluation sequence, not between
        tasks within a continual learning sequence.

        Note: For ECM agents, this should create a new PROJECT (not reset entirely).
        Projects allow "resetting" the session while preserving learned insights.
        Previous scopes are preserved but renamed under the old project.
        """
        pass

    def start_project(self, project_name: str) -> None:
        """
        Start a new ECM project for this evaluation sequence.

        Projects in ECM allow:
        - Resetting the session state
        - Preserving learned insights from previous projects
        - Renaming previous scopes under the old project namespace

        Args:
            project_name: Name for the new project (e.g., 'swe-bench-cl-django')
        """
        pass  # Override in harness implementations that need project management

    def get_sequence_ids(self) -> list[str]:
        """
        Get available sequence IDs for CL benchmarks.

        Returns:
            List of sequence identifiers (e.g., ['django', 'flask'] for SWE-Bench-CL)
        """
        return []

    def teardown(self) -> None:
        """
        Clean up harness resources.

        Called when done with evaluation to release Docker containers, VMs, etc.
        """
        pass


class HarnessAdapter:
    """
    Adapts an ECM agent to work with an official harness.

    This is the bridge between the ECM agent and the benchmark harness,
    handling:
    - Task routing to agent
    - Token metric collection
    - Correctness verification
    - Memory persistence across CL tasks

    Subclasses implement harness-specific prompt formatting.
    """

    def __init__(
        self,
        harness: OfficialHarness,
        agent,  # BaseAgent
        model: str = "gpt-4o",
    ):
        self.harness = harness
        self.agent = agent
        self.model = model
        self.correctness = CorrectnessMetrics()

    def run_sequence(
        self,
        config: dict,
        reset_between_tasks: bool = False,  # False for CL, True for independent
    ) -> tuple["CumulativeTokenReport", CorrectnessMetrics]:
        """
        Run a task sequence through the harness.

        Args:
            config: Harness configuration
            reset_between_tasks: If True, reset agent between tasks (NOT for CL!)

        Returns:
            Tuple of (token_report, correctness_metrics)
        """
        from benchmarks.core.metrics import CumulativeTokenReport, TaskTokenRecord

        report = CumulativeTokenReport(
            agent_type="ecm",
            model=self.model,
            benchmark=self.harness.name,
        )

        for task in self.harness.load_tasks(config):
            if reset_between_tasks:
                self.agent.reset()

            # Process task with agent
            result = self._process_task(task)

            # Execute in harness
            harness_result = self.harness.execute_task(task, result["agent_output"])

            # Verify correctness
            success = self.harness.verify_result(task, harness_result)

            # Update metrics
            self.correctness.tasks_attempted += 1
            if success:
                self.correctness.tasks_succeeded += 1
            self.correctness.update_success_rate()

            # Capture ECM state if available
            ecm_state = {}
            if hasattr(self.agent, 'store'):
                store = self.agent.store
                ecm_state = {
                    "current_scope": getattr(store, 'current_scope', 'main'),
                    "notes_count": len(getattr(store, 'notes', [])),
                    "insights_count": len(getattr(store, 'insights', [])),
                    "notes": [n.get('content', str(n))[:200] for n in getattr(store, 'notes', [])[-5:]],
                    "insights": [i.get('content', str(i))[:200] for i in getattr(store, 'insights', [])[-3:]],
                }

            # Record token metrics with tool call tracking
            record = TaskTokenRecord(
                task_id=task.task_id,
                task_name=f"{config.get('sequence', 'default')}:{task.task_id}",
                # Legacy metrics (includes system prompt)
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                context_at_start=result.get("context_at_start", 0),
                context_at_end=result.get("context_at_end", 0),
                # Working context metrics (excludes system prompt)
                prompt_tokens_start=result.get("prompt_tokens_start", 0),
                prompt_tokens=result.get("prompt_tokens", 0),
                peak_prompt_tokens=result.get("peak_prompt_tokens", 0),
                completion_tokens=result.get("completion_tokens", result.get("output_tokens", 0)),
                # Performance
                api_calls=result.get("api_calls", 1),
                execution_time_seconds=result.get("latency", 0.0),
                success=success,
                tool_calls=result.get("tool_calls", []),
                ctx_cli_commands=result.get("ctx_cli_commands", []),
                # Cache metrics
                cached_tokens=result.get("cached_tokens", 0),
                cache_hit_rate=result.get("cache_hit_rate", 0.0),
                # Reasoning tokens (o-series models)
                reasoning_tokens=result.get("reasoning_tokens", 0),
                # Debug fields for inspection
                agent_output=result.get("agent_output", result.get("answer", ""))[:2000],  # Truncate for JSON
                prompt_sent=result.get("prompt_sent", "")[:2000],
                execution_log=harness_result.execution_log if harness_result else [],
                ecm_state=ecm_state,
                messages_snapshot=result.get("messages_snapshot", [])[-10:],  # Last 10 messages
            )
            report.add_task(record)

        return report, self.correctness

    def _process_task(self, task: HarnessTask) -> dict:
        """
        Process a single task with the agent.

        Override in subclasses for harness-specific prompt formatting.
        """
        prompt = self._build_prompt(task)

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

        # Store prompt for debug logging
        result["prompt_sent"] = prompt

        return result

    def _build_prompt(self, task: HarnessTask) -> str:
        """
        Build the prompt for a task.

        Override in subclasses for harness-specific formatting.
        """
        return task.instruction
