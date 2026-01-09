"""
ECM Evaluation Metrics.

Implements the metrics defined in Appendix B for evaluating
Explicit Context Management performance.

This module is the authoritative source for all benchmark metrics.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# =============================================================================
# Token Utilities (inline to avoid import issues)
# =============================================================================

def estimate_tokens(text: str) -> int:
    """Estimate token count (~4 characters per token)."""
    return max(1, len(text) // 4)


def count_message_tokens(message: dict, model: str = "gpt-4o") -> int:
    """Count tokens in a single message."""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
    except (ImportError, KeyError):
        encoding = None

    overhead = 4
    content = message.get("content", "")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    else:
        text = str(content)

    text += message.get("role", "")

    if encoding:
        return len(encoding.encode(text)) + overhead
    return estimate_tokens(text) + overhead


def count_context_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    """Count total tokens in a message list."""
    total = sum(count_message_tokens(msg, model) for msg in messages)
    return total + 3  # reply priming


def count_working_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    """
    Count tokens excluding system prompt.

    This is the key metric for measuring actual context growth,
    since the system prompt is constant and cacheable.
    """
    working = [m for m in messages if m.get("role") != "system"]
    return count_context_tokens(working, model)


# =============================================================================
# Token Economics Metrics
# =============================================================================

@dataclass
class TokenMetrics:
    """Token economics metrics for a single run."""

    context_history: list[int] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    api_calls: int = 0
    execution_time_seconds: float = 0.0
    tasks_completed: int = 0
    tasks_total: int = 0

    @property
    def peak_context(self) -> int:
        """C_peak = max_t C(t)"""
        return max(self.context_history) if self.context_history else 0

    @property
    def base_context(self) -> int:
        """C_base = C(1) - first call context (cacheable)"""
        return self.context_history[0] if self.context_history else 0

    @property
    def context_growth(self) -> int:
        """Delta C = C_peak - C_base"""
        return self.peak_context - self.base_context

    @property
    def final_context(self) -> int:
        """Context at last step"""
        return self.context_history[-1] if self.context_history else 0

    @property
    def avg_context(self) -> float:
        """Average context across all calls"""
        if not self.context_history:
            return 0.0
        return sum(self.context_history) / len(self.context_history)

    @property
    def growth_rate(self) -> float:
        """gamma = Delta C / (T - 1) tokens per task"""
        if self.tasks_completed <= 1:
            return 0.0
        return self.context_growth / (self.tasks_completed - 1)

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)"""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def token_efficiency(self) -> float:
        """eta = tasks / total_tokens"""
        if self.total_tokens == 0:
            return 0.0
        return self.tasks_completed / self.total_tokens

    @property
    def avg_latency_per_call(self) -> float:
        """Average time per API call"""
        if self.api_calls == 0:
            return 0.0
        return self.execution_time_seconds / self.api_calls

    def add_context_sample(self, context_size: int) -> None:
        """Record context size for an API call."""
        self.context_history.append(context_size)
        self.api_calls += 1

    def to_dict(self) -> dict:
        return {
            "peak_context": self.peak_context,
            "base_context": self.base_context,
            "context_growth": self.context_growth,
            "final_context": self.final_context,
            "avg_context": round(self.avg_context, 1),
            "growth_rate": round(self.growth_rate, 2),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "token_efficiency": self.token_efficiency,
            "api_calls": self.api_calls,
            "execution_time": round(self.execution_time_seconds, 2),
            "avg_latency": round(self.avg_latency_per_call, 3),
            "tasks_completed": self.tasks_completed,
            "tasks_total": self.tasks_total,
        }


def compute_reduction_ratio(ecm_metrics: TokenMetrics, linear_metrics: TokenMetrics) -> float:
    """R = 1 - C_peak^ECM / C_peak^linear"""
    if linear_metrics.peak_context == 0:
        return 0.0
    return 1 - (ecm_metrics.peak_context / linear_metrics.peak_context)


def compute_speedup(ecm_metrics: TokenMetrics, linear_metrics: TokenMetrics) -> float:
    """Speedup = 1 - T_exec^ECM / T_exec^linear"""
    if linear_metrics.execution_time_seconds == 0:
        return 0.0
    return 1 - (ecm_metrics.execution_time_seconds / linear_metrics.execution_time_seconds)


