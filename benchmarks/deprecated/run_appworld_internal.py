#!/usr/bin/env python3
"""
AppWorld-Style Benchmark for ECM (Internal Refactor).

Uses ECMAgentWrapper components to enforce explicit memory management.
"""

import os
import sys
import json
import time
import random
import argparse
from typing import Literal, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.adapters.ecm_adapter import ECMAgentWrapper, ECMLogger
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore
from tokens import TokenTracker

# =============================================================================
# Data Structures
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
    difficulty: str
    metadata: dict = field(default_factory=dict)

@dataclass
class BenchmarkResult:
    """Result of AppWorld benchmark."""
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
    subtasks_completed: int = 0
    total_subtasks: int = 0
    api_calls: int = 0

    # Timing
    elapsed_seconds: float = 0.0

    # Details
    task_results: list = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        return (self.tasks_completed / self.num_tasks * 100) if self.num_tasks > 0 else 0
    
    @property
    def progress_rate(self) -> float:
        return (self.subtasks_completed / self.total_subtasks * 100) if self.total_subtasks > 0 else 0


# =============================================================================
# App World Simulation
# =============================================================================

class AppWorldSimulator:
    """
    Simulates the AppWorld environment.
    """

    APPS = ["email", "calendar", "notes", "todo", "contacts", "files", "browser", "shopping", "social"]

    def __init__(self):
        self.states: dict[str, AppState] = {
            app: AppState(app_name=app, data={}) for app in self.APPS
        }
        self.action_log: list[dict] = []
        self._populate_initial_state()

    def _populate_initial_state(self):
        """Add some dummy data to make world alive."""
        self.states["email"].data["inbox"] = [
            {"id": "1", "from": "boss@company.com", "subject": "Project Kickoff", "content": "Meeting tomorrow at 10am."},
            {"id": "2", "from": "newsletter@tech.com", "subject": "Daily Tech News", "content": "AI is taking over..."},
            {"id": "3", "from": "charlie@newhire.com", "subject": "Hello!", "content": "Hi, I'm Charlie, the new designer. Here is my email."}
        ]
        self.states["notes"].data["notes"] = [
            {"id": "1", "title": "Ideas", "content": "Buy milk, Learn Python"}
        ]
        self.states["contacts"].data["contacts"] = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]

    def reset(self):
        """Reset all app states."""
        self.states = {app: AppState(app_name=app, data={}) for app in self.APPS}
        self.action_log = []
        self._populate_initial_state()

    def execute_action(self, action: AppAction) -> dict:
        """Execute action and return result."""
        app_state = self.states.get(action.app)
        if not app_state:
            return {"success": False, "result": f"Unknown app: {action.app}", "state_change": {}}

        result = self._simulate_action(app_state, action)

        self.action_log.append({
            "timestamp": datetime.now().isoformat(),
            "app": action.app,
            "action": action.action,
            "params": action.params,
            "success": result["success"],
        })
        return result

    def _simulate_action(self, app_state: AppState, action: AppAction) -> dict:
        app = action.app
        act = action.action.lower()
        params = action.params

        # -- Email --
        if app == "email":
            if act == "send":
                app_state.data.setdefault("sent", []).append(params)
                return {"success": True, "result": f"Email sent to {params.get('to')}", "state_change": {"sent": params}}
            elif act == "read":
                # Find email
                raw_id = params.get("id") or params.get("emailId") or params.get("email_id")
                query_id = str(raw_id) if raw_id is not None else None
                query_from = params.get("from")
                inbox = app_state.data.get("inbox", [])
                
                target = None
                if query_id and query_id != "latest":
                    target = next((m for m in inbox if str(m["id"]) == query_id), None)
                elif query_from:
                    target = next((m for m in inbox if query_from in m["from"]), None)
                else:
                    # Default to latest
                    target = inbox[0] if inbox else None
                
                if target:
                     return {"success": True, "result": f"Email From: {target['from']}\nSubject: {target['subject']}\nBody: {target['content']}", "state_change": {}}
                return {"success": False, "result": "Email not found.", "state_change": {}}
                
            elif act == "search":
                query = params.get("query", "")
                inbox = app_state.data.get("inbox", [])
                # Handle "from:Name" syntax
                if query.lower().startswith("from:"):
                    clean_query = query[5:].strip().lower()
                    matches = [m for m in inbox if clean_query in m["from"].lower()]
                else:
                    matches = [m for m in inbox if query.lower() in m["subject"].lower() or query.lower() in m["from"].lower()]
                
                if matches:
                    return {"success": True, "result": f"Found {len(matches)} emails: " + ", ".join([f"[{m['id']}] {m['subject']}" for m in matches]), "state_change": {}}
                return {"success": True, "result": "No matching emails found.", "state_change": {}}

            elif act == "list":
                inbox = app_state.data.get("inbox", [])
                return {"success": True, "result": "Inbox:\n" + "\n".join([f"[{m['id']}] From: {m['from']} | Subject: {m['subject']}" for m in inbox]), "state_change": {}}

        # -- Calendar --
        elif app == "calendar":
            if act == "create_event" or act == "create":
                app_state.data.setdefault("events", []).append(params)
                # Normalize action name in log for checks
                if act == "create": action.action = "create_event" 
                return {"success": True, "result": f"Event '{params.get('title')}' scheduled for {params.get('time')}", "state_change": {"event": params}}
            elif act == "list_events" or act == "list":
                events = app_state.data.get("events", [])
                return {"success": True, "result": f"Calendar Events:\n" + "\n".join([f"- {e.get('title')} at {e.get('time')}" for e in events]), "state_change": {}}

        # -- Notes --
        elif app == "notes":
            if act == "create":
                app_state.data.setdefault("notes", []).append(params)
                return {"success": True, "result": f"Note '{params.get('title')}' saved.", "state_change": {"note": params}}
            elif act == "search":
                query = params.get("query", "").lower()
                notes = app_state.data.get("notes", [])
                matches = [n for n in notes if query in n["title"].lower() or query in n["content"].lower()]
                if matches:
                    return {"success": True, "result": "Notes found:\n" + "\n".join([f"Title: {n['title']}\nContent: {n['content']}" for n in matches]), "state_change": {}}
                return {"success": True, "result": "No matching notes found.", "state_change": {}}
            elif act == "list":
                notes = app_state.data.get("notes", [])
                return {"success": True, "result": "Notes:\n" + "\n".join([f"- {n['title']}" for n in notes]), "state_change": {}}

        # -- Todo --
        elif app == "todo":
            if act == "add":
                app_state.data.setdefault("todos", []).append(params)
                return {"success": True, "result": f"Todo added: {params.get('task')}", "state_change": {"todo": params}}
            elif act == "list":
                todos = app_state.data.get("todos", [])
                return {"success": True, "result": f"Todos: {len(todos)} active items.", "state_change": {}}
            elif act == "complete":
                return {"success": True, "result": "Task marked as complete.", "state_change": {"completed": True}}

        # -- Contacts --
        elif app == "contacts":
            if act == "add":
                app_state.data.setdefault("contacts", []).append(params)
                return {"success": True, "result": f"Contact saved: {params.get('name')}", "state_change": {"contact": params}}
            elif act == "search":
                return {"success": True, "result": "Contact found: Alice (alice@example.com)", "state_change": {}}

        # -- Files --
        elif app == "files":
            if act == "create":
                app_state.data.setdefault("files", []).append(params)
                return {"success": True, "result": f"File created: {params.get('name')}", "state_change": {"file": params}}
            elif act == "list":
                return {"success": True, "result": "Files: ./documents, ./photos", "state_change": {}}

        # Fallback
        return {"success": True, "result": f"Action '{act}' executed on {app} (simulated success)", "state_change": {}}

    def checks_for_task(self, task: AppWorldTask) -> int:
        """
        Check how many success criteria are met.
        Since we don't have robust state inspection for synthetic tasks, 
        we rely on action history matching specific patterns.
        """
        passed = 0
        
        # Simplified checking logic for demonstration/benchmark consistency
        # In real AppWorld this is complex state matching.
        # Here we check if "critical actions" were performed.
        
        history_strings = [
            f"{log['app']}.{log['action']}" for log in self.action_log
        ]
        
        for criterion in task.success_criteria:
            # Map criterion to expected action patterns
            if criterion == "calendar_event_created":
                if "calendar.create_event" in history_strings: passed += 1
            elif criterion == "confirmation_sent":
                if "email.send" in history_strings: passed += 1
            elif criterion == "todos_created_from_notes":
                if "todo.add" in history_strings and history_strings.count("todo.add") >= 2: passed += 1
            elif criterion == "contact_added":
                if "contacts.add" in history_strings: passed += 1
            elif criterion == "welcome_sent":
                if "email.send" in history_strings: passed += 1
            elif criterion == "folder_created":
                if "files.create" in history_strings: passed += 1
            elif criterion == "todo_completed":
                if "todo.complete" in history_strings: passed += 1
            elif criterion == "all_apps_updated":
                 # Heuristic: check if we touched at least 3 distinct apps
                 unique_apps = set(log['app'] for log in self.action_log)
                 if len(unique_apps) >= 3: passed += 1
            elif criterion == "team_notified":
                if "email.send" in history_strings: passed += 1
                
        return passed


