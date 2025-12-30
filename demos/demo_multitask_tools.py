"""
Multitask Tools Demo: ctx_cli with Bash-like tools (Claude Code style).

This demo compares LINEAR vs BRANCH approaches for a real multitask scenario:
- Agent has access to: bash, read_file, write_file, list_files
- Task: Create a Python project, write code, tests, run them, fix issues

Shows how ctx_cli helps manage context when using multiple tools on multiple tasks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker

# =============================================================================
# Custom Tools (Claude Code style)
# =============================================================================

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": """Execute a bash command and return output.
Use for: running tests, installing packages, git commands, etc.
Example: bash(command="pytest test_calculator.py -v")""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }
}

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": """Read contents of a file.
Use for: examining existing code, checking configs, reviewing files.
Example: read_file(path="src/main.py")""",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["path"]
        }
    }
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": """Write content to a file (creates or overwrites).
Use for: creating new files, updating code, writing configs.
Example: write_file(path="src/main.py", content="def hello(): ...")""",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    }
}

LIST_FILES_TOOL = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": """List files in a directory.
Use for: exploring project structure, finding files.
Example: list_files(path="src/")""",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: current dir)",
                    "default": "."
                }
            },
            "required": []
        }
    }
}


def execute_tool(tool_name: str, args: dict, workdir: str) -> str:
    """Execute a custom tool and return result."""
    try:
        if tool_name == "bash":
            result = subprocess.run(
                args["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=workdir
            )
            output = result.stdout + result.stderr
            return output[:2000] if output else "(no output)"

        elif tool_name == "read_file":
            path = os.path.join(workdir, args["path"])
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()
                return content[:3000] if content else "(empty file)"
            return f"Error: File not found: {args['path']}"

        elif tool_name == "write_file":
            path = os.path.join(workdir, args["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
            with open(path, "w") as f:
                f.write(args["content"])
            return f"Written {len(args['content'])} bytes to {args['path']}"

        elif tool_name == "list_files":
            path = os.path.join(workdir, args.get("path", "."))
            if os.path.exists(path):
                files = os.listdir(path)
                return "\n".join(files) if files else "(empty directory)"
            return f"Error: Directory not found: {args.get('path', '.')}"

        return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# Task Definition
# =============================================================================

MULTITASK_PROMPT = """
I need you to create a small Python project with the following requirements:

1. Create a calculator module (calculator.py) with functions:
   - add(a, b)
   - subtract(a, b)
   - multiply(a, b)
   - divide(a, b) - should handle division by zero

2. Create tests (test_calculator.py) using pytest:
   - Test all four operations
   - Test edge cases (division by zero, negative numbers)

3. Run the tests and make sure they pass

4. Create a README.md documenting the module

Please complete all tasks. Use the tools available to you.
"""

SYSTEM_PROMPT_LINEAR = """You are a software developer with access to bash-like tools.

Available tools:
- bash: Execute shell commands
- read_file: Read file contents
- write_file: Create/update files
- list_files: List directory contents

Complete the user's request step by step."""

SYSTEM_PROMPT_BRANCH = """You are a software developer with access to bash-like tools and ctx_cli for context management.

Available tools:
- bash: Execute shell commands
- read_file: Read file contents
- write_file: Create/update files
- list_files: List directory contents
- ctx_cli: Context management

WORKFLOW with ctx_cli:
1. Create scope for each major subtask: scope <name> -m "what I'll do"
2. Take notes after completing each subtask: note -m "what I did"
3. Return to main when done: goto main -m "summary"

Example workflow for a multi-file task:
- scope calculator -m "Creating calculator module"
- [create calculator.py]
- note -m "Calculator: implemented add, subtract, multiply, divide"
- goto main -m "Calculator module complete"
- scope tests -m "Writing tests"
- [create tests]
- note -m "Tests: added pytest tests for all operations"
- goto main -m "Tests complete"

This keeps context focused and preserves your reasoning."""


# =============================================================================
# Linear Approach (No ctx_cli)
# =============================================================================