# =============================================================================
# Knowledge Transfer Metrics
# =============================================================================

@dataclass
class KnowledgeQuery:
    """A query to test knowledge retention."""
    task_id: int
    query: str
    expected_keywords: list[str]
    actual_response: str = ""
    score: float = 0.0


@dataclass
class KnowledgeMetrics:
    """Knowledge transfer metrics for CL evaluation."""

    queries: list[KnowledgeQuery] = field(default_factory=list)
    task_performances: list[float] = field(default_factory=list)
    baseline_performances: list[float] = field(default_factory=list)

    def add_retention_query(self, query: KnowledgeQuery) -> None:
        """Add a knowledge retention test query."""
        self.queries.append(query)

    def score_query(self, query: KnowledgeQuery, response: str) -> float:
        """Score a query response based on keyword matching."""
        query.actual_response = response
        response_lower = response.lower()

        if not query.expected_keywords:
            query.score = 1.0 if response.strip() else 0.0
            return query.score

        matches = sum(1 for kw in query.expected_keywords if kw.lower() in response_lower)
        query.score = matches / len(query.expected_keywords)
        return query.score

    @property
    def krt_scores(self) -> dict[int, float]:
        """KRT(k) = retention score for task k"""
        scores: dict[int, list[float]] = {}
        for q in self.queries:
            if q.task_id not in scores:
                scores[q.task_id] = []
            scores[q.task_id].append(q.score)
        return {k: sum(v) / len(v) for k, v in scores.items()}

    @property
    def krt_avg(self) -> float:
        """Average knowledge retention across all tasks."""
        scores = self.krt_scores
        if not scores:
            return 0.0
        return sum(scores.values()) / len(scores)

    @property
    def forward_transfer(self) -> float:
        """FWT = (1/(T-1)) * sum(A_i - b_i)"""
        if len(self.task_performances) <= 1:
            return 0.0

        fwt_sum = 0.0
        for i in range(1, len(self.task_performances)):
            a_i = self.task_performances[i]
            b_i = self.baseline_performances[i] if i < len(self.baseline_performances) else 0.0
            fwt_sum += (a_i - b_i)

        return fwt_sum / (len(self.task_performances) - 1)

    def to_dict(self) -> dict:
        return {
            "krt_avg": round(self.krt_avg, 3),
            "krt_per_task": {k: round(v, 3) for k, v in self.krt_scores.items()},
            "forward_transfer": round(self.forward_transfer, 3),
            "num_queries": len(self.queries),
        }


# =============================================================================
# Navigation Metrics
# =============================================================================

@dataclass
class ScopeTransition:
    """Record of a scope transition."""
    from_scope: str
    to_scope: str
    operation: str  # "scope" or "goto"
    timestamp: datetime
    note: str


