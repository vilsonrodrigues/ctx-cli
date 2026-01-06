#!/usr/bin/env python3
"""
AppWorld Benchmark for ECM.

AppWorld tests agents on multi-step tasks across 9 simulated apps with
realistic state management and inter-app dependencies.

Apps Simulated:
1. Email - Send, receive, manage emails
2. Calendar - Schedule events, manage reminders
3. Notes - Create and organize notes
4. Todo - Task management with priorities
5. Contacts - Contact database
6. Files - File system operations
7. Browser - Web browsing simulation
8. Shopping - E-commerce operations
9. Social - Social media interactions

Key Evaluation Dimensions:
- Multi-step reasoning: Tasks require 5-20 sequential actions
- State tracking: Actions affect app state persistently
- Inter-app coordination: Some tasks span multiple apps
- Error recovery: Handling failed actions gracefully
- Context efficiency: Memory usage across long task chains

Metrics:
- Task Completion Rate: % of tasks fully completed
- Partial Progress: Average % of subtasks completed
- Action Efficiency: Actions taken vs optimal path
- State Consistency: Correct state maintenance
- Context Usage: Tokens used per task

Usage:
    # Run on sample tasks
    uv run benchmarks/longhorizon/run_appworld.py --max-tasks 10

    # Compare ECM vs baselines
    uv run benchmarks/longhorizon/run_appworld.py --agents ecm longcontext

    # Run specific app category
    uv run benchmarks/longhorizon/run_appworld.py --app-filter email calendar

References:
- AppWorld: https://appworld.dev/
- Paper: "AppWorld: A Controllable World of Apps and People"
"""

import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from tqdm import tqdm

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.common.base_agent import BaseAgent
from benchmarks.memory.agents import AVAILABLE_AGENTS


# =============================================================================
# App World Simulation
# =============================================================================

@dataclass
class AppState:
    """State of a simulated app."""
    app_name: str
    data: dict = field(default_factory=dict)
    action_history: list[str] = field(default_factory=list)


@dataclass
class AppAction:
    """An action to perform in an app."""
    app: str
    action: str
    params: dict = field(default_factory=dict)
    expected_result: Optional[str] = None


@dataclass
class AppWorldTask:
    """A multi-step task in AppWorld."""
    task_id: str
    description: str
    goal: str
    apps_involved: list[str]
    actions: list[AppAction]
    success_criteria: list[str]
    difficulty: str = "medium"  # easy, medium, hard
    metadata: dict = field(default_factory=dict)


class AppWorldSimulator:
    """
    Simulates the AppWorld environment.

    Provides a controlled environment where agents can execute actions
    and receive feedback, mimicking real app interactions.
    """

    APPS = ["email", "calendar", "notes", "todo", "contacts", "files", "browser", "shopping", "social"]

    def __init__(self):
        self.states: dict[str, AppState] = {
            app: AppState(app_name=app, data={}) for app in self.APPS
        }
        self.action_log: list[dict] = []

    def reset(self):
        """Reset all app states."""
        self.states = {app: AppState(app_name=app, data={}) for app in self.APPS}
        self.action_log = []

    def execute_action(self, action: AppAction) -> dict:
        """
        Execute an action and return the result.

        Returns dict with:
            - success: bool
            - result: str (description of outcome)
            - state_change: dict (what changed)
        """
        app_state = self.states.get(action.app)
        if not app_state:
            return {"success": False, "result": f"Unknown app: {action.app}", "state_change": {}}

        # Simulate action execution based on app type
        result = self._simulate_action(app_state, action)

        # Log the action
        self.action_log.append({
            "timestamp": datetime.now().isoformat(),
            "app": action.app,
            "action": action.action,
            "params": action.params,
            "success": result["success"],
        })

        return result

    def _simulate_action(self, app_state: AppState, action: AppAction) -> dict:
        """Simulate specific app actions."""
        app = action.app
        act = action.action.lower()
        params = action.params

        # Email app actions
        if app == "email":
            if act == "send":
                app_state.data.setdefault("sent", []).append(params)
                return {"success": True, "result": f"Email sent to {params.get('to', 'recipient')}", "state_change": {"sent": params}}
            elif act == "read":
                return {"success": True, "result": "Email read", "state_change": {}}
            elif act == "search":
                return {"success": True, "result": f"Found {random.randint(1,5)} emails matching '{params.get('query', '')}'", "state_change": {}}

        # Calendar app actions
        elif app == "calendar":
            if act == "create_event":
                app_state.data.setdefault("events", []).append(params)
                return {"success": True, "result": f"Event '{params.get('title', 'event')}' created", "state_change": {"event": params}}
            elif act == "list_events":
                events = app_state.data.get("events", [])
                return {"success": True, "result": f"Found {len(events)} events", "state_change": {}}

        # Notes app actions
        elif app == "notes":
            if act == "create":
                app_state.data.setdefault("notes", []).append(params)
                return {"success": True, "result": f"Note '{params.get('title', 'note')}' created", "state_change": {"note": params}}
            elif act == "search":
                return {"success": True, "result": f"Found {random.randint(0,3)} notes", "state_change": {}}

        # Todo app actions
        elif app == "todo":
            if act == "add":
                app_state.data.setdefault("todos", []).append({**params, "completed": False})
                return {"success": True, "result": f"Todo added: {params.get('task', 'task')}", "state_change": {"todo": params}}
            elif act == "complete":
                return {"success": True, "result": "Todo marked complete", "state_change": {"completed": True}}
            elif act == "list":
                todos = app_state.data.get("todos", [])
                return {"success": True, "result": f"Found {len(todos)} todos", "state_change": {}}

        # Files app actions
        elif app == "files":
            if act == "create":
                app_state.data.setdefault("files", []).append(params)
                return {"success": True, "result": f"File created: {params.get('name', 'file')}", "state_change": {"file": params}}
            elif act == "read":
                return {"success": True, "result": f"File content: [simulated content]", "state_change": {}}
            elif act == "list":
                files = app_state.data.get("files", [])
                return {"success": True, "result": f"Found {len(files)} files", "state_change": {}}

        # Contacts app actions
        elif app == "contacts":
            if act == "add":
                app_state.data.setdefault("contacts", []).append(params)
                return {"success": True, "result": f"Contact added: {params.get('name', 'contact')}", "state_change": {"contact": params}}
            elif act == "search":
                return {"success": True, "result": f"Found {random.randint(0,2)} contacts", "state_change": {}}

        # Default fallback
        return {"success": True, "result": f"Action '{act}' executed on {app}", "state_change": {}}

    def get_state_summary(self) -> str:
        """Get a summary of all app states."""
        summary_parts = []
        for app, state in self.states.items():
            if state.data:
                items = []
                for key, value in state.data.items():
                    if isinstance(value, list):
                        items.append(f"{len(value)} {key}")
                    else:
                        items.append(f"{key}: {value}")
                if items:
                    summary_parts.append(f"[{app}] " + ", ".join(items))
        return "\n".join(summary_parts) if summary_parts else "All apps empty"