def run_linear_approach(client: OpenAI, tracker: TokenTracker) -> dict:
    """Run multitask with traditional linear conversation."""
    print("\n" + "=" * 70)
    print("APPROACH 1: LINEAR (No ctx_cli)")
    print("=" * 70)

    workdir = tempfile.mkdtemp(prefix="ctx_linear_")
    print(f"Working directory: {workdir}\n")

    tools = [BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_LINEAR},
        {"role": "user", "content": MULTITASK_PROMPT}
    ]

    token_history = []
    tool_calls_count = 0
    start_time = time.time()

    for round_num in range(30):  # Max rounds
        tokens = tracker.count_messages(messages)
        token_history.append(tokens)

        print(f"Round {round_num + 1}: {tokens} tokens, {len(messages)} messages")

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
        tools=tools,
        )

        message = response.choices[0].message

        if message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [tc.model_dump() for tc in message.tool_calls]
            })

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                result = execute_tool(tool_name, args, workdir)
                tool_calls_count += 1

                # Show tool usage
                if tool_name == "write_file":
                    print(f"  📝 write_file: {args.get('path', '?')}")
                elif tool_name == "bash":
                    cmd = args.get('command', '')[:40]
                    print(f"  💻 bash: {cmd}...")
                elif tool_name == "read_file":
                    print(f"  📖 read_file: {args.get('path', '?')}")
                else:
                    print(f"  📁 {tool_name}")

                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call.id
                })
        else:
            messages.append({
                "role": "assistant",
                "content": message.content or ""
            })

            # Check if task complete
            content_lower = (message.content or "").lower()
            if any(word in content_lower for word in ["complete", "finished", "done", "all tasks"]):
                print(f"\n✅ Task completed!")
                break

    elapsed = time.time() - start_time

    # Verify results
    files_created = os.listdir(workdir)

    return {
        "approach": "linear",
        "final_tokens": token_history[-1] if token_history else 0,
        "max_tokens": max(token_history) if token_history else 0,
        "token_history": token_history,
        "message_count": len(messages),
        "tool_calls": tool_calls_count,
        "files_created": files_created,
        "elapsed_time": elapsed,
        "workdir": workdir,
    }


# =============================================================================
# Branch Approach (With ctx_cli)
# =============================================================================

def run_branch_approach(client: OpenAI, tracker: TokenTracker) -> dict:
    """Run multitask with ctx_cli context management."""
    print("\n" + "=" * 70)
    print("APPROACH 2: BRANCH (With ctx_cli)")
    print("=" * 70)

    workdir = tempfile.mkdtemp(prefix="ctx_branch_")
    print(f"Working directory: {workdir}\n")

    store = ContextStore()
    tools = [CTX_CLI_TOOL, BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL]

    token_history = []
    tool_calls_count = 0
    ctx_commands = 0
    start_time = time.time()

    store.add_message(Message(role="user", content=MULTITASK_PROMPT))

    for round_num in range(40):  # More rounds for ctx_cli overhead
        context = store.get_context(SYSTEM_PROMPT_BRANCH)
        tokens = tracker.count_messages(context)
        token_history.append(tokens)

        print(f"Round {round_num + 1}: {tokens} tokens, branch={store.current_branch}")

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=context,
            tools=tools,
        )

        message = response.choices[0].message

        if message.tool_calls:
            store.add_message(Message(
                role="assistant",
                content=message.content or "",
                tool_calls=[tc.model_dump() for tc in message.tool_calls]
            ))

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if tool_name == "ctx_cli":
                    result, _ = execute_command(store, args["command"])
                    ctx_commands += 1
                    cmd = args["command"]
                    if "commit" in cmd:
                        print(f"  💾 ctx: {cmd[:50]}...")
                    elif "checkout" in cmd:
                        print(f"  🌿 ctx: {cmd[:50]}...")
                    elif "merge" in cmd:
                        print(f"  🔗 ctx: {cmd}")
                    else:
                        print(f"  📋 ctx: {cmd[:40]}")
                else:
                    result = execute_tool(tool_name, args, workdir)
                    tool_calls_count += 1

                    if tool_name == "write_file":
                        print(f"  📝 write_file: {args.get('path', '?')}")
                    elif tool_name == "bash":
                        cmd = args.get('command', '')[:40]
                        print(f"  💻 bash: {cmd}...")
                    elif tool_name == "read_file":
                        print(f"  📖 read_file: {args.get('path', '?')}")
                    else:
                        print(f"  📁 {tool_name}")

                store.add_message(Message(
                    role="tool",
                    content=result,
                    tool_call_id=tool_call.id
                ))
        else:
            store.add_message(Message(
                role="assistant",
                content=message.content or ""
            ))

            # Check if task complete
            content_lower = (message.content or "").lower()
            if any(word in content_lower for word in ["complete", "finished", "done", "all tasks"]):
                print(f"\n✅ Task completed!")
                break

    elapsed = time.time() - start_time

    # Verify results
    files_created = os.listdir(workdir)
    total_commits = sum(len(b.commits) for b in store.branches.values())

    return {
        "approach": "branch",
        "final_tokens": token_history[-1] if token_history else 0,
        "max_tokens": max(token_history) if token_history else 0,
        "token_history": token_history,
        "message_count": sum(len(b.messages) for b in store.branches.values()),
        "tool_calls": tool_calls_count,
        "ctx_commands": ctx_commands,
        "commits": total_commits,
        "branches": len(store.branches),
        "files_created": files_created,
        "elapsed_time": elapsed,
        "workdir": workdir,
        "store": store,
    }