@dataclass
class NavigationMetrics:
    """Navigation pattern metrics."""

    transitions: list[ScopeTransition] = field(default_factory=list)
    scope_message_counts: dict[str, int] = field(default_factory=dict)
    scope_creation_order: list[str] = field(default_factory=list)

    def record_transition(self, from_scope: str, to_scope: str,
                          operation: str, note: str) -> None:
        """Record a scope transition."""
        self.transitions.append(ScopeTransition(
            from_scope=from_scope,
            to_scope=to_scope,
            operation=operation,
            timestamp=datetime.now(),
            note=note
        ))

        if operation == "scope" and to_scope not in self.scope_creation_order:
            self.scope_creation_order.append(to_scope)

    def record_scope_size(self, scope: str, message_count: int) -> None:
        """Record the final message count for a scope."""
        self.scope_message_counts[scope] = message_count

    @property
    def scope_count(self) -> int:
        """|S| = number of scopes created"""
        return len(self.scope_creation_order)

    @property
    def transition_count(self) -> int:
        """|T| = total transitions"""
        return len(self.transitions)

    @property
    def scope_operations(self) -> int:
        """Number of 'scope' operations"""
        return sum(1 for t in self.transitions if t.operation == "scope")

    @property
    def goto_operations(self) -> int:
        """Number of 'goto' operations"""
        return sum(1 for t in self.transitions if t.operation == "goto")

    @property
    def return_to_main_count(self) -> int:
        """Number of times agent returned to main"""
        return sum(1 for t in self.transitions if t.to_scope == "main")

    @property
    def return_rate(self) -> float:
        """r_return = goto_main / total_transitions"""
        if self.transition_count == 0:
            return 0.0
        return self.return_to_main_count / self.transition_count

    @property
    def avg_scope_lifetime(self) -> float:
        """Average messages per scope before transition."""
        if not self.scope_message_counts:
            return 0.0
        return sum(self.scope_message_counts.values()) / len(self.scope_message_counts)

    @property
    def max_scope_depth(self) -> int:
        """Maximum nesting depth."""
        if not self.transitions:
            return 0

        depth = 0
        max_depth = 0
        current_stack = ["main"]

        for t in self.transitions:
            if t.operation == "scope":
                depth += 1
                current_stack.append(t.to_scope)
            elif t.operation == "goto":
                if t.to_scope in current_stack:
                    idx = current_stack.index(t.to_scope)
                    depth = idx
                    current_stack = current_stack[:idx + 1]

            max_depth = max(max_depth, depth)

        return max_depth

    @property
    def navigation_entropy(self) -> float:
        """H_nav = -sum p(i->j) log p(i->j)"""
        if not self.transitions:
            return 0.0

        pair_counts: dict[tuple[str, str], int] = {}
        for t in self.transitions:
            pair = (t.from_scope, t.to_scope)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

        total = len(self.transitions)
        entropy = 0.0

        for count in pair_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def to_dict(self) -> dict:
        return {
            "scope_count": self.scope_count,
            "transition_count": self.transition_count,
            "scope_operations": self.scope_operations,
            "goto_operations": self.goto_operations,
            "return_to_main": self.return_to_main_count,
            "return_rate": round(self.return_rate, 3),
            "avg_scope_lifetime": round(self.avg_scope_lifetime, 1),
            "max_depth": self.max_scope_depth,
            "navigation_entropy": round(self.navigation_entropy, 3),
            "scopes": self.scope_creation_order,
        }


# =============================================================================
# Note/Insight Utility Metrics
# =============================================================================

@dataclass
class NoteRecord:
    """Record of a note creation and usage."""
    content: str
    scope: str
    created_at: datetime
    retrieval_count: int = 0
    retrieval_opportunities: int = 0


@dataclass
class InsightRecord:
    """Record of an insight creation and usage."""
    content: str
    created_at: datetime
    scopes_retrieved_from: set = field(default_factory=set)
    total_scopes: int = 0


@dataclass
class UtilityMetrics:
    """Note and insight utility metrics."""

    notes: list[NoteRecord] = field(default_factory=list)
    insights: list[InsightRecord] = field(default_factory=list)

    def record_note(self, content: str, scope: str) -> None:
        """Record a note creation."""
        self.notes.append(NoteRecord(
            content=content,
            scope=scope,
            created_at=datetime.now()
        ))

    def record_insight(self, content: str) -> None:
        """Record an insight creation."""
        self.insights.append(InsightRecord(
            content=content,
            created_at=datetime.now()
        ))

    def record_note_retrieval(self, scope: str) -> None:
        """Record that notes were retrieved."""
        for note in self.notes:
            if note.scope == scope:
                note.retrieval_opportunities += 1

    def record_note_used(self, note_content_substring: str) -> None:
        """Record that a specific note was used."""
        for note in self.notes:
            if note_content_substring.lower() in note.content.lower():
                note.retrieval_count += 1

    def record_insight_retrieval(self, from_scope: str, total_scopes: int) -> None:
        """Record insight retrieval from a scope."""
        for insight in self.insights:
            insight.scopes_retrieved_from.add(from_scope)
            insight.total_scopes = max(insight.total_scopes, total_scopes)

    @property
    def note_utility_scores(self) -> list[float]:
        """U(n) = retrievals / opportunities for each note."""
        scores = []
        for note in self.notes:
            if note.retrieval_opportunities > 0:
                scores.append(note.retrieval_count / note.retrieval_opportunities)
            else:
                scores.append(0.0)
        return scores

    @property
    def avg_note_utility(self) -> float:
        """Average note utility."""
        scores = self.note_utility_scores
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @property
    def dead_note_ratio(self) -> float:
        """Fraction of notes never used."""
        if not self.notes:
            return 0.0
        dead = sum(1 for n in self.notes if n.retrieval_count == 0)
        return dead / len(self.notes)

    @property
    def insight_coverage_scores(self) -> list[float]:
        """Coverage for each insight."""
        scores = []
        for insight in self.insights:
            if insight.total_scopes > 0:
                scores.append(len(insight.scopes_retrieved_from) / insight.total_scopes)
            else:
                scores.append(0.0)
        return scores

    @property
    def avg_insight_coverage(self) -> float:
        """Average insight coverage."""
        scores = self.insight_coverage_scores
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def to_dict(self) -> dict:
        return {
            "total_notes": len(self.notes),
            "total_insights": len(self.insights),
            "avg_note_utility": round(self.avg_note_utility, 3),
            "dead_note_ratio": round(self.dead_note_ratio, 3),
            "avg_insight_coverage": round(self.avg_insight_coverage, 3),
        }