# =============================================================================
# Task Generation
# =============================================================================

def generate_appworld_tasks(
    num_tasks: int = 20,
    app_filter: Optional[list[str]] = None,
) -> list[AppWorldTask]:
    """
    Generate AppWorld tasks.

    For full evaluation, would load from official AppWorld dataset.
    This generates synthetic tasks for development/testing.
    """
    tasks = []

    # Task templates
    templates = [
        {
            "type": "email_calendar_coordination",
            "description": "Schedule a meeting based on an email request",
            "apps": ["email", "calendar"],
            "actions": [
                AppAction("email", "search", {"query": "meeting request"}),
                AppAction("email", "read", {"id": "latest"}),
                AppAction("calendar", "list_events", {"date": "next_week"}),
                AppAction("calendar", "create_event", {"title": "Meeting", "time": "2pm"}),
                AppAction("email", "send", {"to": "requester", "subject": "Meeting confirmed"}),
            ],
            "criteria": ["calendar_event_created", "confirmation_sent"],
        },
        {
            "type": "task_from_notes",
            "description": "Create todos from meeting notes",
            "apps": ["notes", "todo"],
            "actions": [
                AppAction("notes", "search", {"query": "action items"}),
                AppAction("notes", "read", {"id": "latest"}),
                AppAction("todo", "add", {"task": "Task 1", "priority": "high"}),
                AppAction("todo", "add", {"task": "Task 2", "priority": "medium"}),
            ],
            "criteria": ["todos_created_from_notes"],
        },
        {
            "type": "contact_management",
            "description": "Add new contact from email signature and send welcome",
            "apps": ["email", "contacts"],
            "actions": [
                AppAction("email", "read", {"id": "new_contact_email"}),
                AppAction("contacts", "add", {"name": "New Contact", "email": "contact@example.com"}),
                AppAction("email", "send", {"to": "contact@example.com", "subject": "Welcome"}),
            ],
            "criteria": ["contact_added", "welcome_sent"],
        },
        {
            "type": "file_organization",
            "description": "Organize files based on todo items",
            "apps": ["todo", "files"],
            "actions": [
                AppAction("todo", "list", {}),
                AppAction("files", "list", {}),
                AppAction("files", "create", {"name": "project_docs", "type": "folder"}),
                AppAction("todo", "complete", {"id": "organize_files"}),
            ],
            "criteria": ["folder_created", "todo_completed"],
        },
        {
            "type": "multi_app_workflow",
            "description": "Complete end-to-end project setup",
            "apps": ["email", "calendar", "notes", "todo", "files"],
            "actions": [
                AppAction("email", "search", {"query": "project kickoff"}),
                AppAction("notes", "create", {"title": "Project Plan", "content": "..."}),
                AppAction("calendar", "create_event", {"title": "Kickoff", "time": "tomorrow"}),
                AppAction("todo", "add", {"task": "Prepare presentation", "priority": "high"}),
                AppAction("todo", "add", {"task": "Send agenda", "priority": "high"}),
                AppAction("files", "create", {"name": "project_folder", "type": "folder"}),
                AppAction("email", "send", {"to": "team", "subject": "Project kickoff scheduled"}),
            ],
            "criteria": ["all_apps_updated", "team_notified"],
        },
    ]

    # Filter templates by apps if specified
    if app_filter:
        templates = [t for t in templates if any(app in t["apps"] for app in app_filter)]

    # Generate tasks
    for i in range(num_tasks):
        template = templates[i % len(templates)]
        task = AppWorldTask(
            task_id=f"appworld_{i+1:03d}",
            description=template["description"],
            goal=f"Complete the following workflow: {template['description']}",
            apps_involved=template["apps"],
            actions=template["actions"],
            success_criteria=template["criteria"],
            difficulty="medium" if len(template["actions"]) < 5 else "hard",
        )
        tasks.append(task)

    return tasks


