"""
Memory Benchmark Agents.

Baseline agents for memory benchmarks:
- LongContextAgent: Full context accumulation (no memory management)
- RAGAgent: Top-k retrieval with keyword overlap
- Mem0Agent: Mem0 memory framework
- LettaAgent: Letta/MemGPT memory framework
- ECMAgent: Explicit Context Management (ours)
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from benchmarks.common.base_agent import BaseAgent


# =============================================================================
# Long Context Agent (Baseline)
# =============================================================================

class LongContextAgent(BaseAgent):
    """
    Long Context Agent - Appends all content to context window.

    This is the simplest baseline: just accumulate everything in the prompt.
    Context grows linearly with content. Simulates infinite context window.
    """

    def __init__(self, model: str = "gpt-4o-mini", max_tokens: int = 100000):
        super().__init__(model)
        self.max_tokens = max_tokens
        self.context_by_id: dict[int, list[str]] = {}

    def memorize(self, content: str, context_id: int = 0):
        """Append content to context buffer."""
        if context_id not in self.context_by_id:
            self.context_by_id[context_id] = []
        self.context_by_id[context_id].append(content)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using full accumulated context."""
        context_parts = self.context_by_id.get(context_id, [])
        full_context = "\n\n".join(context_parts)

        # Truncate if too long (simple truncation from start)
        if len(full_context) > self.max_tokens * 4:  # ~4 chars per token
            full_context = full_context[-(self.max_tokens * 4):]

        messages = [
            {
                "role": "system",
                "content": f"Answer the question based on the following context:\n\n{full_context}"
            },
            {"role": "user", "content": question}
        ]

        return self._call_llm(messages)

    def reset(self):
        self.context_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["context_size"] = sum(len(c) for chunks in self.context_by_id.values() for c in chunks)
        stats["num_chunks"] = sum(len(chunks) for chunks in self.context_by_id.values())
        return stats


# =============================================================================
# RAG Agent (Baseline)
# =============================================================================

class RAGAgent(BaseAgent):
    """
    RAG Agent - Uses simple keyword/TF-IDF style retrieval.

    Stores chunks and retrieves top-k most relevant based on keyword overlap.
    Simple but effective baseline for memory retrieval.
    """

    def __init__(self, model: str = "gpt-4o-mini", top_k: int = 5):
        super().__init__(model)
        self.top_k = top_k
        self.chunks_by_id: dict[int, list[str]] = {}

    def memorize(self, content: str, context_id: int = 0):
        """Store content chunk."""
        if context_id not in self.chunks_by_id:
            self.chunks_by_id[context_id] = []
        self.chunks_by_id[context_id].append(content)

    def _retrieve(self, query: str, context_id: int = 0) -> list[str]:
        """Retrieve top-k relevant chunks using keyword overlap."""
        chunks = self.chunks_by_id.get(context_id, [])
        if not chunks:
            return []

        # Simple keyword matching (TF-IDF style)
        query_words = set(query.lower().split())

        scored_chunks = []
        for chunk in chunks:
            chunk_words = set(chunk.lower().split())
            overlap = len(query_words & chunk_words)
            score = overlap / (len(query_words) + 1)
            scored_chunks.append((score, chunk))

        # Sort by score and take top-k
        scored_chunks.sort(reverse=True, key=lambda x: x[0])
        return [chunk for _, chunk in scored_chunks[:self.top_k]]

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using retrieved context."""
        retrieved = self._retrieve(question, context_id)
        context = "\n\n".join(retrieved)

        messages = [
            {
                "role": "system",
                "content": f"Answer the question based on the following retrieved context:\n\n{context}"
            },
            {"role": "user", "content": question}
        ]

        result = self._call_llm(messages)
        result["retrieved_chunks"] = len(retrieved)
        return result

    def reset(self):
        self.chunks_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["total_chunks"] = sum(len(chunks) for chunks in self.chunks_by_id.values())
        stats["top_k"] = self.top_k
        return stats


# =============================================================================
# Mem0 Agent (Baseline)
# =============================================================================

class Mem0Agent(BaseAgent):
    """
    Mem0 Agent - Uses Mem0 memory framework.

    Mem0 provides automatic memory extraction and semantic search.
    Falls back to simple memory if Mem0 is not installed.

    Install: pip install mem0ai
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)
        self.available = False
        self.memories_by_id: dict[int, list[str]] = {}

        try:
            from mem0 import Memory
            self.Memory = Memory
            self.m = Memory()
            self.available = True
        except ImportError:
            print("  [Mem0] Not installed. Run: pip install mem0ai")
            self.m = None

    def memorize(self, content: str, context_id: int = 0):
        """Add memory using Mem0."""
        user_id = f"context_{context_id}"

        if self.available and self.m:
            try:
                self.m.add(content, user_id=user_id)
            except Exception:
                # Fallback to simple storage
                if context_id not in self.memories_by_id:
                    self.memories_by_id[context_id] = []
                self.memories_by_id[context_id].append(content)
        else:
            if context_id not in self.memories_by_id:
                self.memories_by_id[context_id] = []
            self.memories_by_id[context_id].append(content)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using Mem0 memories."""
        user_id = f"context_{context_id}"

        # Retrieve memories
        if self.available and self.m:
            try:
                memories = self.m.search(question, user_id=user_id, limit=5)
                context = "\n".join([m.get("memory", "") for m in memories])
            except Exception:
                chunks = self.memories_by_id.get(context_id, [])
                context = "\n".join(chunks[-5:])
        else:
            chunks = self.memories_by_id.get(context_id, [])
            context = "\n".join(chunks[-5:])

        messages = [
            {
                "role": "system",
                "content": f"Answer based on these memories:\n\n{context}"
            },
            {"role": "user", "content": question}
        ]

        return self._call_llm(messages)

    def reset(self):
        if self.available and self.m:
            try:
                self.m.reset()
            except Exception:
                pass
        self.memories_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["mem0_available"] = self.available
        stats["total_memories"] = sum(len(m) for m in self.memories_by_id.values())
        return stats


# =============================================================================
# Letta Agent (Baseline)
# =============================================================================

class LettaAgent(BaseAgent):
    """
    Letta Agent - Uses Letta/MemGPT memory framework.

    Letta provides core memory + archival storage with automatic management.
    Uses simplified implementation (full Letta requires server setup).

    Install: pip install letta
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)
        self.available = False
        self.memories_by_id: dict[int, list[str]] = {}

        try:
            # Letta requires server setup, use simplified fallback
            self.available = False
            print("  [Letta] Using simplified memory (full Letta requires server setup)")
        except ImportError:
            print("  [Letta] Not installed. Run: pip install letta")

    def memorize(self, content: str, context_id: int = 0):
        """Add memory (Letta-style: recent window + archival)."""
        if context_id not in self.memories_by_id:
            self.memories_by_id[context_id] = []
        self.memories_by_id[context_id].append(content)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using Letta-style memory."""
        chunks = self.memories_by_id.get(context_id, [])

        # Letta-style: core memory (recent) + archival (older)
        recent = chunks[-3:] if len(chunks) > 3 else chunks
        context = "\n".join(recent)

        messages = [
            {
                "role": "system",
                "content": f"[Core Memory]\n{context}\n\nAnswer the question."
            },
            {"role": "user", "content": question}
        ]

        return self._call_llm(messages)

    def reset(self):
        self.memories_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["letta_available"] = self.available
        return stats


# =============================================================================
# ECM Agent (Ours)
# =============================================================================

class ECMAgent(BaseAgent):
    """
    ECM Agent - Explicit Context Management.

    Uses OpenAI tool calling for ctx_cli commands.
    The model calls the ctx_cli tool when it wants to save notes/insights.
    """

    SYSTEM_PROMPT = """You are a helpful assistant with access to a context management tool (ctx_cli).

