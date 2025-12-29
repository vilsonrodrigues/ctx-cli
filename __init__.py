"""ctx-cli: Git-like context management for LLM agents."""

from ctx_store import ContextStore, Message, Commit, Tag, Branch, Event
from ctx_cli import CTX_CLI_TOOL, parse_command, execute_command
from policies import (
    Policy,
    PolicyEngine,
    PolicyAction,
    PolicyResult,
    MaxMessagesPolicy,
    MaxTokensPolicy,
    InactivityPolicy,
    NoCommitPolicy,
    create_conservative_policies,
    create_relaxed_policies,
    create_strict_policies,
)
from tokens import (
    TokenTracker,
    count_tokens_tiktoken,
    estimate_tokens,
    count_message_tokens,
    count_context_tokens,
    get_model_context_limit,
    TIKTOKEN_AVAILABLE,
)

__all__ = [
    # Core
    "ContextStore",
    "Message",
    "Commit",
    "Tag",
    "Branch",
    "Event",
    # CLI
    "CTX_CLI_TOOL",
    "parse_command",
    "execute_command",
    # Policies
    "Policy",
    "PolicyEngine",
    "PolicyAction",
    "PolicyResult",
    "MaxMessagesPolicy",
    "MaxTokensPolicy",
    "InactivityPolicy",
    "NoCommitPolicy",
    "create_conservative_policies",
    "create_relaxed_policies",
    "create_strict_policies",
    # Tokens
    "TokenTracker",
    "count_tokens_tiktoken",
    "estimate_tokens",
    "count_message_tokens",
    "count_context_tokens",
    "get_model_context_limit",
    "TIKTOKEN_AVAILABLE",
]
