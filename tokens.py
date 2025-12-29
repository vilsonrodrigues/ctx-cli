"""
Token counting utilities.

Provides accurate token counting using tiktoken for OpenAI models,
with fallback to estimation for other models.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ctx_store import Message

# Try to import tiktoken, fallback to estimation if not available
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


@lru_cache(maxsize=4)
def get_encoding(model: str) -> "tiktoken.Encoding | None":
    """Get tiktoken encoding for a model."""
    if not TIKTOKEN_AVAILABLE:
        return None

    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models
        return tiktoken.get_encoding("cl100k_base")


def count_tokens_tiktoken(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken."""
    encoding = get_encoding(model)
    if encoding is None:
        return estimate_tokens(text)
    return len(encoding.encode(text))


def estimate_tokens(text: str) -> int:
    """
    Estimate token count without tiktoken.

    Uses a rough heuristic of ~4 characters per token.
    """
    return max(1, len(text) // 4)


def count_message_tokens(
    message: dict,
    model: str = "gpt-4o",
) -> int:
    """
    Count tokens in a single message.

    Accounts for message structure overhead (role, etc).
    """
    # Base overhead per message (role, separators)
    overhead = 4  # <|im_start|>role<|im_sep|>...<|im_end|>

    content = message.get("content", "")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        # Handle content arrays (for images, etc)
        text = " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    else:
        text = str(content)

    # Add role
    text += message.get("role", "")

    # Add function/tool call info if present
    if "tool_calls" in message and message["tool_calls"]:
        for tc in message["tool_calls"]:
            if isinstance(tc, dict):
                text += tc.get("function", {}).get("name", "")
                text += tc.get("function", {}).get("arguments", "")

    if "name" in message:
        text += message["name"]

    if TIKTOKEN_AVAILABLE:
        return count_tokens_tiktoken(text, model) + overhead
    return estimate_tokens(text) + overhead


def count_context_tokens(
    messages: list[dict],
    model: str = "gpt-4o",
) -> int:
    """
    Count total tokens in a message list.

    Includes per-message overhead and reply priming.
    """
    total = 0

    for msg in messages:
        total += count_message_tokens(msg, model)

    # Add reply priming overhead
    total += 3  # <|im_start|>assistant<|im_sep|>

    return total


def get_model_context_limit(model: str) -> int:
    """Get the context window limit for a model."""
    limits = {
        # OpenAI
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        # Anthropic (approximate)
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        # Default
        "default": 128000,
    }

    for key, limit in limits.items():
        if key in model.lower():
            return limit

    return limits["default"]


class TokenTracker:
    """
    Tracks token usage across a conversation.

    Provides real-time estimates and warnings.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.context_limit = get_model_context_limit(model)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.current_context_tokens = 0

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if TIKTOKEN_AVAILABLE:
            return count_tokens_tiktoken(text, self.model)
        return estimate_tokens(text)

    def count_messages(self, messages: list[dict]) -> int:
        """Count tokens in message list."""
        return count_context_tokens(messages, self.model)

    def update_context(self, messages: list[dict]) -> int:
        """Update current context token count."""
        self.current_context_tokens = self.count_messages(messages)
        return self.current_context_tokens

    def add_input(self, tokens: int) -> None:
        """Track input tokens used."""
        self.total_input_tokens += tokens

    def add_output(self, tokens: int) -> None:
        """Track output tokens used."""
        self.total_output_tokens += tokens

    def get_usage_percent(self) -> float:
        """Get current context usage as percentage."""
        return (self.current_context_tokens / self.context_limit) * 100

    def get_remaining(self) -> int:
        """Get remaining tokens in context window."""
        return self.context_limit - self.current_context_tokens

    def is_near_limit(self, threshold: float = 0.8) -> bool:
        """Check if context is near limit."""
        return self.get_usage_percent() >= (threshold * 100)

    def get_stats(self) -> dict:
        """Get token usage statistics."""
        return {
            "model": self.model,
            "context_limit": self.context_limit,
            "current_context": self.current_context_tokens,
            "usage_percent": round(self.get_usage_percent(), 1),
            "remaining": self.get_remaining(),
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "total": self.total_input_tokens + self.total_output_tokens,
            "tiktoken_available": TIKTOKEN_AVAILABLE,
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"TokenTracker(model={stats['model']}, "
            f"context={stats['current_context']:,}/{stats['context_limit']:,} "
            f"({stats['usage_percent']}%), "
            f"total={stats['total']:,})"
        )