# =============================================================================
# Comparison
# =============================================================================

def run_comparison():
    """Run both approaches and compare."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    tracker = TokenTracker(model="gpt-4.1-mini")

    print("=" * 70)
    print("MULTITASK TOOLS COMPARISON")
    print("=" * 70)
    print("\nTask: Create Python calculator with tests, run tests, add docs")
    print("Tools: bash, read_file, write_file, list_files (+ctx_cli for branch)")
    print("\nRunning both approaches...\n")

    # Run both
    linear = run_linear_approach(client, tracker)
    branch = run_branch_approach(client, tracker)

    # ==========================================================================
    # Results
    # ==========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    # Token comparison
    print("\n📊 Token Usage:")
    print(f"  {'Metric':<25} {'Linear':>12} {'Branch':>12} {'Diff':>12}")
    print(f"  {'-' * 25} {'-' * 12} {'-' * 12} {'-' * 12}")

    linear_max = linear["max_tokens"]
    branch_max = branch["max_tokens"]
    diff_max = ((linear_max - branch_max) / linear_max * 100) if linear_max > 0 else 0

    linear_final = linear["final_tokens"]
    branch_final = branch["final_tokens"]
    diff_final = ((linear_final - branch_final) / linear_final * 100) if linear_final > 0 else 0

    print(f"  {'Peak tokens':.<25} {linear_max:>12,} {branch_max:>12,} {diff_max:>+11.1f}%")
    print(f"  {'Final tokens':.<25} {linear_final:>12,} {branch_final:>12,} {diff_final:>+11.1f}%")

    # Tool usage
    print("\n🔧 Tool Usage:")
    print(f"  {'Metric':<25} {'Linear':>12} {'Branch':>12}")
    print(f"  {'-' * 25} {'-' * 12} {'-' * 12}")
    print(f"  {'Tool calls (bash/file)':.<25} {linear['tool_calls']:>12} {branch['tool_calls']:>12}")
    print(f"  {'ctx_cli commands':.<25} {'N/A':>12} {branch.get('ctx_commands', 0):>12}")
    print(f"  {'Total messages':.<25} {linear['message_count']:>12} {branch['message_count']:>12}")

    # Context management
    print("\n📋 Context Management (Branch approach):")
    print(f"  Commits made: {branch.get('commits', 0)}")
    print(f"  Branches used: {branch.get('branches', 1)}")

    # Files created
    print("\n📁 Files Created:")
    print(f"  Linear: {', '.join(linear['files_created']) or '(none)'}")
    print(f"  Branch: {', '.join(branch['files_created']) or '(none)'}")

    # Time
    print("\n⏱️  Execution Time:")
    print(f"  Linear: {linear['elapsed_time']:.1f}s")
    print(f"  Branch: {branch['elapsed_time']:.1f}s")

    # Token growth curve
    print("\n📈 Token Growth (sampled):")
    linear_hist = linear["token_history"]
    branch_hist = branch["token_history"]
    max_len = max(len(linear_hist), len(branch_hist))
    sample_points = [0, max_len // 4, max_len // 2, 3 * max_len // 4, max_len - 1]
    sample_points = [p for p in sample_points if p < max_len]

    print(f"  {'Round':<8} {'Linear':>10} {'Branch':>10}")
    for i in sample_points:
        l = linear_hist[i] if i < len(linear_hist) else linear_hist[-1]
        b = branch_hist[i] if i < len(branch_hist) else branch_hist[-1]
        print(f"  {i + 1:<8} {l:>10,} {b:>10,}")

    # Insights
    print("\n💡 Key Insights:")
    if diff_final > 0:
        print(f"  ✓ Branch approach saved {diff_final:.1f}% tokens at completion")
    else:
        print(f"  → Branch used {-diff_final:.1f}% more tokens (ctx_cli overhead)")

    if branch.get("commits", 0) > 0:
        print(f"  ✓ {branch['commits']} commits preserved reasoning across subtasks")

    if branch.get("branches", 1) > 1:
        print(f"  ✓ {branch['branches']} branches isolated different concerns")

    print("\n📝 Summary:")
    print("  Linear: Simple, but context grows with every tool call")
    print("  Branch: ctx_cli overhead, but flattens growth for long tasks")
    print("  Best for: Multi-file projects, iterative development, debugging")

    # Cleanup note
    print(f"\n🗑️  Temp directories (can be inspected):")
    print(f"  Linear: {linear['workdir']}")
    print(f"  Branch: {branch['workdir']}")


if __name__ == "__main__":
    run_comparison()