# =============================================================================
# Task Generation
# =============================================================================

def generate_tasks() -> list[AppWorldTask]:
    return [
        AppWorldTask(
            task_id="appworld_001",
            description="Schedule a meeting based on the latest email request from 'boss@company.com' and reply to confirm.",
            goal="Read email -> Schedule Calendar -> Reply Email",
            apps_involved=["email", "calendar"],
            actions=[],
            success_criteria=["calendar_event_created", "confirmation_sent"],
            difficulty="medium"
        ),
        AppWorldTask(
            task_id="appworld_002",
            description="Read the latest note about 'Ideas' and create Todo items for each idea found in it.",
            goal="Read Note -> Create 2 Todos",
            apps_involved=["notes", "todo"],
            actions=[],
            success_criteria=["todos_created_from_notes"],
            difficulty="medium"
        ),
        AppWorldTask(
            task_id="appworld_003",
            description="A new team member 'Charlie' sent an email (simulated). Add them to contacts and send a welcome email.",
            goal="Add Contact -> Send Email",
            apps_involved=["email", "contacts"],
            actions=[],
            success_criteria=["contact_added", "welcome_sent"],
            difficulty="medium"
        )
    ]

# =============================================================================
# Agent
# =============================================================================

class AppWorldExplicitAgent(ECMAgentWrapper):
    """
    AppWorld Agent using Explicit ECM + App Tools.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.simulator = None
        self.current_result = None

    def _run_tool_loop(self, messages: list[dict], max_rounds: int = 15) -> str:
        
        APP_TOOL = {
            "type": "function",
            "function": {
                "name": "app_action",
                "description": "Perform an action in an app.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app": {
                            "type": "string", 
                            "enum": ["email", "calendar", "notes", "todo", "contacts", "files", "browser", "shopping", "social"],
                            "description": "App to use"
                        },
                        "action": {
                            "type": "string",
                            "description": "Action name (e.g. send, read, create, add, list, search)"
                        },
                        "params": {
                            "type": "string",
                            "description": "JSON string of parameters (e.g. '{\"to\": \"bob\", \"subject\": \"Hi\"}')"
                        }
                    },
                    "required": ["app", "action", "params"]
                }
            }
        }
        
        tools = [CTX_CLI_TOOL, APP_TOOL]
        
        for round_num in range(max_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            assistant_msg = response.choices[0].message
            messages.append(assistant_msg.model_dump())

            if hasattr(self, 'current_result') and response.usage:
                self.current_result.total_prompt_tokens += response.usage.prompt_tokens
                self.current_result.total_completion_tokens += response.usage.completion_tokens
                self.current_result.api_calls += 1

            if not assistant_msg.tool_calls:
                return assistant_msg.content or ""
            
            for tool_call in assistant_msg.tool_calls:
                call_id = tool_call.id
                
                if tool_call.function.name == "ctx_cli":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    result, _ = execute_command(self.store, command)
                    
                    self.logger.log("CTX", command)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result
                    })
                    
                elif tool_call.function.name == "app_action":
                    args = json.loads(tool_call.function.arguments)
                    app = args.get("app")
                    action_name = args.get("action")
                    try:
                        params = json.loads(args.get("params", "{}"))
                    except:
                        params = {}
                        
                    app_action = AppAction(app=app, action=action_name, params=params)
                    result_dict = self.simulator.execute_action(app_action)
                    
                    output = f"Result: {result_dict['result']}"
                    
                    self.logger.log("APP", f"{app}.{action_name} {params}")
                    print(f"[{app.upper()}] {action_name} -> {result_dict['success']}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": output
                    })
        
        return messages[-1].get("content", "")

    def run_task(self, task: AppWorldTask, simulator: AppWorldSimulator, result_tracker: BenchmarkResult):
        self.simulator = simulator
        self.current_result = result_tracker
        
        print(f"\nTask: {task.description}")
        
        if self.store.current_project != "appworld_session":
            self.store.new_project("appworld_session")
            self.store.checkout("main", note="Starting AppWorld", create=True)
            
        from prompts import SYSTEM_PROMPT_ECM_MEMORY
        
        system_prompt = SYSTEM_PROMPT_ECM_MEMORY + """
