#!/usr/bin/env python3
"""
OSWorld-Style Benchmark for ECM (Internal Refactor).

Uses ECMAgentWrapper components to enforce explicit memory management.
"""

import os
import sys
import json
import time
import re
import argparse
from typing import Literal, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.adapters.ecm_adapter import ECMAgentWrapper, ECMLogger
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

# =============================================================================
# Simulated OS
# =============================================================================

class SimulatedOS:
    """Simplified OS simulation."""
    def __init__(self):
        self.files = {
            "/home/user/notes.txt": "TODO: Review project\nCHECK: data.csv integrity\nBACKUP: app.py",
            "/home/user/projects/app.py": "def main():\n    print('Hello World')\n    # TODO: Add logic",
            "/home/user/data.csv": "id,name,value\n1,test,100\n2,prod,200",
            "/home/user/logs/error.log": "Error: Connection failed at 10:00\nError: Timeout at 10:05",
        }
        self.cwd = "/home/user"
        self.history = []

    def execute(self, command: str) -> str:
        self.history.append(command)
        parts = command.strip().split()
        if not parts:
            return "Error: empty command"
        
        cmd = parts[0]
        
        if cmd == "ls":
            # Handle flags like -la
            args = [p for p in parts[1:] if not p.startswith("-")]
            path = args[0] if args else self.cwd
            
            if not path.startswith("/"):
                path = os.path.normpath(os.path.join(self.cwd, path))
            
            # Simple prefix match
            files = [f for f in self.files if f.startswith(path)]
            # Get immediate children
            children = set()
            for f in files:
                rel = f[len(path):].lstrip("/")
                if "/" in rel:
                    children.add(rel.split("/")[0] + "/")
                elif rel:
                    children.add(rel)
            
            return "\n".join(sorted(children)) or "empty"

        elif cmd == "cp":
            if len(parts) < 3:
                return "Error: missing args"
            src = parts[1]
            dst = parts[2]
            if not src.startswith("/"): src = os.path.normpath(os.path.join(self.cwd, src))
            if not dst.startswith("/"): dst = os.path.normpath(os.path.join(self.cwd, dst))
            
            if src in self.files:
                self.files[dst] = self.files[src]
                return ""
            return f"Error: file not found {src}"

        elif cmd == "find":
            # Simple find . -name 'pattern'
            try:
                name_idx = parts.index("-name")
                pattern = parts[name_idx + 1].strip("'\"")
                start_path = parts[1] if parts[1] != "-name" else "."
                if start_path == ".": start_path = self.cwd
                
                matches = []
                for f in self.files:
                    if f.startswith(start_path) and os.path.basename(f) == pattern:
                        matches.append(f)
                return "\n".join(matches) or "no matches"
            except (ValueError, IndexError):
                return "Usage: find <path> -name <pattern>"

        elif cmd == "cat":
            if len(parts) < 2:
                return "Error: missing file"
            path = parts[1]
            if not path.startswith("/"):
                path = os.path.normpath(os.path.join(self.cwd, path))
            return self.files.get(path, f"Error: file not found: {path} (Available: {list(self.files.keys())})")

        elif cmd == "pwd":
            return self.cwd

        elif cmd == "cd":
            path = parts[1] if len(parts) > 1 else "/home/user"
            self.cwd = path
            return self.cwd

        elif cmd == "echo":
            if ">" in command:
                idx = command.index(">")
                text = command[:idx].replace("echo", "", 1).strip().strip('"')
                path = command[idx+1:].strip()
                if not path.startswith("/"):
                    path = os.path.normpath(os.path.join(self.cwd, path))
                self.files[path] = text
                return ""
            return " ".join(parts[1:])

        elif cmd == "grep":
            # Simplified grep
            pattern = parts[1].strip('"') 
            path = parts[-1]
            if not path.startswith("/"):
                path = os.path.normpath(os.path.join(self.cwd, path))
            
            content = self.files.get(path, "")
            matches = [l for l in content.split("\n") if pattern in l]
            return "\n".join(matches) or "no matches"

        return f"executed: {command}"

    def check_state(self, checks: list[dict]) -> tuple[int, int]:
        passed = 0
        for check in checks:
            if check["type"] == "file_exists":
                if check["path"] in self.files:
                    passed += 1
            elif check["type"] == "content_contains":
                content = self.files.get(check["path"], "")
                if check["text"] in content:
                    passed += 1
            elif check["type"] == "command_executed":
                pattern = check.get("pattern", "")
                if any(pattern in cmd for cmd in self.history):
                    passed += 1
        return passed, len(checks)

