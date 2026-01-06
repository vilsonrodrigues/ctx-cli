"""
ECM Adapter for MemoryAgentBench - Fully Explicit Version.

The model MUST explicitly call ctx_cli tools to:
- Save notes/insights during memorization
- Pull notes/insights during query answering
- Create scopes for analysis

This version uses tool calling, not auto-injection.
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
from ctx_cli import CTX_CLI_TOOL, execute_command
from metrics import MetricsCollector, ECMMetrics

# =============================================================================
# ECM Logger
# =============================================================================

class ECMLogger:
    """Logger for ECM operations."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.operations: list[dict] = []
        self.start_time = time.time()

    def _timestamp(self) -> str:
        elapsed = time.time() - self.start_time
        return f"[{elapsed:7.2f}s]"

    def log(self, level: str, message: str):
        """Log an operation."""
        entry = {"timestamp": time.time() - self.start_time, "level": level, "message": message}
        self.operations.append(entry)

        prefix = {
            "TOOL": "🔧",
            "SCOPE": "📁",
            "NOTE": "📝",
            "INSIGHT": "💡",
            "NOTES": "📥",
            "INSIGHTS": "📥",
            "STATUS": "📊",
            "QUERY": "❓",
            "RESPONSE": "💬",
            "MEMORIZE": "💾",
            "INFO": "ℹ️ ",
        }.get(level, "•")

        if self.verbose:
            print(f"{self._timestamp()} {prefix} {message}")

    def get_summary(self) -> dict:
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
        """Close logger (no-op for this implementation)."""
        pass


# =============================================================================
# ECM Agent - Fully Explicit
# =============================================================================

class ECMAgentWrapper:
    """
    ECM Agent with fully explicit tool calling.
    
    The model must call ctx_cli tools to access memory.
    No automatic injection of notes/insights.
    """

    def __init__(
        self,
        agent_config: dict,
        dataset_config: dict,
        load_agent_from: Optional[str] = None,
        verbose_logging: bool = True,
        log_file: Optional[str] = None,
    ):
        self.logger = ECMLogger(verbose=verbose_logging)
        self.logger.log("INFO", "Initializing ECM Agent (Fully Explicit)")

        # Configuration
        self.model = agent_config.get('model', 'gpt-4o-mini')
        self.temperature = agent_config.get('temperature', 0.0)
        self.max_tokens = dataset_config.get('generation_max_length', 4000)
        self.max_tool_rounds = agent_config.get('max_tool_rounds', 10)
        
        # Thread safety
        import threading
        self._lock = threading.Lock()

        # Initialize components
        self.store = ContextStore()
        self.client = OpenAI()
        self._init_tokenizer()

        # Metrics
        self.metrics_collector = MetricsCollector(model=self.model, agent_type="ecm")
        self.agent_start_time = time.time()
        self.current_context_id = -1
        self.memorized_chunks = 0

        self.logger.log("INFO", f"ECM Agent ready (model={self.model})")

    def _init_tokenizer(self):
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")

    def _run_tool_loop(self, messages: list[dict], max_rounds: int = 10) -> str:
        """
        Run the tool loop.
        Expects the model to output tool calls based on messages.
        Executes tools and feeds back results until model produces final answer or max rounds.
        """
        # Ensure we always define the tools
        tools = [CTX_CLI_TOOL]

        for round_num in range(max_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            assistant_message = response.choices[0].message
            # Append assistant message to history
            messages.append(assistant_message.model_dump())

            if not assistant_message.tool_calls:
                # No more tools, return content
                return assistant_message.content or ""

            # Execute tools
            for tool_call in assistant_message.tool_calls:
                if tool_call.function.name == "ctx_cli":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    
                    # Execute with lock
                    with self._lock:
                        result, event = execute_command(self.store, command)
                    
                    # Log
                    cmd_type = command.split()[0].upper() if command else "UNKNOWN"
                    self.logger.log(cmd_type, f"ctx_cli {command}")
                    
                    # Store metrics if event
                    if event:
                         self.metrics_collector.track_operation(event["type"], 0.0) # Duration negligible here

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
        
        return messages[-1].get("content", "")

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, disallowed_special=()))

    # =========================================================================
    # Main Interface
    # =========================================================================

    def send_message(
        self,
        message: str,
        memorizing: bool = False,
        query_id: Optional[int] = None,
        context_id: Optional[int] = None,
    ) -> Any:
        if memorizing:
            return self._memorize(message, context_id)
        else:
            return self._query(message, query_id, context_id)

    # =========================================================================
    # Memorization - Model decides what to save
    # =========================================================================

    def _memorize(self, content: str, context_id: Optional[int] = None) -> str:
        """
        Present content to model. Model must explicitly call note/insight commands.
        """
        # Switch context if needed
        if context_id is not None and context_id != self.current_context_id:
            self._switch_context(context_id)
            self.current_context_id = context_id

        self.logger.log("MEMORIZE", f"Processing content ({len(content)} chars)")

        # Build messages for model
        from prompts import SYSTEM_PROMPT_ECM_MEMORY
        
        system_prompt = SYSTEM_PROMPT_ECM_MEMORY + f"""

# CURRENT STATE
scope: {self.store.current_branch}
project: {self.store.current_project}

# TASK
Read the information below and use the ctx_cli tool to save important facts.
Use: note -m "fact" for specific facts
Use: insight -m "pattern" for patterns/rules
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Memorize this information:\n\n{content}"}
        ]

        # Run tool loop - model calls note/insight as needed
        self._run_tool_loop(messages, max_rounds=5)
        
        self.memorized_chunks += 1
        return "Memorized"

    # =========================================================================
    # Query - Model must explicitly pull notes/insights
    # =========================================================================

    def _query(
        self,
        query: str,
        query_id: Optional[int] = None,
        context_id: Optional[int] = None,
    ) -> dict:
        """
        Answer a query. Model must explicitly call notes/insights to retrieve memory.
        """
        memory_construction_time = time.time() - self.agent_start_time

        # Switch context if needed
        if context_id is not None and context_id != self.current_context_id:
            self._switch_context(context_id)
            self.current_context_id = context_id

        self.logger.log("QUERY", f"Query: {query[:50]}...")

        # Build messages - model must decide to check memory
        from prompts import SYSTEM_PROMPT_ECM_MEMORY
        
        system_prompt = SYSTEM_PROMPT_ECM_MEMORY + f"""