# CURRENT STATE
project: appworld_session
scope: main

# ENVIRONMENT
You are in 'AppWorld', a simulated OS with apps: Email, Calendar, Notes, Todo, Contacts, Files.
You have `app_action` tool to interact with these apps.

# RULES
1. **Explore first**: If you need information, use `list`, `search`, or `read` actions in relevant apps.
2. **Memory**: Save important info (emails, dates, names) using `ctx_cli note` so you remember it for subsequent steps.
3. **Sequence**: 
   - Check Memory (`status`, `notes`)
   - Perform App Action (`app_action`)
   - Save Result to Memory (`note`)
   - Repeat

You are autonomous. Manage state explicitly.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task.description}\nGoal: {task.goal}"}
        ]
        
        final_response = self._run_tool_loop(messages)
        print(f"Agent Final: {final_response}")
        
        passed = simulator.checks_for_task(task)
        total = len(task.success_criteria)
        
        result_tracker.subtasks_completed += passed
        result_tracker.total_subtasks += total
        if passed >= total:
            result_tracker.tasks_completed += 1
            
        result_tracker.task_results.append({
            "task_id": task.task_id,
            "completed": passed >= total,
            "progress": f"{passed}/{total}"
        })


# =============================================================================
# Main
# =============================================================================

def main():
    from benchmarks.adapters.ecm_adapter import get_ecm_agent_config, get_ecm_dataset_config
    
    model_name = "gpt-4.1-mini"
    agent_config = get_ecm_agent_config(model=model_name)
    dataset_config = get_ecm_dataset_config()
    
    agent = AppWorldExplicitAgent(agent_config, dataset_config)
    simulator = AppWorldSimulator()
    tasks = generate_tasks()
    
    result = BenchmarkResult(approach="explicit", model=model_name, num_tasks=len(tasks))
    start_time = time.time()
    
    print(f"🚀 Starting AppWorld Benchmark (Explicit ECM) - {len(tasks)} tasks")
    
    for i, task in enumerate(tasks):
        print(f"\n--- Task {i+1}/{len(tasks)}: {task.task_id} ---")
        simulator.reset() # Reset world per task for clean slate
        agent.run_task(task, simulator, result)
        
    result.elapsed_seconds = time.time() - start_time
    
    # Report
    print("\n" + "="*50)
    print("APPWORLD BENCHMARK RESULTS")
    print("="*50)
    print(f"Model:           {result.model}")
    print(f"Tasks Completed: {result.tasks_completed}/{result.num_tasks} ({result.completion_rate:.1f}%)")
    print(f"Subtasks Passed: {result.subtasks_completed}/{result.total_subtasks} ({result.progress_rate:.1f}%)")
    print(f"Time Elapsed:    {result.elapsed_seconds:.2f}s")
    print(f"Total API Calls: {result.api_calls}")
    print(f"Tokens Used:     {result.total_prompt_tokens + result.total_completion_tokens:,}")
    print("-" * 50)
    for res in result.task_results:
        status = "✅ PASS" if res["completed"] else "❌ FAIL"
        print(f"{res['task_id']:<15} {status} ({res['progress']})")
    print("="*50)

if __name__ == "__main__":
    main()