# =============================================================================
# Tasks
# =============================================================================

TASKS = [
    {
        "id": "explore_home",
        "description": "List files in home directory and read notes.txt to see what TO-DOs exist.",
        "checks": [{"type": "command_executed", "pattern": "cat"}], # Generic check
    },
    {
        "id": "backup_app",
        "description": "Based on the TODOs you found, create a backup of the application file app.py named app.py.bak.",
        "checks": [{"type": "file_exists", "path": "/home/user/projects/app.py.bak"}],
    },
    {
        "id": "verify_data",
        "description": "Check data.csv integrity as requested in the notes.",
        "checks": [{"type": "command_executed", "pattern": "cat"}],
    },
]

# =============================================================================
from tokens import TokenTracker

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of OSWorld benchmark."""
    approach: Literal["explicit"]
    model: str
    num_tasks: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Token metrics
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    
    # Context metrics
    peak_context: int = 0
    context_per_task: list = field(default_factory=list)

    # Task metrics
    tasks_completed: int = 0
    checks_passed: int = 0
    total_checks: int = 0
    api_calls: int = 0

    # Timing
    elapsed_seconds: float = 0.0

    # Details
    task_results: list = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        return (self.tasks_completed / self.num_tasks * 100) if self.num_tasks > 0 else 0


# =============================================================================
# OSWorld Agent (Explicit)
# =============================================================================

class OSWorldExplicitAgent(ECMAgentWrapper):
    """
    Extends ECMAgentWrapper to support multi-turn OSWorld environment.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.os_env = None

    def _run_tool_loop(self, messages: list[dict], max_rounds: int = 10) -> str:
        """Override to include Bash tool."""
        
        # Define Bash Tool
        BASH_TOOL = {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a bash command in the OS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to run (e.g. ls -la, cat file.txt)"}
                    },
                    "required": ["command"]
                }
            }
        }
        
        tools = [CTX_CLI_TOOL, BASH_TOOL]

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
            messages.append(assistant_message.model_dump())

            # Track tokens (approximate via tiktoken utility)
            # Usage is only available in response object
            if hasattr(self, 'current_result') and response.usage:
                self.current_result.total_prompt_tokens += response.usage.prompt_tokens
                self.current_result.total_completion_tokens += response.usage.completion_tokens
                self.current_result.api_calls += 1

            if not assistant_message.tool_calls:
                return assistant_message.content or ""

            for tool_call in assistant_message.tool_calls:
                if tool_call.function.name == "ctx_cli":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    result, event = execute_command(self.store, command)
                    
                    cmd_type = command.split()[0].upper() if command else "UNKNOWN"
                    self.logger.log(cmd_type, f"ctx_cli {command}")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
                    
                elif tool_call.function.name == "bash":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    
                    result = self.os_env.execute(command)
                    
                    self.logger.log("BASH", f"{command}")
                    print(f"Executed: {command}\nOutput: {result[:50]}...")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })

        return messages[-1].get("content", "")

    def run_task(self, task: dict, os_env: SimulatedOS, result_tracker: BenchmarkResult, max_turns: int = 10) -> dict:
        """Run a single task using explicit memory."""
        self.os_env = os_env
        self.current_result = result_tracker
        
        print(f"\nExample Task: {task['description']}")
        
        # Track context size
        tracker = TokenTracker(model=self.model)
        
        if self.store.current_project != "osworld_session":
            self.store.new_project("osworld_session")
            self.store.checkout("main", note="Starting OSWorld session", create=True)
            
        from prompts import SYSTEM_PROMPT_ECM_MEMORY
        
        system_prompt = SYSTEM_PROMPT_ECM_MEMORY + """
# CURRENT STATE
project: osworld_session
scope: main

# ENVIRONMENT
You are in a simulated Linux environment (SimulatedOS).
You have a `bash` tool to execute commands.

# EXPLICIT TOKEN USAGE RULES
1. **MEMORY**: Use `ctx_cli` for:
   - `note` / `notes`
   - `insight` / `insights`
   - `status`

2. **ACTION**: Use `bash` tool to execute commands.

3. **SEQUENCE**:
   - CHECK memory (`status`, `notes`)
   - EXECUTE action (`bash`)
   - SAVE if needed (`note`)

**CRITICAL**: You are working on a LONG HORIZON sequence of tasks.
Information found in Task N (like TODOs in a file) WILL be needed in Task N+1.
ALWAYS save important file contents or findings to `ctx_cli note` so you can retrieve them later.
If you read a file with instructions (like notes.txt), SAVE THOSE INSTRUCTIONS as a note immediately.

You are an autonomous agent. Manage your memory explicitly.
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task['description']}"}
        ]
        
        # Run tool loop
        final_response = self._run_tool_loop(messages, max_rounds=20)
        print(f"Agent Final: {final_response}")
        
        # Metrics
        passed, total = os_env.check_state(task.get("checks", []))
        
        # Update result tracker
        result_tracker.checks_passed += passed
        result_tracker.total_checks += total
        if passed == total:
            result_tracker.tasks_completed += 1
            
        context_size = tracker.count_messages(messages)
        result_tracker.context_per_task.append(context_size)
        result_tracker.peak_context = max(result_tracker.peak_context, context_size)
        
        result_tracker.task_results.append({
            "task_id": task["id"],
            "completed": passed == total,
            "checks": f"{passed}/{total}",
            "context_size": context_size
        })

        return {"passed": passed, "total": total}


# =============================================================================
# Main
# =============================================================================

def main():
    from benchmarks.adapters.ecm_adapter import get_ecm_agent_config, get_ecm_dataset_config
    
    # Config
    model_name = "gpt-4.1-mini"
    agent_config = get_ecm_agent_config(model=model_name)
    dataset_config = get_ecm_dataset_config()
    
    agent = OSWorldExplicitAgent(agent_config, dataset_config)
    os_env = SimulatedOS()
    
    # Initialize Result
    result = BenchmarkResult(approach="explicit", model=model_name, num_tasks=len(TASKS))
    start_time = time.time()
    
    print(f"🚀 Starting OSWorld Benchmark (Explicit ECM) - {len(TASKS)} tasks")
    
    for i, task in enumerate(TASKS):
        print(f"\n--- Task {i+1}/{len(TASKS)}: {task['id']} ---")
        agent.run_task(task, os_env, result)
        
    result.elapsed_seconds = time.time() - start_time
    
    # Report
    print("\n" + "="*50)
    print("BENCHMARK RESULTS")
    print("="*50)
    print(f"Approach:        {result.approach}")
    print(f"Model:           {result.model}")
    print(f"Tasks Completed: {result.tasks_completed}/{result.num_tasks} ({result.completion_rate:.1f}%)")
    print(f"Checks Passed:   {result.checks_passed}/{result.total_checks}")
    print(f"Time Elapsed:    {result.elapsed_seconds:.2f}s")
    print(f"Total API Calls: {result.api_calls}")
    print(f"Tokens Used:     {result.total_prompt_tokens + result.total_completion_tokens:,}")
    print(f"Peak Context:    {result.peak_context:,} tokens")
    print("-" * 50)
    for res in result.task_results:
        status = "✅ PASS" if res["completed"] else "❌ FAIL"
        print(f"{res['task_id']:<15} {status} (Ctx: {res['context_size']})")
    print("="*50)

if __name__ == "__main__":
    main()