# CURRENT STATE
scope: {self.store.current_branch}
project: {self.store.current_project}

# TASK
Answer the user's question. 
IMPORTANT: You MUST first use ctx_cli to check your memory:
1. Use: status - to see what's available
2. Use: notes - to recall saved information
3. Use: insights - to recall patterns
Then provide your answer.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        # Run tool loop - model must call notes/insights explicitly
        start_time = time.time()
        final_response = self._run_tool_loop(messages, max_rounds=self.max_tool_rounds)
        query_time = time.time() - start_time

        self.logger.log("RESPONSE", f"Answer: {final_response[:60]}...")

        # Calculate tokens
        input_tokens = self._count_tokens(json.dumps(messages))
        output_tokens = self._count_tokens(final_response)

        self.agent_start_time = time.time()

        return {
            "output": final_response,
            "input_len": input_tokens,
            "output_len": output_tokens,
            "memory_construction_time": memory_construction_time,
            "query_time_len": query_time,
            "ecm_metrics": self.get_status(),
        }

    # =========================================================================
    # Tool Loop - Core of explicit ECM
    # =========================================================================

    def _run_tool_loop(self, messages: list[dict], max_rounds: int = 10) -> str:
        """
        Run conversation with tool calls until model stops calling tools.
        
        Returns the final text response from the model.
        """
        for round_num in range(max_rounds):
            # Call model
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[CTX_CLI_TOOL],
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            assistant_message = response.choices[0].message
            messages.append(assistant_message.model_dump())

            # Check if model wants to call tools
            if not assistant_message.tool_calls:
                # No more tool calls - return final response
                return assistant_message.content or ""

            # Process each tool call
            for tool_call in assistant_message.tool_calls:
                if tool_call.function.name == "ctx_cli":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    
                    # Execute the command
                    result, event = execute_command(self.store, command)
                    
                    # Log the operation
                    cmd_type = command.split()[0].upper() if command else "UNKNOWN"
                    self.logger.log(cmd_type, f"ctx_cli {command}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })

        # Max rounds reached
        return messages[-1].get("content", "") if messages else ""

    # =========================================================================
    # Context Management
    # =========================================================================

    def _switch_context(self, context_id: int):
        """Switch to a new context using new_project()."""
        if self.current_context_id >= 0:
            # New project preserves old scopes with @suffix
            project_name = f"context_{context_id}"
            self.store.new_project(project_name)
            self.logger.log("INFO", f"New project: {project_name}")
        
        # Create scope for this context
        scope_name = f"context_{context_id}"
        if scope_name not in self.store.branches:
            self.store.checkout(scope_name, f"Starting context {context_id}", create=True)
            self.logger.log("SCOPE", f"Created scope: {scope_name}")

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict:
        return {
            "current_scope": self.store.current_branch,
            "total_scopes": len(self.store.branches),
            "total_notes": sum(len(b.notes) for b in self.store.branches.values()),
            "total_insights": len(self.store.insights),
            "working_memory_size": len(self.store._get_current_branch().messages),
            "memorized_chunks": self.memorized_chunks,
        }

    def get_metrics(self) -> ECMMetrics:
        return self.metrics_collector.get_metrics()


# =============================================================================
# Factory
# =============================================================================

def get_ecm_agent_config(
    model: str = "gpt-4o-mini",
    chunk_size: int = 1000,
    use_insights: bool = True,
) -> dict:
    return {
        "agent_name": "ecm_agent",
        "model": model,
        "temperature": 0.0,
        "max_tool_rounds": 10,
        "agent_chunk_size": chunk_size,
        "use_insights": use_insights,
    }

def get_ecm_dataset_config(
    dataset: str = "custom",
    sub_dataset: str = "default",
    context_max_length: int = 64000,
) -> dict:
    return {
        "dataset": dataset,
        "sub_dataset": sub_dataset,
        "context_max_length": context_max_length,
        "generation_max_length": 4000,
    }

def create_ecm_agent_for_benchmark(
    agent_config: dict,
    dataset_config: dict,
    load_agent_from: Optional[str] = None,
) -> ECMAgentWrapper:
    return ECMAgentWrapper(agent_config, dataset_config, load_agent_from)


if __name__ == "__main__":
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
