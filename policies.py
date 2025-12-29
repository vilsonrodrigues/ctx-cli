"""
Policies - Automatic context management rules.

Policies are rules that trigger actions based on context state.
They help ensure the model doesn't overflow the context window.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ctx_store import ContextStore


class PolicyAction(Enum):
    """Actions that a policy can trigger."""

    SUGGEST_COMMIT = "suggest_commit"  # Add system message suggesting commit
    FORCE_COMMIT = "force_commit"  # Automatically commit with generated message
    WARN = "warn"  # Add warning system message
    BLOCK = "block"  # Prevent adding more messages


@dataclass
class PolicyResult:
    """Result of evaluating a policy."""

    triggered: bool
    action: PolicyAction | None = None
    message: str | None = None
    auto_commit_message: str | None = None


class Policy(ABC):
    """Base class for context policies."""

    name: str
    enabled: bool = True

    @abstractmethod
    def evaluate(self, store: "ContextStore") -> PolicyResult:
        """Evaluate if this policy should trigger."""
        ...


@dataclass
class MaxMessagesPolicy(Policy):
    """
    Trigger when working messages exceed a threshold.

    Useful for preventing context overflow by encouraging commits.
    """

    name: str = "max_messages"
    max_messages: int = 20
    warn_at: int = 15
    action: PolicyAction = PolicyAction.SUGGEST_COMMIT
    enabled: bool = True

    def evaluate(self, store: "ContextStore") -> PolicyResult:
        if not self.enabled:
            return PolicyResult(triggered=False)

        branch = store.branches[store.current_branch]
        msg_count = len(branch.messages)

        if msg_count >= self.max_messages:
            return PolicyResult(
                triggered=True,
                action=self.action,
                message=f"[POLICY] Working memory has {msg_count} messages (max: {self.max_messages}). "
                f"Consider committing to preserve your reasoning.",
                auto_commit_message=f"Auto-commit: {msg_count} messages accumulated",
            )

        if msg_count >= self.warn_at:
            return PolicyResult(
                triggered=True,
                action=PolicyAction.WARN,
                message=f"[POLICY] Working memory approaching limit: {msg_count}/{self.max_messages} messages.",
            )

        return PolicyResult(triggered=False)


@dataclass
class MaxTokensPolicy(Policy):
    """
    Trigger when estimated tokens exceed a threshold.

    More accurate than message count for managing context window.
    """

    name: str = "max_tokens"
    max_tokens: int = 50000
    warn_at: int = 40000
    action: PolicyAction = PolicyAction.SUGGEST_COMMIT
    enabled: bool = True
    token_counter: Callable[[str], int] | None = None  # Optional custom counter

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.token_counter:
            return self.token_counter(text)
        # Rough estimate: ~4 chars per token
        return len(text) // 4

    def evaluate(self, store: "ContextStore") -> PolicyResult:
        if not self.enabled:
            return PolicyResult(triggered=False)

        # Count tokens in current context
        context = store.get_context()
        total_chars = sum(len(str(m)) for m in context)
        estimated_tokens = self._count_tokens("x" * total_chars)

        if estimated_tokens >= self.max_tokens:
            return PolicyResult(
                triggered=True,
                action=self.action,
                message=f"[POLICY] Context has ~{estimated_tokens:,} tokens (max: {self.max_tokens:,}). "
                f"Commit now to avoid overflow.",
                auto_commit_message=f"Auto-commit: ~{estimated_tokens:,} tokens accumulated",
            )

        if estimated_tokens >= self.warn_at:
            return PolicyResult(
                triggered=True,
                action=PolicyAction.WARN,
                message=f"[POLICY] Context approaching limit: ~{estimated_tokens:,}/{self.max_tokens:,} tokens.",
            )

        return PolicyResult(triggered=False)


@dataclass
class InactivityPolicy(Policy):
    """
    Trigger when branch has been active for too long without commits.

    Encourages regular checkpointing.
    """

    name: str = "inactivity"
    max_messages_since_commit: int = 10
    action: PolicyAction = PolicyAction.SUGGEST_COMMIT
    enabled: bool = True

    def evaluate(self, store: "ContextStore") -> PolicyResult:
        if not self.enabled:
            return PolicyResult(triggered=False)

        branch = store.branches[store.current_branch]
        msg_count = len(branch.messages)

        if msg_count >= self.max_messages_since_commit and branch.commits:
            return PolicyResult(
                triggered=True,
                action=self.action,
                message=f"[POLICY] {msg_count} messages since last commit. "
                f"Consider committing to checkpoint your progress.",
                auto_commit_message=f"Checkpoint: {msg_count} messages since last commit",
            )

        return PolicyResult(triggered=False)


@dataclass
class NoCommitPolicy(Policy):
    """
    Trigger when branch has messages but no commits yet.

    Ensures work is saved before switching branches.
    """

    name: str = "no_commit"
    min_messages: int = 5
    action: PolicyAction = PolicyAction.WARN
    enabled: bool = True

    def evaluate(self, store: "ContextStore") -> PolicyResult:
        if not self.enabled:
            return PolicyResult(triggered=False)

        branch = store.branches[store.current_branch]

        if not branch.commits and len(branch.messages) >= self.min_messages:
            return PolicyResult(
                triggered=True,
                action=self.action,
                message=f"[POLICY] Branch '{store.current_branch}' has no commits yet. "
                f"Consider committing before switching branches.",
            )

        return PolicyResult(triggered=False)


@dataclass
class PolicyEngine:
    """
    Engine that evaluates policies and takes actions.

    The engine runs all policies and collects their results.
    """

    policies: list[Policy] = field(default_factory=list)

    def __post_init__(self):
        if not self.policies:
            # Default policies
            self.policies = [
                MaxMessagesPolicy(),
                MaxTokensPolicy(),
                InactivityPolicy(),
                NoCommitPolicy(),
            ]

    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the engine."""
        self.policies.append(policy)

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name."""
        for i, p in enumerate(self.policies):
            if p.name == name:
                self.policies.pop(i)
                return True
        return False

    def enable_policy(self, name: str) -> bool:
        """Enable a policy by name."""
        for p in self.policies:
            if p.name == name:
                p.enabled = True
                return True
        return False

    def disable_policy(self, name: str) -> bool:
        """Disable a policy by name."""
        for p in self.policies:
            if p.name == name:
                p.enabled = False
                return True
        return False

    def evaluate(self, store: "ContextStore") -> list[PolicyResult]:
        """Evaluate all policies and return triggered results."""
        results = []

        for policy in self.policies:
            result = policy.evaluate(store)
            if result.triggered:
                results.append(result)

        return results

    def get_system_messages(self, store: "ContextStore") -> list[str]:
        """Get system messages from triggered policies."""
        results = self.evaluate(store)
        return [r.message for r in results if r.message and r.action in (
            PolicyAction.WARN,
            PolicyAction.SUGGEST_COMMIT,
        )]

    def should_force_commit(self, store: "ContextStore") -> tuple[bool, str | None]:
        """Check if any policy requires forced commit."""
        results = self.evaluate(store)

        for r in results:
            if r.action == PolicyAction.FORCE_COMMIT:
                return True, r.auto_commit_message

        return False, None

    def should_block(self, store: "ContextStore") -> tuple[bool, str | None]:
        """Check if any policy blocks adding messages."""
        results = self.evaluate(store)

        for r in results:
            if r.action == PolicyAction.BLOCK:
                return True, r.message

        return False, None


# =============================================================================
# Pre-configured policy sets
# =============================================================================

def create_conservative_policies() -> PolicyEngine:
    """Create policies for conservative token usage."""
    return PolicyEngine(policies=[
        MaxMessagesPolicy(max_messages=15, warn_at=10),
        MaxTokensPolicy(max_tokens=30000, warn_at=20000),
        InactivityPolicy(max_messages_since_commit=5),
        NoCommitPolicy(min_messages=3),
    ])


def create_relaxed_policies() -> PolicyEngine:
    """Create policies for larger context windows."""
    return PolicyEngine(policies=[
        MaxMessagesPolicy(max_messages=50, warn_at=40),
        MaxTokensPolicy(max_tokens=100000, warn_at=80000),
        InactivityPolicy(max_messages_since_commit=20),
        NoCommitPolicy(min_messages=10),
    ])


def create_strict_policies() -> PolicyEngine:
    """Create policies that force commits automatically."""
    return PolicyEngine(policies=[
        MaxMessagesPolicy(
            max_messages=10,
            warn_at=7,
            action=PolicyAction.FORCE_COMMIT
        ),
        MaxTokensPolicy(
            max_tokens=20000,
            warn_at=15000,
            action=PolicyAction.FORCE_COMMIT
        ),
        InactivityPolicy(max_messages_since_commit=5),
        NoCommitPolicy(min_messages=3),
    ])