# =============================================================================
# Per-Task Token Tracking (for Paper Figures)
# =============================================================================

@dataclass
class TaskTokenRecord:
    """Token usage for a single task - enables per-task I/O tracking."""

    task_id: str
    task_name: str = ""

    # Token counts (legacy - includes system prompt)
    input_tokens: int = 0
    output_tokens: int = 0

    # Context window state (legacy)
    context_at_start: int = 0
    context_at_end: int = 0

    # NEW: Working context (excludes system prompt - the real metric)
    prompt_tokens_start: int = 0     # Working context at START of task
    prompt_tokens: int = 0           # Working context at END of task
    peak_prompt_tokens: int = 0      # Maximum working context during task
    completion_tokens: int = 0       # Output tokens (same as output_tokens)

    # Performance
    api_calls: int = 0
    execution_time_seconds: float = 0.0

    # Task outcome
    success: bool = False

    # Tool call tracking (especially ctx_cli)
    tool_calls: list = field(default_factory=list)
    ctx_cli_commands: list = field(default_factory=list)

    # DEBUG: Full context inspection (for post-run analysis)
    agent_output: str = ""           # Final response from agent
    prompt_sent: str = ""            # User prompt sent to model
    execution_log: list = field(default_factory=list)  # Harness execution log
    ecm_state: dict = field(default_factory=dict)      # ECM notes/insights snapshot
    messages_snapshot: list = field(default_factory=list)  # Full message history (optional)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def context_delta(self) -> int:
        """Change in context window size during this task."""
        return self.context_at_end - self.context_at_start

    @property
    def num_tool_calls(self) -> int:
        """Number of tool calls made during this task."""
        return len(self.tool_calls)

    @property
    def num_ctx_cli_calls(self) -> int:
        """Number of ctx_cli commands executed."""
        return len(self.ctx_cli_commands)

    @property
    def prompt_delta(self) -> int:
        """Change in working context during this task."""
        return self.prompt_tokens - self.prompt_tokens_start

    def to_dict(self, include_debug: bool = True) -> dict:
        result = {
            "task_id": self.task_id,
            "task_name": self.task_name,
            # Legacy (includes system prompt)
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "context_at_start": self.context_at_start,
            "context_at_end": self.context_at_end,
            "context_delta": self.context_delta,
            # Working context (excludes system prompt - the real metrics)
            "prompt_tokens_start": self.prompt_tokens_start,
            "prompt_tokens": self.prompt_tokens,
            "prompt_delta": self.prompt_delta,
            "peak_prompt_tokens": self.peak_prompt_tokens,
            "completion_tokens": self.completion_tokens,
            # Performance
            "api_calls": self.api_calls,
            "execution_time": round(self.execution_time_seconds, 3),
            "success": self.success,
            "tool_calls": self.tool_calls,
            "ctx_cli_commands": self.ctx_cli_commands,
            "num_tool_calls": self.num_tool_calls,
            "num_ctx_cli_calls": self.num_ctx_cli_calls,
        }

        # Debug fields (for detailed inspection after long runs)
        if include_debug:
            result["debug"] = {
                "agent_output": self.agent_output,
                "prompt_sent": self.prompt_sent,
                "execution_log": self.execution_log,
                "ecm_state": self.ecm_state,
                "messages_snapshot": self.messages_snapshot,
            }

        return result


