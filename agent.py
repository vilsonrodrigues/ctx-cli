"""
Agent with Git-like Context Management.

This module implements an LLM agent that uses ctx_cli to manage its own context,
enabling long-running tasks without context window overflow.
"""

from __future__ import annotations

import json
import os
from typing import Callable

from openai import OpenAI

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are an AI assistant with Git-like context management capabilities.

You have access to ctx_cli, a tool for managing your working memory and episodic memory.
Use it proactively to keep your context clean and focused.

## Context Management Guidelines

1. **COMMIT frequently**: After completing any subtask, commit your reasoning.
   This clears working memory but preserves learning in episodic memory.

2. **CHECKOUT for new tasks**: When starting a distinct task, create a new branch.
   Always include a transition note explaining what you'll do.

3. **TAG milestones**: After user approval or reaching stable states, create a tag.
   Tags are immutable - they mark important points you can always reference.

4. **CHECK STATUS**: If unsure about your context state, use `status`.

5. **Use STASH for interruptions**: If the user changes topic mid-task, stash your work.

## Token Management

Your context has a limit. ctx_cli helps you stay under it:
- Working messages (current branch) = RAM
- Commits = Episodic memory (accessible via `log`)
- When you commit, working messages are cleared but summarized in the commit

## Best Practices

- Commit message should capture the KEY INSIGHT or DECISION, not just "did X"
- Good: "Identified root cause: SQL injection in user input validation"
- Bad: "Analyzed the code"

- Checkout notes should state the INTENTION for the new branch
- Good: "Going to implement input sanitization using parameterized queries"
- Bad: "Working on fix"

You are encouraged to use ctx_cli proactively. Don't wait for the context to overflow."""


# =============================================================================
# Agent Implementation
# =============================================================================

class ContextManagedAgent:
    """
    An LLM agent with Git-like context management.

    The agent uses ctx_cli to manage its own context, enabling long-running
    tasks without context window overflow.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        tools: list[dict] | None = None,
        tool_handlers: dict[str, Callable] | None = None,
        max_iterations: int = 50,
        token_warning_threshold: int = 50000,
    ):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        self.store = ContextStore()
        self.max_iterations = max_iterations
        self.token_warning_threshold = token_warning_threshold

        # Combine ctx_cli with user-provided tools
        self.tools = [CTX_CLI_TOOL]
        if tools:
            self.tools.extend(tools)

        # Tool handlers (ctx_cli is handled internally)
        self.tool_handlers = tool_handlers or {}

    def _handle_tool_call(self, tool_call) -> str:
        """Handle a tool call from the model."""
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if name == "ctx_cli":
            result, event = execute_command(self.store, args["command"])
            if event:
                print(f"  [EVENT] {event.type}: {event.payload}")
            return result

        # Handle other tools
        if name in self.tool_handlers:
            return self.tool_handlers[name](**args)

        return f"Error: Unknown tool '{name}'"

    def _check_token_usage(self) -> bool:
        """Check if we should warn about token usage."""
        estimate = self.store.get_token_estimate()
        if estimate > self.token_warning_threshold:
            print(f"  [WARNING] Estimated tokens: {estimate}. Consider committing.")
            return True
        return False

    def run(self, user_message: str) -> str:
        """
        Run the agent with a user message.

        The agent will execute tools and manage context until it produces
        a final response or hits the iteration limit.
        """
        # Add user message to store
        self.store.add_message(Message(role="user", content=user_message))

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")

            # Get current context
            context = self.store.get_context(SYSTEM_PROMPT)
            self._check_token_usage()

            # Call the model
            response = self.client.chat.completions.create(
                model=self.model,
                messages=context,
                tools=self.tools if self.tools else None,
                tool_choice="auto",
            )

            message = response.choices[0].message

            # Check if model wants to use tools
            if message.tool_calls:
                # Add assistant message with tool calls to store
                self.store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                    tool_calls=[tc.model_dump() for tc in message.tool_calls]
                ))

                # Process each tool call
                for tool_call in message.tool_calls:
                    print(f"  [TOOL] {tool_call.function.name}: {tool_call.function.arguments}")
                    result = self._handle_tool_call(tool_call)
                    print(f"  [RESULT] {result[:200]}..." if len(result) > 200 else f"  [RESULT] {result}")

                    # Add tool result to store
                    self.store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                    ))

            else:
                # No tool calls - this is the final response
                final_response = message.content or ""

                # Add final response to store
                self.store.add_message(Message(
                    role="assistant",
                    content=final_response,
                ))

                print(f"\n[FINAL RESPONSE]")
                return final_response

        return "Error: Max iterations reached"

    def get_events(self) -> list[dict]:
        """Get all events emitted by ctx_cli."""
        return [e.to_dict() for e in self.store.events]

    def save_state(self, path: str) -> None:
        """Save the context store to a file."""
        self.store.save(path)

    def load_state(self, path: str) -> None:
        """Load context store from a file."""
        self.store = ContextStore.load(path)


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example with a simple calculator tool
    def calculator(expression: str) -> str:
        try:
            result = eval(expression)  # Don't do this in production!
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    calculator_tool = {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }
    }

    agent = ContextManagedAgent(
        model="gpt-4o-mini",
        tools=[calculator_tool],
        tool_handlers={"calculator": calculator},
    )

    print("=" * 60)
    print("Context-Managed Agent Demo")
    print("=" * 60)

    # Simulate a multi-step conversation
    response = agent.run("Calculate 15 * 23 and then add 100 to the result")
    print(response)

    print("\n" + "=" * 60)
    print("Events Log:")
    for event in agent.get_events():
        print(f"  {event['type']}: {event['payload']}")