Use ctx_cli to save important information:
- note -m "..." : Save facts, results, or decisions for later reference
- insight -m "..." : Save patterns or principles that might help with similar tasks

Only save what's genuinely useful. The tool helps you maintain memory across interactions."""

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)

        # Import ECM components
        from ctx_store import ContextStore
        from ctx_cli import CTX_CLI_TOOL, execute_command

        self.ContextStore = ContextStore
        self.store = ContextStore()
        self.ctx_cli_tool = CTX_CLI_TOOL
        self.execute_command = execute_command

    def _get_memory_summary(self) -> str:
        """Get current memory state summary."""
        branch = self.store.branches.get(self.store.current_branch)
        note_count = len(branch.notes) if branch else 0
        insight_count = len(self.store.insights)

        parts = [f"[Memory: {note_count} notes, {insight_count} insights]"]

        # Include insights if any
        insights = self.store.get_insights()
        if insights and "No insights" not in insights:
            parts.append(f"\nInsights:\n{insights}")

        # Include recent notes
        notes = self.store.get_all_notes()
        if notes and "No notes" not in notes:
            note_lines = notes.split("\n")[-10:]  # Last 10
            parts.append(f"\nRecent notes:\n" + "\n".join(note_lines))

        return "\n".join(parts)

    def _process_tool_calls(self, tool_calls) -> list[dict]:
        """Process tool calls and return results with captured commands."""
        import json
        results = []

        for tool_call in tool_calls:
            if tool_call.function.name == "ctx_cli":
                args = json.loads(tool_call.function.arguments)
                command = args["command"]
                result, _ = self.execute_command(self.store, command)
                results.append({
                    "tool_call_id": tool_call.id,
                    "command": command,  # Capture the command
                    "result": result
                })

        return results

    def memorize(self, content: str, context_id: int = 0):
        """
        Present content to the model with ctx_cli tool available.

        The model can use the tool to save important info.
        """
        # Ensure correct scope
        scope_name = f"context_{context_id}"
        if scope_name not in self.store.branches:
            self.store.checkout(scope_name, note=f"Starting context {context_id}", create=True)
        elif self.store.current_branch != scope_name:
            self.store.checkout(scope_name, note=f"Returning to context {context_id}", create=False)

        # Build messages
        system = self.SYSTEM_PROMPT + "\n\n" + self._get_memory_summary()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Process this information. Use ctx_cli to save anything important:\n\n{content[:1500]}"}
        ]

        # Call with tool
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=[self.ctx_cli_tool],
            temperature=self.temperature,
            max_tokens=400,
        )

        message = response.choices[0].message
        self.total_input_tokens += response.usage.prompt_tokens
        self.total_output_tokens += response.usage.completion_tokens

        # Process any tool calls
        if message.tool_calls:
            self._process_tool_calls(message.tool_calls)

    def query(self, question: str, context_id: int = 0, system_prompt: str = None) -> dict:
        """Answer question using ECM memory, with tool available.

        Args:
            question: The question/task to process
            context_id: Context ID for multi-context scenarios
            system_prompt: Optional custom system prompt (uses default if None)
        """
        import time
        from benchmarks.core.metrics import count_working_tokens, count_context_tokens

        # Ensure correct scope
        scope_name = f"context_{context_id}"
        if self.store.current_branch != scope_name and scope_name in self.store.branches:
            self.store.checkout(scope_name, note="Query", create=False)

        # Build messages with memory context
        # Use provided system prompt or fall back to default
        base_prompt = system_prompt if system_prompt else self.SYSTEM_PROMPT
        system = base_prompt + "\n\n" + self._get_memory_summary()

        # ECM design: Context accumulates WITHIN a scope
        # The scope IS the working context - cleanup happens via `goto main`
        messages = self.store.get_context(system)
        messages.append({"role": "user", "content": question})

        # Count working context at START (excludes system prompt)
        prompt_tokens_start = count_working_tokens(messages, self.model)
        context_at_start = count_context_tokens(messages, self.model)
        peak_prompt = prompt_tokens_start

        start_time = time.time()

        # Call with tool available
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=[self.ctx_cli_tool],
            temperature=self.temperature,
            max_tokens=500,
        )

        latency = time.time() - start_time

        message = response.choices[0].message
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Process tool calls if any
        tool_calls_captured = []
        if message.tool_calls:
            tool_calls_captured = self._process_tool_calls(message.tool_calls)

        # Add response to current scope's context
        # ECM: Messages accumulate within scope, cleanup via `goto main`
        from ctx_store import Message
        self.store.add_message(Message(role="assistant", content=message.content or ""))

        # Count working context at END (after adding assistant message)
        messages_end = self.store.get_context(system)
        prompt_tokens_end = count_working_tokens(messages_end, self.model)
        context_at_end = count_context_tokens(messages_end, self.model)
        peak_prompt = max(peak_prompt, prompt_tokens_end)

        return {
            "answer": message.content or "",
            # Legacy metrics (includes system prompt)
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "context_at_start": context_at_start,
            "context_at_end": context_at_end,
            # Working context metrics (excludes system prompt)
            "prompt_tokens_start": prompt_tokens_start,
            "prompt_tokens": prompt_tokens_end,
            "peak_prompt_tokens": peak_prompt,
            "completion_tokens": output_tokens,
            # Performance
            "latency": latency,
            "api_calls": 1,
            "tool_calls": tool_calls_captured,
            "ctx_cli_commands": [tc["command"] for tc in tool_calls_captured],
        }

    def reset(self):
        from ctx_store import ContextStore
        self.store = ContextStore()
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["total_scopes"] = len(self.store.branches)
        stats["total_notes"] = sum(
            len(b.notes) for b in self.store.branches.values()
        )
        stats["total_insights"] = len(self.store.insights)
        return stats


# =============================================================================
# Agent Registry
# =============================================================================

AVAILABLE_AGENTS = {
    "longcontext": {
        "name": "Long Context",
        "description": "Appends all content to context window (no memory management)",
        "class": LongContextAgent,
    },
    "rag": {
        "name": "RAG (top-5)",
        "description": "Retrieves top-5 relevant chunks using keyword overlap",
        "class": RAGAgent,
    },
    "ecm": {
        "name": "ECM (ours)",
        "description": "Explicit Context Management with notes + insights",
        "class": ECMAgent,
    },
    "mem0": {
        "name": "Mem0",
        "description": "Mem0 memory framework (requires: pip install mem0ai)",
        "class": Mem0Agent,
    },
    "letta": {
        "name": "Letta",
        "description": "Letta/MemGPT framework (requires: pip install letta)",
        "class": LettaAgent,
    },
}


# Export all
__all__ = [
    "BaseAgent",
    "LongContextAgent",
    "RAGAgent",
    "Mem0Agent",
    "LettaAgent",
    "ECMAgent",
    "AVAILABLE_AGENTS",
]