@dataclass
class CumulativeTokenReport:
    """
    Cumulative token tracking across N tasks.

    Key for paper: proves ECM solves N tasks without context explosion.
    """

    tasks: list[TaskTokenRecord] = field(default_factory=list)
    agent_type: str = ""  # "ecm" or "linear"
    model: str = ""
    benchmark: str = ""

    def add_task(self, record: TaskTokenRecord) -> None:
        """Add a completed task record."""
        self.tasks.append(record)

    @property
    def num_tasks(self) -> int:
        return len(self.tasks)

    @property
    def cumulative_input(self) -> list[int]:
        """Running total of input tokens after each task."""
        cumsum = 0
        result = []
        for t in self.tasks:
            cumsum += t.input_tokens
            result.append(cumsum)
        return result

    @property
    def cumulative_output(self) -> list[int]:
        """Running total of output tokens after each task."""
        cumsum = 0
        result = []
        for t in self.tasks:
            cumsum += t.output_tokens
            result.append(cumsum)
        return result

    @property
    def context_trajectory(self) -> list[int]:
        """Context window size after each task - key metric for paper."""
        return [t.context_at_end for t in self.tasks]

    # =========================================================================
    # Working Context Metrics (excludes system prompt - the real metrics)
    # =========================================================================

    @property
    def prompt_trajectory_start(self) -> list[int]:
        """Working context at START of each task."""
        return [t.prompt_tokens_start for t in self.tasks]

    @property
    def prompt_trajectory(self) -> list[int]:
        """Working context (excluding system prompt) at END of each task."""
        return [t.prompt_tokens for t in self.tasks]

    @property
    def peak_prompt(self) -> int:
        """Maximum working context across all tasks - key paper metric."""
        if not self.tasks:
            return 0
        return max(t.peak_prompt_tokens for t in self.tasks)

    @property
    def completion_trajectory(self) -> list[int]:
        """Completion tokens per task."""
        return [t.completion_tokens for t in self.tasks]

    @property
    def total_completion_tokens(self) -> int:
        """Sum of all completion tokens."""
        return sum(t.completion_tokens for t in self.tasks)

    @property
    def final_prompt(self) -> int:
        """Working context at last task."""
        return self.tasks[-1].prompt_tokens if self.tasks else 0

    @property
    def avg_prompt_growth_per_task(self) -> float:
        """Average increase in working context per task."""
        if len(self.tasks) < 2:
            return 0.0
        trajectory = self.prompt_trajectory
        if not trajectory:
            return 0.0
        first = trajectory[0]
        last = trajectory[-1]
        return (last - first) / len(self.tasks)

    @property
    def success_rate(self) -> float:
        """Fraction of tasks completed successfully."""
        if not self.tasks:
            return 0.0
        return sum(1 for t in self.tasks if t.success) / len(self.tasks)

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.tasks)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.tasks)

    @property
    def peak_context(self) -> int:
        """Maximum context window size across all tasks."""
        if not self.tasks:
            return 0
        return max(t.context_at_end for t in self.tasks)

    @property
    def final_context(self) -> int:
        """Context at last task."""
        return self.tasks[-1].context_at_end if self.tasks else 0

    @property
    def avg_context_growth_per_task(self) -> float:
        """Average increase in context per task."""
        if len(self.tasks) < 2:
            return 0.0
        first = self.tasks[0].context_at_start
        last = self.tasks[-1].context_at_end
        return (last - first) / len(self.tasks)

    def to_dict(self) -> dict:
        return {
            "metadata": {
                "agent_type": self.agent_type,
                "model": self.model,
                "benchmark": self.benchmark,
                "num_tasks": self.num_tasks,
            },
            "summary": {
                # Legacy (includes system prompt)
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "peak_context": self.peak_context,
                "final_context": self.final_context,
                "avg_context_growth": round(self.avg_context_growth_per_task, 1),
                # Working context (excludes system prompt - the real metrics)
                "peak_prompt": self.peak_prompt,
                "final_prompt": self.final_prompt,
                "avg_prompt_growth": round(self.avg_prompt_growth_per_task, 1),
                "total_completion_tokens": self.total_completion_tokens,
                # Success
                "success_rate": round(self.success_rate, 3),
            },
            "trajectory": {
                # Legacy
                "cumulative_input": self.cumulative_input,
                "cumulative_output": self.cumulative_output,
                "context_trajectory": self.context_trajectory,
                # Working context (key for paper figures)
                "prompt_trajectory_start": self.prompt_trajectory_start,
                "prompt_trajectory": self.prompt_trajectory,
                "completion_trajectory": self.completion_trajectory,
            },
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def to_csv(self, path: str) -> None:
        """Export per-task data for paper plots."""
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                # Task info
                "task_idx", "task_id", "task_name",
                # Working context (key metrics - excludes system prompt)
                "prompt_start", "prompt_end", "prompt_delta", "peak_prompt",
                "completion_tokens",
                # Cumulative working context
                "cumulative_prompt", "cumulative_completion",
                # Legacy (includes system prompt)
                "input_tokens", "output_tokens", "context_at_end",
                # Performance
                "api_calls", "success"
            ])
            cum_prompt = 0
            cum_completion = 0
            for i, t in enumerate(self.tasks):
                cum_prompt += t.prompt_tokens
                cum_completion += t.completion_tokens
                writer.writerow([
                    i + 1, t.task_id, t.task_name,
                    # Working context
                    t.prompt_tokens_start, t.prompt_tokens, t.prompt_delta, t.peak_prompt_tokens,
                    t.completion_tokens,
                    # Cumulative
                    cum_prompt, cum_completion,
                    # Legacy
                    t.input_tokens, t.output_tokens, t.context_at_end,
                    # Performance
                    t.api_calls, int(t.success)
                ])

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        """Save report to JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())


def compare_token_reports(ecm: CumulativeTokenReport, linear: CumulativeTokenReport) -> dict:
    """Compare ECM vs Linear cumulative reports."""
    return {
        "num_tasks": ecm.num_tasks,
        # Working context (key metrics - excludes system prompt)
        "peak_prompt": {
            "ecm": ecm.peak_prompt,
            "linear": linear.peak_prompt,
            "reduction": round(1 - ecm.peak_prompt / max(linear.peak_prompt, 1), 3),
        },
        "final_prompt": {
            "ecm": ecm.final_prompt,
            "linear": linear.final_prompt,
        },
        "prompt_growth_per_task": {
            "ecm": round(ecm.avg_prompt_growth_per_task, 1),
            "linear": round(linear.avg_prompt_growth_per_task, 1),
        },
        "total_completion_tokens": {
            "ecm": ecm.total_completion_tokens,
            "linear": linear.total_completion_tokens,
        },
        # Legacy (includes system prompt)
        "peak_context": {
            "ecm": ecm.peak_context,
            "linear": linear.peak_context,
            "reduction": round(1 - ecm.peak_context / max(linear.peak_context, 1), 3),
        },
        "final_context": {
            "ecm": ecm.final_context,
            "linear": linear.final_context,
        },
        "total_tokens": {
            "ecm": ecm.total_input_tokens + ecm.total_output_tokens,
            "linear": linear.total_input_tokens + linear.total_output_tokens,
        },
        "context_growth_per_task": {
            "ecm": round(ecm.avg_context_growth_per_task, 1),
            "linear": round(linear.avg_context_growth_per_task, 1),
        },
        # Success
        "success_rate": {
            "ecm": round(ecm.success_rate, 3),
            "linear": round(linear.success_rate, 3),
        },
    }


# =============================================================================
# Aggregate Metrics
# =============================================================================

@dataclass
class ECMMetrics:
    """Complete metrics for an ECM evaluation run."""

    token_metrics: TokenMetrics = field(default_factory=TokenMetrics)
    knowledge_metrics: KnowledgeMetrics = field(default_factory=KnowledgeMetrics)
    navigation_metrics: NavigationMetrics = field(default_factory=NavigationMetrics)
    utility_metrics: UtilityMetrics = field(default_factory=UtilityMetrics)

    # Metadata
    run_id: str = ""
    model: str = ""
    benchmark: str = ""
    agent_type: str = ""  # "ecm" or "linear"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "metadata": {
                "run_id": self.run_id,
                "model": self.model,
                "benchmark": self.benchmark,
                "agent_type": self.agent_type,
                "timestamp": self.timestamp,
            },
            "token_economics": self.token_metrics.to_dict(),
            "knowledge_transfer": self.knowledge_metrics.to_dict(),
            "navigation": self.navigation_metrics.to_dict(),
            "utility": self.utility_metrics.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        """Save metrics to JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "ECMMetrics":
        """Load metrics from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)

        metrics = cls()
        metrics.run_id = data.get("metadata", {}).get("run_id", "")
        metrics.model = data.get("metadata", {}).get("model", "")
        metrics.benchmark = data.get("metadata", {}).get("benchmark", "")
        metrics.agent_type = data.get("metadata", {}).get("agent_type", "")
        metrics.timestamp = data.get("metadata", {}).get("timestamp", "")

        # Restore token metrics
        tm = data.get("token_economics", {})
        metrics.token_metrics.total_input_tokens = tm.get("total_input_tokens", 0)
        metrics.token_metrics.total_output_tokens = tm.get("total_output_tokens", 0)
        metrics.token_metrics.api_calls = tm.get("api_calls", 0)
        metrics.token_metrics.tasks_completed = tm.get("tasks_completed", 0)
        metrics.token_metrics.tasks_total = tm.get("tasks_total", 0)

        return metrics


def compare_runs(ecm: ECMMetrics, linear: ECMMetrics) -> dict:
    """Compare ECM vs Linear metrics and compute relative improvements."""
    return {
        "context_reduction": round(compute_reduction_ratio(ecm.token_metrics, linear.token_metrics), 3),
        "speedup": round(compute_speedup(ecm.token_metrics, linear.token_metrics), 3),
        "peak_context": {
            "ecm": ecm.token_metrics.peak_context,
            "linear": linear.token_metrics.peak_context,
        },
        "total_tokens": {
            "ecm": ecm.token_metrics.total_tokens,
            "linear": linear.token_metrics.total_tokens,
        },
        "execution_time": {
            "ecm": round(ecm.token_metrics.execution_time_seconds, 2),
            "linear": round(linear.token_metrics.execution_time_seconds, 2),
        },
        "tasks_completed": {
            "ecm": ecm.token_metrics.tasks_completed,
            "linear": linear.token_metrics.tasks_completed,
        },
    }


# =============================================================================
# Metrics Collector (Integration with ContextStore)
# =============================================================================

class MetricsCollector:
    """
    Collects metrics during an ECM agent run.
    Integrates with ContextStore to track operations.
    """

    def __init__(self, model: str = "gpt-4o", agent_type: str = "ecm"):
        self.metrics = ECMMetrics(model=model, agent_type=agent_type)
        self._current_scope = "main"
        self._start_time: Optional[datetime] = None

    def start_run(self, run_id: str, benchmark: str) -> None:
        """Start tracking a run."""
        self.metrics.run_id = run_id
        self.metrics.benchmark = benchmark
        self._start_time = datetime.now()

    def end_run(self) -> None:
        """End tracking and compute final metrics."""
        if self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            self.metrics.token_metrics.execution_time_seconds = elapsed

    def record_api_call(self, messages: list[dict], response_tokens: int) -> None:
        """Record an API call with context and response."""
        context_tokens = count_context_tokens(messages)
        self.metrics.token_metrics.add_context_sample(context_tokens)
        self.metrics.token_metrics.total_input_tokens += context_tokens
        self.metrics.token_metrics.total_output_tokens += response_tokens

    def record_scope_operation(self, from_scope: str, to_scope: str,
                                operation: str, note: str) -> None:
        """Record a scope/goto operation."""
        self.metrics.navigation_metrics.record_transition(
            from_scope, to_scope, operation, note
        )
        self._current_scope = to_scope

    def record_note(self, content: str) -> None:
        """Record a note creation."""
        self.metrics.utility_metrics.record_note(content, self._current_scope)

    def record_insight(self, content: str) -> None:
        """Record an insight creation."""
        self.metrics.utility_metrics.record_insight(content)

    def record_notes_retrieval(self, scope: Optional[str] = None) -> None:
        """Record that notes were retrieved."""
        if scope:
            self.metrics.utility_metrics.record_note_retrieval(scope)

    def record_insights_retrieval(self, total_scopes: int) -> None:
        """Record that insights were retrieved."""
        self.metrics.utility_metrics.record_insight_retrieval(
            self._current_scope, total_scopes
        )

    def record_task_completed(self) -> None:
        """Record a task completion."""
        self.metrics.token_metrics.tasks_completed += 1

    def set_total_tasks(self, total: int) -> None:
        """Set the total number of tasks."""
        self.metrics.token_metrics.tasks_total = total

    def get_metrics(self) -> ECMMetrics:
        """Get the collected metrics."""
        return self.metrics
