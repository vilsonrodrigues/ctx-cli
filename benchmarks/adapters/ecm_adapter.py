"""
ECM Adapter for MemoryAgentBench.

Integrates Explicit Context Management (ECM) as a memory agent
compatible with the MemoryAgentBench evaluation framework.

Usage:
    from benchmarks.adapters.ecm_adapter import ECMAgentWrapper

    agent = ECMAgentWrapper(agent_config, dataset_config, load_agent_from=None)
    agent.send_message(context, memorizing=True)  # Memorize
    result = agent.send_message(query, memorizing=False)  # Query
"""

import os
import sys
import json
import time
import logging
import tiktoken
from typing import Optional, Any
from datetime import datetime
from openai import OpenAI

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ctx_store import ContextStore, Message, Note, Insight
from metrics import MetricsCollector, ECMMetrics

# =============================================================================
# ECM Logger
# =============================================================================

class ECMLogger:
    """Logger for ECM operations - produces detailed ctx-cli usage logs."""

    def __init__(self, verbose: bool = True, log_file: Optional[str] = None):
        self.verbose = verbose
        self.log_file = log_file
        self.operations: list[dict] = []
        self.start_time = time.time()

        # Setup file logging if specified
        if log_file:
            self.file_handler = open(log_file, "w")
        else:
            self.file_handler = None

    def _timestamp(self) -> str:
        elapsed = time.time() - self.start_time
        return f"[{elapsed:7.2f}s]"

    def _log(self, level: str, message: str, details: Optional[dict] = None):
        """Internal logging method."""
        entry = {
            "timestamp": time.time() - self.start_time,
            "level": level,
            "message": message,
            "details": details or {}
        }
        self.operations.append(entry)

        # Format for display
        prefix = {
            "CMD": "🔧",
            "SCOPE": "📁",
            "GOTO": "➡️ ",
            "NOTE": "📝",
            "INSIGHT": "💡",
            "PULL": "📥",
            "QUERY": "❓",
            "RESPONSE": "💬",
            "MEMORIZE": "💾",
            "INFO": "ℹ️ ",
        }.get(level, "•")

        log_line = f"{self._timestamp()} {prefix} {message}"

        if self.verbose:
            print(log_line)

        if self.file_handler:
            # Write without emoji for file
            self.file_handler.write(f"{self._timestamp()} [{level}] {message}\n")
            if details:
                self.file_handler.write(f"           Details: {json.dumps(details, ensure_ascii=False)[:200]}\n")
            self.file_handler.flush()

    def cmd(self, command: str, result: Optional[str] = None):
        """Log a ctx-cli command execution."""
        self._log("CMD", f"ctx_cli {command}", {"result": result[:100] if result else None})

    def scope(self, name: str, note: str, from_scope: str):
        """Log scope creation."""
        self._log("SCOPE", f"scope {name} -m \"{note[:50]}...\"", {
            "from": from_scope,
            "to": name,
            "note": note
        })

    def goto(self, name: str, note: str, from_scope: str):
        """Log goto operation."""
        self._log("GOTO", f"goto {name} -m \"{note[:50]}...\"", {
            "from": from_scope,
            "to": name,
            "note": note
        })

    def note(self, content: str, scope: str):
        """Log note creation."""
        self._log("NOTE", f"note -m \"{content[:60]}...\" (in {scope})", {
            "scope": scope,
            "content": content
        })

    def insight(self, content: str):
        """Log insight creation."""
        self._log("INSIGHT", f"insight -m \"{content[:60]}...\"", {
            "content": content
        })

    def pull_notes(self, scope: Optional[str], count: int):
        """Log notes retrieval."""
        scope_str = scope or "all"
        self._log("PULL", f"notes {scope_str} → {count} notes retrieved", {
            "scope": scope_str,
            "count": count
        })

    def pull_insights(self, count: int):
        """Log insights retrieval."""
        self._log("PULL", f"insights → {count} insights retrieved", {
            "count": count
        })

    def memorize(self, content_preview: str, chunks: int, scope: str):
        """Log memorization operation."""
        self._log("MEMORIZE", f"Memorizing {chunks} chunk(s) in {scope}: \"{content_preview[:40]}...\"", {
            "chunks": chunks,
            "scope": scope
        })

    def query(self, query: str, scope: str, context_tokens: int):
        """Log query operation."""
        self._log("QUERY", f"Query in {scope} ({context_tokens} tokens): \"{query[:50]}...\"", {
            "scope": scope,
            "tokens": context_tokens,
            "query": query
        })

    def response(self, response: str, tokens: int):
        """Log response."""
        self._log("RESPONSE", f"Response ({tokens} tokens): \"{response[:60]}...\"", {
            "tokens": tokens,
            "response": response[:200]
        })

    def info(self, message: str):
        """Log info message."""
        self._log("INFO", message)

    def get_operations(self) -> list[dict]:
        """Get all logged operations."""
        return self.operations

    def get_summary(self) -> dict:
        """Get summary of operations."""
        counts = {}
        for op in self.operations:
            level = op["level"]
            counts[level] = counts.get(level, 0) + 1
        return {
            "total_operations": len(self.operations),
            "by_type": counts,
            "duration_seconds": time.time() - self.start_time,
        }

    def print_summary(self):
        """Print operation summary."""
        summary = self.get_summary()
        print("\n" + "=" * 50)
        print("ECM OPERATIONS SUMMARY")
        print("=" * 50)
        print(f"Total Operations: {summary['total_operations']}")
        print(f"Duration: {summary['duration_seconds']:.2f}s")
        print("\nBy Type:")
        for op_type, count in sorted(summary['by_type'].items()):
            print(f"  {op_type}: {count}")

    def close(self):
        """Close file handler if open."""
        if self.file_handler:
            self.file_handler.close()