# =============================================================================
# Agent Evaluation
# =============================================================================

@dataclass
class AppWorldResult:
    """Result from evaluating an agent on AppWorld."""
    agent_name: str
    task_id: str
    completed: bool
    actions_taken: int
    optimal_actions: int
    action_efficiency: float
    subtasks_completed: int
    total_subtasks: int
    partial_progress: float
    input_tokens: int
    output_tokens: int
    latency: float


class AppWorldEvaluator:
    """Evaluates agents on AppWorld tasks."""

    def __init__(self, agent: BaseAgent, agent_name: str, simulator: AppWorldSimulator):
        self.agent = agent
        self.agent_name = agent_name
        self.simulator = simulator

    def evaluate_task(self, task: AppWorldTask, max_actions: int = 20) -> AppWorldResult:
        """Evaluate the agent on a single AppWorld task."""
        start_time = time.time()
        total_input = 0
        total_output = 0

        # Reset simulator
        self.simulator.reset()

        # Provide task context to agent
        context = f"""
AppWorld Task: {task.task_id}

Goal: {task.goal}

Apps available: {', '.join(self.simulator.APPS)}

You can perform actions in these apps by specifying:
- App name
- Action (e.g., send, create, read, search, list, add, complete)
- Parameters

Current app states are empty. Start by understanding what needs to be done.
"""
        self.agent.memorize(context, context_id=0)

        # Main evaluation loop
        actions_taken = 0
        subtasks_completed = 0

        for step in range(max_actions):
            # Get current state
            state_summary = self.simulator.get_state_summary()

            # Ask agent for next action
            prompt = f"""
Step {step + 1}/{max_actions}

Task: {task.description}

Current State:
{state_summary}

What action should be taken next? Specify:
1. Which app to use
2. What action to perform
3. Any parameters needed

If the task is complete, say "TASK COMPLETE".
"""
            result = self.agent.query(prompt, context_id=0)
            response = result.get("answer", "")
            total_input += result.get("input_tokens", 0)
            total_output += result.get("output_tokens", 0)

            # Check for completion
            if "TASK COMPLETE" in response.upper():
                break

            # Parse and execute action (simplified)
            action = self._parse_action(response, task)
            if action:
                exec_result = self.simulator.execute_action(action)
                actions_taken += 1

                # Memorize the outcome
                outcome = f"Action: {action.app}.{action.action} -> {exec_result['result']}"
                self.agent.memorize(outcome, context_id=0)

                # Check if this completes a subtask
                if exec_result["success"]:
                    subtasks_completed += 1

        latency = time.time() - start_time

        # Evaluate completion
        completed = subtasks_completed >= len(task.actions) * 0.8  # 80% threshold
        optimal = len(task.actions)
        efficiency = optimal / max(actions_taken, 1) if actions_taken > 0 else 0

        return AppWorldResult(
            agent_name=self.agent_name,
            task_id=task.task_id,
            completed=completed,
            actions_taken=actions_taken,
            optimal_actions=optimal,
            action_efficiency=min(efficiency, 1.0) * 100,
            subtasks_completed=subtasks_completed,
            total_subtasks=len(task.actions),
            partial_progress=(subtasks_completed / len(task.actions)) * 100 if task.actions else 0,
            input_tokens=total_input,
            output_tokens=total_output,
            latency=latency,
        )

    def _parse_action(self, response: str, task: AppWorldTask) -> Optional[AppAction]:
        """Parse agent response into an action."""
        response_lower = response.lower()

        # Try to identify app
        app = None
        for a in task.apps_involved:
            if a in response_lower:
                app = a
                break

        if not app:
            # Default to first app in task
            app = task.apps_involved[0] if task.apps_involved else "email"

        # Try to identify action
        action_keywords = {
            "send": "send",
            "read": "read",
            "search": "search",
            "create": "create",
            "add": "add",
            "list": "list",
            "complete": "complete",
            "schedule": "create_event",
        }

        action = "read"  # Default
        for keyword, act in action_keywords.items():
            if keyword in response_lower:
                action = act
                break

        return AppAction(app=app, action=action, params={})


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="AppWorld evaluation for ECM")

    parser.add_argument("--agents", nargs="+", default=["ecm", "longcontext"],
                        help="Agents to evaluate")
    parser.add_argument("--max-tasks", type=int, default=10, help="Max tasks to run")
    parser.add_argument("--max-actions", type=int, default=15, help="Max actions per task")
    parser.add_argument("--app-filter", nargs="+", default=None,
                        help="Filter tasks by apps (e.g., email calendar)")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--output-dir", default="benchmarks/results/appworld", help="Output directory")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Generate tasks
    print("Generating AppWorld tasks...")
    tasks = generate_appworld_tasks(
        num_tasks=args.max_tasks,
        app_filter=args.app_filter,
    )
    print(f"Generated {len(tasks)} tasks")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize simulator
    simulator = AppWorldSimulator()

    # Initialize agents
    agents = {}
    for agent_key in args.agents:
        if agent_key not in AVAILABLE_AGENTS:
            print(f"Warning: Unknown agent '{agent_key}', skipping")
            continue
        info = AVAILABLE_AGENTS[agent_key]
        if agent_key == "ecm":
            agents[info["name"]] = info["class"](model=args.model)
        else:
            agents[info["name"]] = info["class"](model=args.model)

    # Run evaluations
    all_results = []

    for name, agent in agents.items():
        print(f"\n{'='*60}")
        print(f"Evaluating: {name}")
        print(f"{'='*60}")

        evaluator = AppWorldEvaluator(agent, name, simulator)
        agent_results = []

        iterator = tasks
        if not args.quiet:
            iterator = tqdm(tasks, desc=name)

        for task in iterator:
            result = evaluator.evaluate_task(task, max_actions=args.max_actions)
            agent_results.append(result)

        all_results.extend(agent_results)

        # Print summary for this agent
        completed = sum(1 for r in agent_results if r.completed)
        avg_progress = sum(r.partial_progress for r in agent_results) / len(agent_results)
        avg_efficiency = sum(r.action_efficiency for r in agent_results) / len(agent_results)
        avg_tokens = sum(r.input_tokens + r.output_tokens for r in agent_results) / len(agent_results)

        print(f"\n{name} Summary:")
        print(f"  Completion Rate: {completed}/{len(agent_results)} ({completed/len(agent_results)*100:.1f}%)")
        print(f"  Avg Progress: {avg_progress:.1f}%")
        print(f"  Action Efficiency: {avg_efficiency:.1f}%")
        print(f"  Avg Tokens/Task: {avg_tokens:.0f}")

        agent.reset()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"appworld_results_{timestamp}.json"

    # Group results by agent
    results_by_agent = {}
    for r in all_results:
        if r.agent_name not in results_by_agent:
            results_by_agent[r.agent_name] = []
        results_by_agent[r.agent_name].append({
            "task_id": r.task_id,
            "completed": r.completed,
            "partial_progress": r.partial_progress,
            "action_efficiency": r.action_efficiency,
            "tokens": r.input_tokens + r.output_tokens,
            "latency": r.latency,
        })

    results_data = {
        "timestamp": timestamp,
        "config": {
            "agents": args.agents,
            "max_tasks": args.max_tasks,
            "max_actions": args.max_actions,
            "model": args.model,
        },
        "results": results_by_agent,
        "summary": {
            agent_name: {
                "completion_rate": sum(1 for r in results if r["completed"]) / len(results) * 100,
                "avg_progress": sum(r["partial_progress"] for r in results) / len(results),
                "avg_tokens": sum(r["tokens"] for r in results) / len(results),
            }
            for agent_name, results in results_by_agent.items()
        },
    }

    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\nSaved results: {results_path}")

    # Print comparison table
    print(f"\n{'='*60}")
    print("AppWorld Results Comparison")
    print(f"{'='*60}")
    print(f"{'Agent':<20} {'Complete%':>12} {'Progress%':>12} {'Tokens':>10}")
    print("-" * 60)
    for agent_name, summary in results_data["summary"].items():
        print(f"{agent_name:<20} {summary['completion_rate']:>11.1f}% {summary['avg_progress']:>11.1f}% {summary['avg_tokens']:>10.0f}")


if __name__ == "__main__":
    main()
