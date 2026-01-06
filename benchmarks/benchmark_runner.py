#!/usr/bin/env python3
"""
ECM Benchmark Runner

Unified benchmark runner that integrates with the metrics module
to evaluate ECM against linear baselines.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from openai import OpenAI

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from metrics import (
    ECMMetrics,
    MetricsCollector,
    TokenMetrics,
    NavigationMetrics,
    UtilityMetrics,
    KnowledgeMetrics,
    KnowledgeQuery,
    compare_runs,
)
from prompts import SYSTEM_PROMPT_ECM, SYSTEM_PROMPT_LINEAR
from tokens import count_context_tokens


# =============================================================================
# Tool Definitions
# =============================================================================

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute bash command in the repository.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The command to execute"}},
            "required": ["command"]
        }
    }
}

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the repository.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file"}},
            "required": ["path"]
        }
    }
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    }
}

LIST_FILES_TOOL = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": ".", "description": "Directory path"}}
        }
    }
}

TOOLS_BASE = [BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL]


# =============================================================================
# Tool Execution
# =============================================================================

def execute_tool(tool_name: str, args: dict, workdir: str) -> str:
    """Execute a tool and return the result."""
    try:
        if tool_name == "bash":
            result = subprocess.run(
                args["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=workdir
            )
            output = (result.stdout + result.stderr)[:4000]
            return output or "(no output)"

        elif tool_name == "read_file":
            path = os.path.join(workdir, args["path"])
            with open(path, "r") as f:
                return f.read()[:8000]

        elif tool_name == "write_file":
            path = os.path.join(workdir, args["path"])
            dirname = os.path.dirname(path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(path, "w") as f:
                f.write(args["content"])
            return f"Written {len(args['content'])} bytes to {args['path']}"

        elif tool_name == "list_files":
            path = os.path.join(workdir, args.get("path", "."))
            if os.path.exists(path):
                return "\n".join(sorted(os.listdir(path)))
            return "Directory not found"

        return f"Unknown tool: {tool_name}"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# Agent Runner
# =============================================================================

class BenchmarkRunner:
    """Runs benchmarks with integrated metrics collection."""

    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-4o-mini",
        workdir: str = ".",
        max_turns_per_task: int = 15,
        verbose: bool = True,
    ):
        self.client = client
        self.model = model
        self.workdir = workdir
        self.max_turns = max_turns_per_task
        self.verbose = verbose

    def log(self, msg: str, end: str = "\n", flush: bool = True):
        """Print if verbose mode is on."""
        if self.verbose:
            print(msg, end=end, flush=flush)

    def run_linear_agent(
        self,
        tasks: list[dict],
        run_id: str = "",
        benchmark: str = "custom",
    ) -> ECMMetrics:
        """Run linear (baseline) agent on tasks."""
        collector = MetricsCollector(model=self.model, agent_type="linear")
        collector.start_run(run_id or f"linear_{datetime.now().strftime('%H%M%S')}", benchmark)
        collector.set_total_tasks(len(tasks))

        messages = [{"role": "system", "content": SYSTEM_PROMPT_LINEAR}]

        for task_idx, task in enumerate(tasks):
            task_id = task.get("id", f"task_{task_idx}")
            problem = task.get("problem_statement", task.get("prompt", ""))

            self.log(f"\n[Task {task_idx + 1}/{len(tasks)}] {task_id}")

            # Add user message
            user_msg = f"TASK {task_idx + 1}: {problem}"
            messages.append({"role": "user", "content": user_msg})

            task_complete = False
            for turn in range(self.max_turns):
                if task_complete:
                    break

                self.log(f"  Turn {turn + 1}: ", end="")

                # API call
                t0 = time.time()
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=TOOLS_BASE,
                        temperature=0,
                        max_tokens=4000,
                    )
                except Exception as e:
                    self.log(f"API Error: {e}")
                    break

                latency = time.time() - t0
                msg = response.choices[0].message
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                # Record metrics
                collector.record_api_call(messages, output_tokens)

                self.log(f"in={input_tokens}, out={output_tokens}, lat={latency:.2f}s")

                # Add assistant message
                msg_dict = msg.model_dump()
                messages.append({k: v for k, v in msg_dict.items() if v is not None})

                # Handle tool calls
                if not msg.tool_calls:
                    task_complete = True
                    break

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        result = "Error: Invalid JSON in tool arguments"
                    else:
                        self.log(f"    [{name}] ", end="")
                        result = execute_tool(name, args, self.workdir)
                        self.log("done")

                    messages.append({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tc.id,
                    })

            collector.record_task_completed()

        collector.end_run()
        return collector.get_metrics()

    def run_ecm_agent(
        self,
        tasks: list[dict],
        run_id: str = "",
        benchmark: str = "custom",
    ) -> ECMMetrics:
        """Run ECM agent on tasks."""
        collector = MetricsCollector(model=self.model, agent_type="ecm")
        collector.start_run(run_id or f"ecm_{datetime.now().strftime('%H%M%S')}", benchmark)
        collector.set_total_tasks(len(tasks))

        store = ContextStore()
        tools = TOOLS_BASE + [CTX_CLI_TOOL]
        current_scope = "main"

        for task_idx, task in enumerate(tasks):
            task_id = task.get("id", f"task_{task_idx}")
            problem = task.get("problem_statement", task.get("prompt", ""))

            self.log(f"\n[Task {task_idx + 1}/{len(tasks)}] {task_id}")

            # Add user message
            user_msg = f"TASK {task_idx + 1}: {problem}"
            store.add_message(Message(role="user", content=user_msg))

            task_complete = False
            for turn in range(self.max_turns):
                if task_complete:
                    break

                self.log(f"  Turn {turn + 1}: ", end="")

                # Get context from current scope
                ctx = store.get_context(SYSTEM_PROMPT_ECM)

                # API call
                t0 = time.time()
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=ctx,
                        tools=tools,
                        temperature=0,
                        max_tokens=4000,
                    )
                except Exception as e:
                    self.log(f"API Error: {e}")
                    break

                latency = time.time() - t0
                msg = response.choices[0].message
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                # Record metrics
                collector.record_api_call(ctx, output_tokens)

                self.log(f"in={input_tokens}, out={output_tokens}, lat={latency:.2f}s")

                # Add assistant message
                tc_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in (msg.tool_calls or [])
                ]
                store.add_message(Message(
                    role="assistant",
                    content=msg.content or "",
                    tool_calls=tc_data if tc_data else None
                ))

                # Handle tool calls
                if not msg.tool_calls:
                    task_complete = True
                    break

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        result = "Error: Invalid JSON in tool arguments"
                    else:
                        if name == "ctx_cli":
                            cmd = args.get("command", "")
                            self.log(f"    [ctx_cli] {cmd[:60]}... ", end="")
                            result, event = execute_command(store, cmd)

                            # Track navigation
                            if cmd.startswith("scope "):
                                parts = cmd.split("-m")
                                scope_name = parts[0].replace("scope", "").strip()
                                note = parts[1].strip().strip('"\'') if len(parts) > 1 else ""
                                collector.record_scope_operation(current_scope, scope_name, "scope", note)
                                current_scope = scope_name

                            elif cmd.startswith("goto "):
                                parts = cmd.split("-m")
                                scope_name = parts[0].replace("goto", "").strip()
                                note = parts[1].strip().strip('"\'') if len(parts) > 1 else ""
                                collector.record_scope_operation(current_scope, scope_name, "goto", note)
                                current_scope = scope_name

                                # Task complete when returning to main
                                if scope_name == "main":
                                    task_complete = True

                            elif cmd.startswith("note "):
                                note_content = cmd.replace("note", "").replace("-m", "").strip().strip('"\'')
                                collector.record_note(note_content)

                            elif cmd.startswith("insight "):
                                insight_content = cmd.replace("insight", "").replace("-m", "").strip().strip('"\'')
                                collector.record_insight(insight_content)

                            elif cmd == "notes" or cmd.startswith("notes "):
                                scope = cmd.replace("notes", "").strip() or None
                                collector.record_notes_retrieval(scope)

                            elif cmd == "insights":
                                collector.record_insights_retrieval(len(store.branches))

                            self.log("done")
                        else:
                            self.log(f"    [{name}] ", end="")
                            result = execute_tool(name, args, self.workdir)
                            self.log("done")

                    store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc.id,
                    ))

            # Record scope sizes
            for scope_name, branch in store.branches.items():
                collector.metrics.navigation_metrics.record_scope_size(
                    scope_name, len(branch.messages)
                )

            collector.record_task_completed()

        collector.end_run()
        return collector.get_metrics()

    def run_comparison(
        self,
        tasks: list[dict],
        run_id: str = "",
        benchmark: str = "custom",
    ) -> dict:
        """Run both agents and return comparison."""
        self.log("=" * 60)
        self.log("Running LINEAR agent")
        self.log("=" * 60)
        linear_metrics = self.run_linear_agent(tasks, f"{run_id}_linear", benchmark)

        self.log("\n" + "=" * 60)
        self.log("Running ECM agent")
        self.log("=" * 60)
        ecm_metrics = self.run_ecm_agent(tasks, f"{run_id}_ecm", benchmark)

        comparison = compare_runs(ecm_metrics, linear_metrics)

        self.log("\n" + "=" * 60)
        self.log("COMPARISON RESULTS")
        self.log("=" * 60)
        self.log(f"Context Reduction: {comparison['context_reduction'] * 100:.1f}%")
        self.log(f"Speedup: {comparison['speedup'] * 100:.1f}%")
        self.log(f"Peak Context - ECM: {comparison['peak_context']['ecm']:,}, Linear: {comparison['peak_context']['linear']:,}")
        self.log(f"Total Tokens - ECM: {comparison['total_tokens']['ecm']:,}, Linear: {comparison['total_tokens']['linear']:,}")

        return {
            "linear": linear_metrics.to_dict(),
            "ecm": ecm_metrics.to_dict(),
            "comparison": comparison,
        }


# =============================================================================
# SWE-Bench-CL Integration
# =============================================================================

def load_swe_bench_cl(data_path: str, repo_filter: str = "django", max_tasks: int = 15) -> list[dict]:
    """Load tasks from SWE-Bench-CL dataset."""
    with open(data_path, "r") as f:
        data = json.load(f)

    # Find the matching sequence
    sequence = None
    for seq in data.get("sequences", []):
        if repo_filter.lower() in seq.get("repo", "").lower():
            sequence = seq
            break

    if not sequence:
        raise ValueError(f"No sequence found for repo filter: {repo_filter}")

    tasks = sequence.get("tasks", [])[:max_tasks]

    # Normalize task format
    normalized = []
    for task in tasks:
        normalized.append({
            "id": task.get("metadata", {}).get("instance_id", ""),
            "problem_statement": task.get("task", {}).get("problem_statement", ""),
            "metadata": task.get("metadata", {}),
        })

    return normalized


def setup_repo(repo: str, commit: str, workdir: str) -> str:
    """Clone and checkout a repository."""
    repo_dir = os.path.join(workdir, repo.replace("/", "_"))

    if not os.path.exists(repo_dir):
        subprocess.run(
            f"git clone --depth 1 https://github.com/{repo}.git {repo_dir}",
            shell=True,
            capture_output=True,
        )

    subprocess.run(
        f"git fetch --depth 1 origin {commit} && git checkout -f {commit}",
        shell=True,
        cwd=repo_dir,
        capture_output=True,
    )

    return repo_dir


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ECM Benchmark Runner")
    parser.add_argument(
        "--benchmark",
        choices=["swe-bench-cl", "custom"],
        default="swe-bench-cl",
        help="Benchmark to run",
    )
    parser.add_argument(
        "--approach",
        choices=["linear", "ecm", "both"],
        default="both",
        help="Which agent(s) to run",
    )
    parser.add_argument("--tasks", type=int, default=5, help="Number of tasks")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--data-path", default="benchmarks/data/swe-bench-cl.json")

    args = parser.parse_args()

    client = OpenAI()
    os.makedirs(args.output, exist_ok=True)

    if args.benchmark == "swe-bench-cl":
        tasks = load_swe_bench_cl(args.data_path, max_tasks=args.tasks)

        # For SWE-Bench, we need a repo
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get repo info from first task
            first_task = tasks[0]
            repo = first_task.get("metadata", {}).get("repo", "django/django")
            commit = first_task.get("metadata", {}).get("base_commit", "main")

            print(f"Setting up repo: {repo} @ {commit[:8]}")
            workdir = setup_repo(repo, commit, tmpdir)

            runner = BenchmarkRunner(
                client=client,
                model=args.model,
                workdir=workdir,
                verbose=args.verbose,
            )

            run_id = f"swebenchcl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if args.approach == "both":
                results = runner.run_comparison(tasks, run_id, "swe-bench-cl")
            elif args.approach == "ecm":
                metrics = runner.run_ecm_agent(tasks, run_id, "swe-bench-cl")
                results = {"ecm": metrics.to_dict()}
            else:
                metrics = runner.run_linear_agent(tasks, run_id, "swe-bench-cl")
                results = {"linear": metrics.to_dict()}

    else:
        # Custom benchmark - expects tasks as JSON
        print("Custom benchmark mode - provide tasks via stdin or file")
        return

    # Save results
    output_path = os.path.join(
        args.output,
        f"{args.benchmark}_{args.approach}_{datetime.now().strftime('%H%M%S')}.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