class ECMAgentWrapper:
    """
    ECM Agent wrapper compatible with MemoryAgentBench.

    Implements the same interface as other agents (Letta, Mem0, Cognee)
    but uses ECM's scope-based memory management.
    """

    def __init__(
        self,
        agent_config: dict,
        dataset_config: dict,
        load_agent_from: Optional[str] = None,
        verbose_logging: bool = True,
        log_file: Optional[str] = None,
    ):
        """
        Initialize ECM agent.

        Args:
            agent_config: Agent configuration dict with model, temperature, etc.
            dataset_config: Dataset configuration with context limits, etc.
            load_agent_from: Optional path to load existing agent state
            verbose_logging: If True, print ECM operations to console
            log_file: Optional file path to write ECM logs
        """
        # Initialize logger first
        self.logger = ECMLogger(verbose=verbose_logging, log_file=log_file)
        self.logger.info(f"Initializing ECM Agent")

        # Basic configuration
        self.agent_name = agent_config.get('agent_name', 'ecm_agent')
        self.sub_dataset = dataset_config.get('sub_dataset', 'default')
        self.dataset = dataset_config.get('dataset', 'custom')

        # Model configuration
        self.model = agent_config.get('model', 'gpt-4o-mini')
        self.temperature = agent_config.get('temperature', 0.0)
        self.max_tokens = dataset_config.get('generation_max_length', 4000)

        # Context limits
        self.context_max_length = dataset_config.get('context_max_length', 128000)
        self.input_length_limit = (
            agent_config.get('input_length_limit', 128000) -
            agent_config.get('buffer_length', 1000) -
            self.max_tokens
        )

        # ECM-specific configuration
        self.chunk_size = agent_config.get('agent_chunk_size', 1000)
        self.use_insights = agent_config.get('use_insights', True)
        self.auto_scope = agent_config.get('auto_scope', True)

        # Initialize components
        self._initialize_ecm(load_agent_from)
        self._initialize_client()
        self._initialize_tokenizer()

        # Metrics tracking
        self.metrics_collector = MetricsCollector(model=self.model, agent_type="ecm")
        self.agent_start_time = time.time()

        # State tracking
        self.current_context_id = -1
        self.memorized_chunks = 0

        self.logger.info(f"ECM Agent ready (model={self.model}, insights={self.use_insights})")

    def _initialize_ecm(self, load_from: Optional[str] = None):
        """Initialize ECM context store."""
        self.store = ContextStore()

        if load_from and os.path.exists(load_from):
            self._load_state(load_from)

    def _initialize_client(self):
        """Initialize OpenAI client."""
        # Check for Azure
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if azure_endpoint:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=azure_endpoint,
            )
        else:
            self.client = OpenAI()

    def _initialize_tokenizer(self):
        """Initialize tokenizer for token counting."""
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def _create_standard_response(
        self,
        output: str,
        input_tokens: int,
        output_tokens: int,
        memory_time: float,
        query_time: float,
    ) -> dict:
        """Create standardized response dictionary."""
        return {
            "output": output,
            "input_len": input_tokens,
            "output_len": output_tokens,
            "memory_construction_time": memory_time,
            "query_time_len": query_time,
            # ECM-specific metrics
            "ecm_metrics": {
                "current_scope": self.store.current_branch,
                "total_scopes": len(self.store.branches),
                "total_notes": sum(len(b.notes) for b in self.store.branches.values()),
                "total_insights": len(self.store.insights),
                "working_memory_size": len(self.store._get_current_branch().messages),
            }
        }

    # =========================================================================
    # Core Interface (MemoryAgentBench compatible)
    # =========================================================================

    def send_message(
        self,
        message: str,
        memorizing: bool = False,
        query_id: Optional[int] = None,
        context_id: Optional[int] = None,
    ) -> Any:
        """
        Send a message for memorization or querying.

        Args:
            message: Content to memorize or query to answer
            memorizing: True for memorization, False for querying
            query_id: Unique query identifier
            context_id: Unique context identifier

        Returns:
            "Memorized" for memorization, or response dict for queries
        """
        if memorizing:
            return self._memorize(message, context_id)
        else:
            return self._query(message, query_id, context_id)

    def _memorize(self, content: str, context_id: Optional[int] = None) -> str:
        """
        Present content to the model for ECM processing.

        The model sees the content with ECM prompt and decides:
        - Whether to create notes (episodic memory)
        - Whether to create insights (semantic memory)
        - Using ctx_cli commands in its response
        """
        # Track context changes
        if context_id is not None and context_id != self.current_context_id:
            self._switch_context(context_id)
            self.current_context_id = context_id

        # Chunk the content if too large
        chunks = self._chunk_content(content)

        # Log memorization
        self.logger.memorize(content[:100], len(chunks), self.store.current_branch)

        for i, chunk in enumerate(chunks):
            self.memorized_chunks += 1

            # Let the model process and decide what to memorize
            if self.use_insights:
                self._process_with_ecm(chunk)
            else:
                # Fallback: simple note without model decision
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                note_content = f"[{timestamp}] {chunk[:300]}"
                self.store.note(note_content)
                self.logger.note(note_content, self.store.current_branch)

        # Track metrics
        self.metrics_collector.record_note(f"Processed {len(chunks)} chunks")

        return "Memorized"

    def _process_with_ecm(self, content: str):
        """
        Let the model process content using ECM commands.

        The model receives the ECM prompt and can use:
        - note -m "message" to save episodic facts
        - insight -m "message" to save semantic patterns
        """
        from prompts import SYSTEM_PROMPT_ECM_MEMORY

        # Build memory context
        memory_state = self._get_memory_state()
        system = SYSTEM_PROMPT_ECM_MEMORY + f"\n\n# CURRENT STATE\n{memory_state}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Process this information. Use note/insight commands only for important facts:\n\n{content[:1500]}"}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_tokens=400,
            )

            output = response.choices[0].message.content
            self._parse_ecm_commands(output)

        except Exception as e:
            # Fallback: create simple note
            self.store.note(content[:200])

    def _get_memory_state(self) -> str:
        """Get current memory state for prompt."""
        branch = self.store.branches.get(self.store.current_branch)
        note_count = len(branch.notes) if branch else 0
        insight_count = len(self.store.insights)
        return f"scope={self.store.current_branch} | notes={note_count} | insights={insight_count}"

    def _parse_ecm_commands(self, response: str):
        """Parse and execute ctx_cli commands from model response."""
        import re

        # Patterns matching ctx_cli format
        patterns = [
            # note -m "message"
            (r'note\s+-m\s+"([^"]+)"', self._exec_note),
            (r"note\s+-m\s+'([^']+)'", self._exec_note),
            # insight -m "message"
            (r'insight\s+-m\s+"([^"]+)"', self._exec_insight),
            (r"insight\s+-m\s+'([^']+)'", self._exec_insight),
            # scope name -m "reason"
            (r'scope\s+(\S+)\s+-m\s+"([^"]+)"', self._exec_scope),
            (r"scope\s+(\S+)\s+-m\s+'([^']+)'", self._exec_scope),
        ]

        for pattern, handler in patterns:
            for match in re.finditer(pattern, response):
                groups = match.groups()
                handler(*groups)

    def _exec_note(self, message: str):
        """Execute note command."""
        self.store.note(message)
        self.logger.note(message, self.store.current_branch)
        self.metrics_collector.record_note(message)

    def _exec_insight(self, message: str):
        """Execute insight command."""
        self.store.insight(message)
        self.logger.insight(message)
        self.metrics_collector.record_insight(message)

    def _exec_scope(self, name: str, reason: str):
        """Execute scope command."""
        old_scope = self.store.current_branch
        self.store.checkout(name, note=reason, create=True)
        self.logger.scope(name, reason, old_scope)

    def _query(
        self,
        query: str,
        query_id: Optional[int] = None,
        context_id: Optional[int] = None,
    ) -> dict:
        """
        Answer a query using ECM's memory system.

        ECM approach:
        1. Pull relevant notes from current and related scopes
        2. Pull global insights
        3. Compose context with pulled memories
        4. Generate response
        """
        memory_construction_time = time.time() - self.agent_start_time

        # Ensure we're in the right context
        if context_id is not None and context_id != self.current_context_id:
            self._switch_context(context_id)
            self.current_context_id = context_id

        # Pull memories using ECM commands
        notes_context = self._pull_notes()
        insights_context = self._pull_insights()

        # Build prompt with pulled memories
        system_prompt = self._build_system_prompt(notes_context, insights_context)

        # Add query as user message
        self.store.add_message(Message(role="user", content=query))

        # Get context for API call
        messages = self.store.get_context(system_prompt)

        # Track context size
        context_tokens = self._count_tokens(json.dumps(messages))
        self.metrics_collector.record_api_call(messages, 0)

        # Log query
        self.logger.query(query, self.store.current_branch, context_tokens)

        # Call API
        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            output = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

        except Exception as e:
            output = f"Error: {str(e)}"
            input_tokens = context_tokens
            output_tokens = 0

        # Log response
        self.logger.response(output, output_tokens)

        # Add assistant response to store
        self.store.add_message(Message(role="assistant", content=output))

        # Calculate times
        query_time = time.time() - start_time
        self.agent_start_time = time.time()

        # Record metrics
        self.metrics_collector.metrics.token_metrics.total_input_tokens += input_tokens
        self.metrics_collector.metrics.token_metrics.total_output_tokens += output_tokens

        return self._create_standard_response(
            output,
            input_tokens,
            output_tokens,
            memory_construction_time,
            query_time,
        )

    # =========================================================================
    # ECM-Specific Methods
    # =========================================================================

    def _switch_context(self, context_id: int):
        """
        Switch to a new context scope.
        
        Uses new_project() to properly reset the session while preserving
        notes from previous contexts for cross-context memory retrieval.
        """
        scope_name = f"context_{context_id}"
        old_scope = self.store.current_branch
        
        # Use new_project when switching to a completely new context
        # This preserves old main as main-{previous_project} for reference
        if context_id != self.current_context_id and self.current_context_id >= 0:
            project_name = f"context_{context_id}"
            self.store.new_project(project_name)
            self.logger.info(f"New project: {project_name} (previous context preserved)")
            self.metrics_collector.record_scope_operation(
                old_scope, "main", "new_project", f"Starting context {context_id}"
            )
        
        # Now create the working scope within this project
        if scope_name not in self.store.branches:
            note = f"Starting context {context_id}"
            self.store.checkout(scope_name, note=note, create=True)
            self.logger.scope(scope_name, note, self.store.current_branch)
            self.metrics_collector.record_scope_operation(
                self.store.current_branch, scope_name, "scope", note
            )

    def _chunk_content(self, content: str) -> list[str]:
        """Split content into chunks based on token limit."""
        tokens = self.tokenizer.encode(content, disallowed_special=())

        if len(tokens) <= self.chunk_size:
            return [content]

        chunks = []
        for i in range(0, len(tokens), self.chunk_size):
            chunk_tokens = tokens[i:i + self.chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks

    def _pull_notes(self) -> str:
        """Pull relevant notes using ECM's notes command."""
        notes_output = self.store.get_all_notes()
        # Count notes in current scope
        current_branch = self.store.branches.get(self.store.current_branch)
        note_count = len(current_branch.notes) if current_branch else 0
        self.logger.pull_notes(self.store.current_branch, note_count)
        self.metrics_collector.record_notes_retrieval(self.store.current_branch)
        return notes_output

    def _pull_insights(self) -> str:
        """Pull global insights using ECM's insights command."""
        insights_output = self.store.get_insights()
        insight_count = len(self.store.insights)
        self.logger.pull_insights(insight_count)
        self.metrics_collector.record_insights_retrieval(len(self.store.branches))
        return insights_output

    def _build_system_prompt(self, notes: str, insights: str) -> str:
        """Build system prompt with pulled memories."""
        prompt_parts = [
            "You are a helpful assistant with access to memory.",
            "Answer questions based on the context and your memory.",
            ""
        ]

        if insights and "No" not in insights[:20]:
            prompt_parts.extend([
                "## Global Knowledge (Insights)",
                insights,
                ""
            ])

        if notes and "No" not in notes[:20]:
            # Truncate notes if too long
            max_notes_tokens = self.input_length_limit // 3
            notes_tokens = self._count_tokens(notes)
            if notes_tokens > max_notes_tokens:
                notes_encoded = self.tokenizer.encode(notes, disallowed_special=())
                notes = self.tokenizer.decode(notes_encoded[-max_notes_tokens:])

            prompt_parts.extend([
                "## Memory (Notes from previous interactions)",
                notes,
                ""
            ])

        return "\n".join(prompt_parts)

    # =========================================================================
    # State Management
    # =========================================================================

    def save_state(self, path: str):
        """Save agent state to file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        state = {
            "store": self.store.to_dict(),
            "current_context_id": self.current_context_id,
            "memorized_chunks": self.memorized_chunks,
            "metrics": self.metrics_collector.get_metrics().to_dict(),
        }

        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self, path: str):
        """Load agent state from file."""
        with open(path, "r") as f:
            state = json.load(f)

        # Reconstruct store from dict
        # Note: This is a simplified version; full reconstruction would need more work
        self.current_context_id = state.get("current_context_id", -1)
        self.memorized_chunks = state.get("memorized_chunks", 0)

    def get_metrics(self) -> ECMMetrics:
        """Get collected metrics."""
        return self.metrics_collector.get_metrics()

    def get_status(self) -> dict:
        """Get current ECM status."""
        return {
            "current_scope": self.store.current_branch,
            "total_scopes": len(self.store.branches),
            "total_notes": sum(len(b.notes) for b in self.store.branches.values()),
            "total_insights": len(self.store.insights),
            "working_memory_size": len(self.store._get_current_branch().messages),
            "memorized_chunks": self.memorized_chunks,
        }


# =============================================================================
# Configuration Templates
# =============================================================================

def get_ecm_agent_config(
    model: str = "gpt-4o-mini",
    chunk_size: int = 1000,
    use_insights: bool = True,
) -> dict:
    """Get default ECM agent configuration."""
    return {
        "agent_name": "ecm_agent",
        "model": model,
        "temperature": 0.0,
        "input_length_limit": 128000,
        "buffer_length": 1000,
        "agent_chunk_size": chunk_size,
        "use_insights": use_insights,
        "auto_scope": True,
        "output_dir": "benchmarks/results/ecm",
    }


def get_ecm_dataset_config(
    dataset: str = "custom",
    sub_dataset: str = "default",
    context_max_length: int = 64000,
) -> dict:
    """Get default dataset configuration for ECM."""
    return {
        "dataset": dataset,
        "sub_dataset": sub_dataset,
        "context_max_length": context_max_length,
        "generation_max_length": 4000,
        "chunk_size": 1000,
    }


# =============================================================================
# Integration with MemoryAgentBench
# =============================================================================

def create_ecm_agent_for_benchmark(
    agent_config: dict,
    dataset_config: dict,
    load_agent_from: Optional[str] = None,
) -> ECMAgentWrapper:
    """
    Factory function to create ECM agent for MemoryAgentBench.

    This function is called by MemoryAgentBench's initialization code.
    """
    return ECMAgentWrapper(agent_config, dataset_config, load_agent_from)


if __name__ == "__main__":
    # Quick test
    agent_config = get_ecm_agent_config()
    dataset_config = get_ecm_dataset_config()

    agent = ECMAgentWrapper(agent_config, dataset_config)

    # Test memorization
    result = agent.send_message(
        "The capital of France is Paris. It has a population of 2.1 million.",
        memorizing=True,
        context_id=0
    )
    print(f"Memorize result: {result}")

    # Test query
    result = agent.send_message(
        "What is the capital of France?",
        memorizing=False,
        context_id=0
    )
    print(f"Query result: {result['output']}")
    print(f"ECM metrics: {result['ecm_metrics']}")
