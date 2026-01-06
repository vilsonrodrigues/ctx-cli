"""
Base Agent Interface for ECM Benchmarks.

Provides the abstract base class that all benchmark agents must implement,
along with common data structures for results.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any

from openai import OpenAI


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AgentResult:
    """Result from a single agent benchmark run."""
    agent_name: str
    dataset: str
    total_queries: int
    exact_match: float
    contains_match: float
    f1_score: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_query_time: float
    total_time: float
    extra_metrics: dict = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Comparison results across multiple agents."""
    dataset: str
    timestamp: str
    agents: list[AgentResult]
    config: dict


# =============================================================================
# Base Agent Interface
# =============================================================================

class BaseAgent(ABC):
    """
    Abstract base class for memory agents in ECM benchmarks.

    All benchmark agents (ECM, Mem0, Letta, RAG, Long Context) must
    implement this interface to be compatible with the evaluation framework.

    Key Methods:
        - memorize(): Store content in agent's memory
        - query(): Answer a question using stored memory
        - reset(): Clear agent state for new context
        - get_stats(): Return usage statistics
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the base agent.

        Args:
            model: LLM model to use for queries
            temperature: Temperature for LLM generation
            api_key: Optional OpenAI API key (uses env var if not provided)
        """
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Timing
        self.total_memorize_time = 0.0
        self.total_query_time = 0.0
        self.query_count = 0
        self.memorize_count = 0

    @abstractmethod
    def memorize(self, content: str, context_id: int = 0) -> None:
        """
        Store content in the agent's memory.

        Args:
            content: The content to memorize
            context_id: ID of the context (for multi-context benchmarks)
        """
        pass

    @abstractmethod
    def query(self, question: str, context_id: int = 0) -> dict:
        """
        Answer a question using the agent's memory.

        Args:
            question: The question to answer
            context_id: ID of the context to query against

        Returns:
            dict with keys:
                - answer: str - The generated answer
                - input_tokens: int - Tokens used in prompt
                - output_tokens: int - Tokens generated
                - latency: float - Query time in seconds
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset agent state for a new context/evaluation."""
        pass

    def get_stats(self) -> dict:
        """
        Get agent statistics.

        Returns:
            dict with usage statistics
        """
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_memorize_time": self.total_memorize_time,
            "total_query_time": self.total_query_time,
            "query_count": self.query_count,
            "memorize_count": self.memorize_count,
        }

    def _call_llm(
        self,
        messages: list[dict],
        max_tokens: int = 500,
    ) -> dict:
        """
        Helper method to call the LLM with token tracking.

        Args:
            messages: List of message dicts for the LLM
            max_tokens: Maximum tokens to generate

        Returns:
            dict with answer, input_tokens, output_tokens, latency
        """
        start_time = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        latency = time.time() - start_time

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        return {
            "answer": response.choices[0].message.content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency": latency,
        }
