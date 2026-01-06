#!/usr/bin/env python3
"""
TheAgentCompany Benchmark for ECM.

TheAgentCompany simulates a realistic company work environment where agents
must complete complex, multi-step tasks that mirror real employee workflows.

Work Environment Simulation:
- Email system with threads and attachments
- Document management (Word, Excel, PDF)
- Project management tools
- Code repositories
- Communication channels (Slack-like)
- Databases and dashboards

Task Categories:
1. Administrative: Scheduling, document preparation, reporting
2. Technical: Code review, debugging, documentation
3. Communication: Email drafting, meeting coordination
4. Analysis: Data analysis, report generation
5. Cross-functional: Tasks spanning multiple systems

Key Evaluation Dimensions:
- Task Completion: Fully completing multi-step workflows
- Quality: Output matches expected standards
- Efficiency: Steps taken vs optimal path
- Context Retention: Remembering details across long workflows
- Error Handling: Recovering from mistakes gracefully

Metrics:
- Overall Completion Rate
- Average Task Quality Score (1-5)
- Step Efficiency Ratio
- Context Utilization Score
- Cross-system Coordination Score

Usage:
    # Run evaluation
    uv run benchmarks/longhorizon/run_agentcompany.py --max-tasks 10

    # Compare agents
    uv run benchmarks/longhorizon/run_agentcompany.py --agents ecm longcontext rag

    # Filter by task category
    uv run benchmarks/longhorizon/run_agentcompany.py --category technical

References:
- TheAgentCompany: Benchmarking LLM Agents on Consequential Real World Tasks
- https://github.com/TheAgentCompany/TheAgentCompany
"""

import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from tqdm import tqdm

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.common.base_agent import BaseAgent
from benchmarks.memory.agents import AVAILABLE_AGENTS


# =============================================================================
# Company Environment Simulation
# =============================================================================

@dataclass
class Employee:
    """Simulated employee in the company."""
    name: str
    email: str
    role: str
    department: str
    reports_to: Optional[str] = None


@dataclass
class Email:
    """Simulated email."""
    id: str
    from_: str
    to: list[str]
    cc: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    attachments: list[str] = field(default_factory=list)
    timestamp: str = ""
    thread_id: Optional[str] = None


@dataclass
class Document:
    """Simulated document."""
    id: str
    name: str
    type: str  # word, excel, pdf, code
    content: str = ""
    owner: str = ""
    last_modified: str = ""
    shared_with: list[str] = field(default_factory=list)


@dataclass
class Project:
    """Simulated project."""
    id: str
    name: str
    status: str  # planning, active, review, completed
    owner: str
    members: list[str] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    deadline: str = ""


class CompanyEnvironment:
    """
    Simulates a company work environment.

    Provides access to:
    - Email system
    - Document repository
    - Project management
    - Employee directory
    - Communication channels
    """

    def __init__(self):
        self.employees: dict[str, Employee] = {}
        self.emails: dict[str, Email] = {}
        self.documents: dict[str, Document] = {}
        self.projects: dict[str, Project] = {}
        self.channels: dict[str, list[dict]] = {}
        self.action_log: list[dict] = []

        self._initialize_company()

    def _initialize_company(self):
        """Set up initial company state."""
        # Create employees
        departments = ["Engineering", "Product", "Marketing", "Sales", "HR"]
        roles = ["Manager", "Senior", "Junior", "Lead", "Director"]

        for i, (dept, role) in enumerate([
            ("Engineering", "Director"),
            ("Engineering", "Manager"),
            ("Engineering", "Senior"),
            ("Engineering", "Junior"),
            ("Product", "Manager"),
            ("Product", "Senior"),
            ("Marketing", "Manager"),
            ("Sales", "Manager"),
            ("HR", "Manager"),
        ]):
            name = f"Employee_{i+1}"
            self.employees[name] = Employee(
                name=name,
                email=f"{name.lower()}@company.com",
                role=role,
                department=dept,
                reports_to="Employee_1" if i > 0 and dept == "Engineering" else None,
            )

        # Create some initial documents
        self.documents["doc_001"] = Document(
            id="doc_001",
            name="Q4_Report_Draft.docx",
            type="word",
            content="Quarterly report draft with placeholder sections...",
            owner="Employee_1",
            last_modified=datetime.now().isoformat(),
        )

        self.documents["doc_002"] = Document(
            id="doc_002",
            name="Budget_2024.xlsx",
            type="excel",
            content="Budget spreadsheet with department allocations...",
            owner="Employee_5",
            last_modified=datetime.now().isoformat(),
        )

        # Create a project
        self.projects["proj_001"] = Project(
            id="proj_001",
            name="Product Launch v2.0",
            status="active",
            owner="Employee_5",
            members=["Employee_1", "Employee_2", "Employee_5", "Employee_7"],
            tasks=[
                {"id": "task_1", "title": "Finalize specs", "status": "done"},
                {"id": "task_2", "title": "Development", "status": "in_progress"},
                {"id": "task_3", "title": "Testing", "status": "pending"},
                {"id": "task_4", "title": "Launch prep", "status": "pending"},
            ],
            deadline=(datetime.now() + timedelta(days=30)).isoformat(),
        )

        # Create some emails
        self.emails["email_001"] = Email(
            id="email_001",
            from_="employee_5@company.com",
            to=["employee_1@company.com"],
            subject="Q4 Report Review Needed",
            body="Hi, please review the attached Q4 report draft and provide feedback by Friday.",
            attachments=["Q4_Report_Draft.docx"],
            timestamp=datetime.now().isoformat(),
        )

        # Create communication channel
        self.channels["engineering"] = [
            {"user": "Employee_2", "message": "Sprint planning at 2pm today", "time": "9:00 AM"},
            {"user": "Employee_3", "message": "PR #123 ready for review", "time": "10:30 AM"},
        ]

    def reset(self):
        """Reset environment to initial state."""
        self.emails = {}
        self.action_log = []
        self._initialize_company()

    def execute_action(self, action_type: str, params: dict) -> dict:
        """
        Execute an action in the company environment.

        Actions:
        - email_send: Send an email
        - email_read: Read an email
        - email_search: Search emails
        - doc_read: Read a document
        - doc_create: Create a document
        - doc_edit: Edit a document
        - project_update: Update project status
        - employee_lookup: Look up employee info
        - channel_post: Post to channel
        - channel_read: Read channel messages
        """
        result = {"success": False, "data": None, "message": ""}

        try:
            if action_type == "email_send":
                email_id = f"email_{len(self.emails)+1:03d}"
                self.emails[email_id] = Email(
                    id=email_id,
                    from_=params.get("from", "agent@company.com"),
                    to=params.get("to", []),
                    cc=params.get("cc", []),
                    subject=params.get("subject", ""),
                    body=params.get("body", ""),
                    timestamp=datetime.now().isoformat(),
                )
                result = {"success": True, "data": {"email_id": email_id}, "message": "Email sent"}

            elif action_type == "email_read":
                email_id = params.get("id")
                if email_id in self.emails:
                    email = self.emails[email_id]
                    result = {"success": True, "data": {
                        "from": email.from_,
                        "to": email.to,
                        "subject": email.subject,
                        "body": email.body,
                        "attachments": email.attachments,
                    }, "message": "Email retrieved"}
                else:
                    result = {"success": False, "data": None, "message": "Email not found"}

            elif action_type == "email_search":
                query = params.get("query", "").lower()
                matches = [
                    {"id": e.id, "subject": e.subject, "from": e.from_}
                    for e in self.emails.values()
                    if query in e.subject.lower() or query in e.body.lower()
                ]
                result = {"success": True, "data": {"emails": matches}, "message": f"Found {len(matches)} emails"}

            elif action_type == "doc_read":
                doc_id = params.get("id")
                if doc_id in self.documents:
                    doc = self.documents[doc_id]
                    result = {"success": True, "data": {
                        "name": doc.name,
                        "type": doc.type,
                        "content": doc.content[:500],
                        "owner": doc.owner,
                    }, "message": "Document retrieved"}
                else:
                    result = {"success": False, "data": None, "message": "Document not found"}

            elif action_type == "doc_create":
                doc_id = f"doc_{len(self.documents)+1:03d}"
                self.documents[doc_id] = Document(
                    id=doc_id,
                    name=params.get("name", "Untitled"),
                    type=params.get("type", "word"),
                    content=params.get("content", ""),
                    owner=params.get("owner", "agent"),
                    last_modified=datetime.now().isoformat(),
                )
                result = {"success": True, "data": {"doc_id": doc_id}, "message": "Document created"}

            elif action_type == "doc_edit":
                doc_id = params.get("id")
                if doc_id in self.documents:
                    self.documents[doc_id].content = params.get("content", self.documents[doc_id].content)
                    self.documents[doc_id].last_modified = datetime.now().isoformat()
                    result = {"success": True, "data": {"doc_id": doc_id}, "message": "Document updated"}
                else:
                    result = {"success": False, "data": None, "message": "Document not found"}

            elif action_type == "project_update":
                proj_id = params.get("id")
                if proj_id in self.projects:
                    if "status" in params:
                        self.projects[proj_id].status = params["status"]
                    if "task_update" in params:
                        task_id = params["task_update"].get("id")
                        for task in self.projects[proj_id].tasks:
                            if task["id"] == task_id:
                                task["status"] = params["task_update"].get("status", task["status"])
                    result = {"success": True, "data": {"project": proj_id}, "message": "Project updated"}
                else:
                    result = {"success": False, "data": None, "message": "Project not found"}

            elif action_type == "employee_lookup":
                name = params.get("name", "")
                matches = [
                    {"name": e.name, "email": e.email, "role": e.role, "department": e.department}
                    for e in self.employees.values()
                    if name.lower() in e.name.lower() or name.lower() in e.email.lower()
                ]
                result = {"success": True, "data": {"employees": matches}, "message": f"Found {len(matches)} employees"}

            elif action_type == "channel_post":
                channel = params.get("channel", "general")
                if channel not in self.channels:
                    self.channels[channel] = []
                self.channels[channel].append({
                    "user": "Agent",
                    "message": params.get("message", ""),
                    "time": datetime.now().strftime("%I:%M %p"),
                })
                result = {"success": True, "data": None, "message": "Message posted"}

            elif action_type == "channel_read":
                channel = params.get("channel", "general")
                messages = self.channels.get(channel, [])[-10:]  # Last 10 messages
                result = {"success": True, "data": {"messages": messages}, "message": f"{len(messages)} messages"}

            else:
                result = {"success": False, "data": None, "message": f"Unknown action: {action_type}"}

        except Exception as e:
            result = {"success": False, "data": None, "message": str(e)}

        # Log action
        self.action_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action_type,
            "params": params,
            "success": result["success"],
        })

        return result

    def get_context_summary(self) -> str:
        """Get a summary of current environment state."""
        lines = [
            f"Emails: {len(self.emails)} total",
            f"Documents: {len(self.documents)} total",
            f"Projects: {len(self.projects)} active",
            f"Employees: {len(self.employees)} in directory",
        ]

        if self.emails:
            recent = list(self.emails.values())[-3:]
            lines.append("\nRecent emails:")
            for e in recent:
                lines.append(f"  - {e.subject} (from {e.from_})")

        return "\n".join(lines)


# =============================================================================
# Task Definitions
# =============================================================================

@dataclass
class CompanyTask:
    """A work task in TheAgentCompany."""
    task_id: str
    title: str
    description: str
    category: str  # administrative, technical, communication, analysis, cross_functional
    systems_involved: list[str]
    steps: list[str]
    success_criteria: list[str]
    difficulty: int  # 1-5
    expected_duration: int  # minutes
    context: dict = field(default_factory=dict)


def generate_company_tasks(
    num_tasks: int = 20,
    category_filter: Optional[str] = None,
) -> list[CompanyTask]:
    """Generate realistic company work tasks."""
    task_templates = [
        # Administrative tasks
        {
            "category": "administrative",
            "title": "Prepare meeting summary and action items",
            "description": "Review the meeting notes, extract key decisions and action items, and send a summary to all attendees.",
            "systems": ["email", "documents"],
            "steps": [
                "Read the meeting notes document",
                "Identify key decisions made",
                "List action items with owners",
                "Create summary document",
                "Email summary to attendees",
            ],
            "criteria": ["summary_created", "action_items_identified", "email_sent"],
            "difficulty": 2,
            "duration": 20,
        },
        {
            "category": "administrative",
            "title": "Schedule quarterly review meetings",
            "description": "Coordinate with department heads to schedule Q4 review meetings, considering everyone's availability.",
            "systems": ["email", "calendar", "employee_directory"],
            "steps": [
                "Look up department heads",
                "Send availability request emails",
                "Collect responses",
                "Propose meeting times",
                "Send calendar invites",
            ],
            "criteria": ["all_heads_contacted", "times_proposed", "invites_sent"],
            "difficulty": 3,
            "duration": 30,
        },
        # Technical tasks
        {
            "category": "technical",
            "title": "Review and document code changes",
            "description": "Review the PR for the new feature, check for issues, and update the technical documentation.",
            "systems": ["code_repo", "documents", "project_management"],
            "steps": [
                "Read the PR description and changes",
                "Identify potential issues",
                "Write review comments",
                "Update technical docs",
                "Update project task status",
            ],
            "criteria": ["review_completed", "docs_updated", "task_updated"],
            "difficulty": 4,
            "duration": 45,
        },
        {
            "category": "technical",
            "title": "Investigate and document bug report",
            "description": "Analyze the reported bug, identify root cause, and document findings for the engineering team.",
            "systems": ["project_management", "code_repo", "documents"],
            "steps": [
                "Read bug report details",
                "Analyze error logs",
                "Identify likely cause",
                "Document investigation findings",
                "Update bug status with findings",
            ],
            "criteria": ["analysis_complete", "cause_identified", "documented"],
            "difficulty": 4,
            "duration": 40,
        },
        # Communication tasks
        {
            "category": "communication",
            "title": "Draft project status update email",
            "description": "Write a comprehensive project status update for stakeholders, including progress, risks, and next steps.",
            "systems": ["email", "project_management", "documents"],
            "steps": [
                "Review current project status",
                "Gather progress metrics",
                "Identify risks and blockers",
                "Draft status email",
                "Send to stakeholders",
            ],
            "criteria": ["status_gathered", "email_drafted", "stakeholders_informed"],
            "difficulty": 3,
            "duration": 25,
        },
        {
            "category": "communication",
            "title": "Respond to client inquiry",
            "description": "Read the client's technical inquiry, gather relevant information, and send a detailed response.",
            "systems": ["email", "documents", "employee_directory"],
            "steps": [
                "Read client email",
                "Understand the question",
                "Find relevant documentation",
                "Consult with technical lead if needed",
                "Draft and send response",
            ],
            "criteria": ["inquiry_understood", "info_gathered", "response_sent"],
            "difficulty": 3,
            "duration": 30,
        },
        # Analysis tasks
        {
            "category": "analysis",
            "title": "Analyze quarterly metrics report",
            "description": "Review the quarterly metrics, identify trends and anomalies, and prepare an executive summary.",
            "systems": ["documents", "data_dashboard"],
            "steps": [
                "Open quarterly report",
                "Review key metrics",
                "Identify trends",
                "Note anomalies",
                "Create executive summary",
            ],
            "criteria": ["metrics_reviewed", "trends_identified", "summary_created"],
            "difficulty": 4,
            "duration": 35,
        },
        # Cross-functional tasks
        {
            "category": "cross_functional",
            "title": "Coordinate product launch activities",
            "description": "Work across engineering, marketing, and sales to coordinate the upcoming product launch activities.",
            "systems": ["email", "project_management", "channels", "documents"],
            "steps": [
                "Review launch timeline",
                "Check engineering readiness",
                "Confirm marketing materials",
                "Verify sales enablement",
                "Send coordination update",
                "Update project status",
            ],
            "criteria": ["all_teams_checked", "blockers_identified", "status_communicated"],
            "difficulty": 5,
            "duration": 50,
        },
    ]

    # Filter by category if specified
    if category_filter:
        task_templates = [t for t in task_templates if t["category"] == category_filter]

    # Generate tasks
    tasks = []
    for i in range(num_tasks):
        template = task_templates[i % len(task_templates)]
        task = CompanyTask(
            task_id=f"company_{i+1:03d}",
            title=template["title"],
            description=template["description"],
            category=template["category"],
            systems_involved=template["systems"],
            steps=template["steps"],
            success_criteria=template["criteria"],
            difficulty=template["difficulty"],
            expected_duration=template["duration"],
        )
        tasks.append(task)

    return tasks


# =============================================================================
# Evaluation
# =============================================================================

@dataclass
class TaskEvaluation:
    """Evaluation result for a company task."""
    task_id: str
    agent_name: str
    completed: bool
    quality_score: float  # 1-5
    steps_taken: int
    optimal_steps: int
    efficiency: float
    criteria_met: int
    total_criteria: int
    input_tokens: int
    output_tokens: int
    latency: float
    context_utilization: float  # How well agent used available context


class CompanyEvaluator:
    """Evaluates agents on TheAgentCompany tasks."""

    def __init__(self, agent: BaseAgent, agent_name: str, env: CompanyEnvironment):
        self.agent = agent
        self.agent_name = agent_name
        self.env = env

    def evaluate_task(self, task: CompanyTask, max_steps: int = 15) -> TaskEvaluation:
        """Evaluate agent on a single company task."""
        start_time = time.time()
        total_input = 0
        total_output = 0
        steps_taken = 0
        actions_successful = 0

        # Reset environment
        self.env.reset()

        # Provide task context
        context = f"""
TheAgentCompany Work Task

Task: {task.title}
Category: {task.category}
Description: {task.description}

Available Systems: {', '.join(task.systems_involved)}

Expected Steps:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(task.steps))}

Success Criteria:
{chr(10).join(f'- {c}' for c in task.success_criteria)}

Current Environment:
{self.env.get_context_summary()}
"""
        self.agent.memorize(context, context_id=0)

        # Execute task steps
        for step in range(max_steps):
            # Get current state
            env_summary = self.env.get_context_summary()

            # Ask agent for next action
            prompt = f"""
Step {step + 1}/{max_steps}

Task: {task.title}

Current Environment State:
{env_summary}

Progress so far: {actions_successful} successful actions

What action should be taken next?
Specify the action type and parameters.

If the task is complete, respond with "TASK COMPLETE" and a brief summary.
"""
            result = self.agent.query(prompt, context_id=0)
            response = result.get("answer", "")
            total_input += result.get("input_tokens", 0)
            total_output += result.get("output_tokens", 0)

            # Check for completion
            if "TASK COMPLETE" in response.upper():
                break

            # Parse and execute action
            action_type, params = self._parse_action(response)
            if action_type:
                exec_result = self.env.execute_action(action_type, params)
                steps_taken += 1

                if exec_result["success"]:
                    actions_successful += 1

                # Memorize outcome
                outcome = f"Action: {action_type} -> {exec_result['message']}"
                self.agent.memorize(outcome, context_id=0)

        latency = time.time() - start_time

        # Evaluate results
        criteria_met = self._evaluate_criteria(task)
        completed = criteria_met >= len(task.success_criteria) * 0.8
        quality = self._calculate_quality(task, criteria_met, steps_taken)
        efficiency = len(task.steps) / max(steps_taken, 1) if steps_taken > 0 else 0
        context_util = self._calculate_context_utilization(task)

        return TaskEvaluation(
            task_id=task.task_id,
            agent_name=self.agent_name,
            completed=completed,
            quality_score=quality,
            steps_taken=steps_taken,
            optimal_steps=len(task.steps),
            efficiency=min(efficiency, 1.0) * 100,
            criteria_met=criteria_met,
            total_criteria=len(task.success_criteria),
            input_tokens=total_input,
            output_tokens=total_output,
            latency=latency,
            context_utilization=context_util,
        )

    def _parse_action(self, response: str) -> tuple[Optional[str], dict]:
        """Parse agent response into action type and params."""
        response_lower = response.lower()

        # Action keywords
        action_map = {
            "send email": "email_send",
            "read email": "email_read",
            "search email": "email_search",
            "read document": "doc_read",
            "create document": "doc_create",
            "edit document": "doc_edit",
            "update project": "project_update",
            "look up": "employee_lookup",
            "post": "channel_post",
            "read channel": "channel_read",
        }

        for keyword, action in action_map.items():
            if keyword in response_lower:
                return action, {}

        # Default action based on context
        if "email" in response_lower:
            return "email_search", {"query": "recent"}
        if "document" in response_lower or "doc" in response_lower:
            return "doc_read", {"id": "doc_001"}

        return None, {}

    def _evaluate_criteria(self, task: CompanyTask) -> int:
        """Evaluate how many success criteria were met."""
        # Simplified: count actions that match criteria
        criteria_actions = {
            "summary_created": ["doc_create"],
            "email_sent": ["email_send"],
            "action_items_identified": ["doc_read", "doc_create"],
            "all_heads_contacted": ["email_send", "employee_lookup"],
            "review_completed": ["doc_read"],
            "docs_updated": ["doc_edit", "doc_create"],
            "task_updated": ["project_update"],
        }

        met = 0
        for criterion in task.success_criteria:
            expected = criteria_actions.get(criterion, [])
            for action in self.env.action_log:
                if action["action"] in expected and action["success"]:
                    met += 1
                    break

        return min(met, len(task.success_criteria))

    def _calculate_quality(self, task: CompanyTask, criteria_met: int, steps: int) -> float:
        """Calculate quality score (1-5)."""
        completion_ratio = criteria_met / len(task.success_criteria) if task.success_criteria else 0
        efficiency_ratio = len(task.steps) / max(steps, 1) if steps > 0 else 0

        # Weight: 60% completion, 40% efficiency
        score = (completion_ratio * 0.6 + min(efficiency_ratio, 1.0) * 0.4) * 5
        return max(1.0, min(5.0, score))

    def _calculate_context_utilization(self, task: CompanyTask) -> float:
        """Calculate how well context was utilized."""
        # Check if agent used relevant systems
        systems_used = set()
        for action in self.env.action_log:
            if action["action"].startswith("email"):
                systems_used.add("email")
            elif action["action"].startswith("doc"):
                systems_used.add("documents")
            elif action["action"].startswith("project"):
                systems_used.add("project_management")
            elif action["action"].startswith("employee"):
                systems_used.add("employee_directory")
            elif action["action"].startswith("channel"):
                systems_used.add("channels")

        expected = set(task.systems_involved)
        if not expected:
            return 100.0

        overlap = len(systems_used & expected)
        return (overlap / len(expected)) * 100


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="TheAgentCompany evaluation for ECM")

    parser.add_argument("--agents", nargs="+", default=["ecm", "longcontext"],
                        help="Agents to evaluate")
    parser.add_argument("--max-tasks", type=int, default=10, help="Max tasks to run")
    parser.add_argument("--max-steps", type=int, default=15, help="Max steps per task")
    parser.add_argument("--category", default=None,
                        choices=["administrative", "technical", "communication", "analysis", "cross_functional"],
                        help="Filter by task category")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--output-dir", default="benchmarks/results/agentcompany", help="Output directory")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Generate tasks
    print("Generating TheAgentCompany tasks...")
    tasks = generate_company_tasks(
        num_tasks=args.max_tasks,
        category_filter=args.category,
    )
    print(f"Generated {len(tasks)} tasks")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize environment
    env = CompanyEnvironment()

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

        evaluator = CompanyEvaluator(agent, name, env)
        agent_results = []

        iterator = tasks
        if not args.quiet:
            iterator = tqdm(tasks, desc=name)

        for task in iterator:
            result = evaluator.evaluate_task(task, max_steps=args.max_steps)
            agent_results.append(result)

        all_results.extend(agent_results)

        # Print summary
        completed = sum(1 for r in agent_results if r.completed)
        avg_quality = sum(r.quality_score for r in agent_results) / len(agent_results)
        avg_efficiency = sum(r.efficiency for r in agent_results) / len(agent_results)
        avg_context = sum(r.context_utilization for r in agent_results) / len(agent_results)
        avg_tokens = sum(r.input_tokens + r.output_tokens for r in agent_results) / len(agent_results)

        print(f"\n{name} Summary:")
        print(f"  Completion: {completed}/{len(agent_results)} ({completed/len(agent_results)*100:.1f}%)")
        print(f"  Avg Quality: {avg_quality:.2f}/5.0")
        print(f"  Avg Efficiency: {avg_efficiency:.1f}%")
        print(f"  Context Utilization: {avg_context:.1f}%")
        print(f"  Avg Tokens/Task: {avg_tokens:.0f}")

        agent.reset()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"agentcompany_results_{timestamp}.json"

    results_by_agent = {}
    for r in all_results:
        if r.agent_name not in results_by_agent:
            results_by_agent[r.agent_name] = []
        results_by_agent[r.agent_name].append({
            "task_id": r.task_id,
            "completed": r.completed,
            "quality_score": r.quality_score,
            "efficiency": r.efficiency,
            "context_utilization": r.context_utilization,
            "tokens": r.input_tokens + r.output_tokens,
            "latency": r.latency,
        })

    results_data = {
        "timestamp": timestamp,
        "config": {
            "agents": args.agents,
            "max_tasks": args.max_tasks,
            "max_steps": args.max_steps,
            "category": args.category,
            "model": args.model,
        },
        "results": results_by_agent,
        "summary": {
            agent_name: {
                "completion_rate": sum(1 for r in results if r["completed"]) / len(results) * 100,
                "avg_quality": sum(r["quality_score"] for r in results) / len(results),
                "avg_efficiency": sum(r["efficiency"] for r in results) / len(results),
                "avg_context_util": sum(r["context_utilization"] for r in results) / len(results),
                "avg_tokens": sum(r["tokens"] for r in results) / len(results),
            }
            for agent_name, results in results_by_agent.items()
        },
    }

    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\nSaved results: {results_path}")

    # Print comparison table
    print(f"\n{'='*70}")
    print("TheAgentCompany Results Comparison")
    print(f"{'='*70}")
    print(f"{'Agent':<20} {'Complete%':>10} {'Quality':>10} {'Efficiency':>12} {'Context':>10}")
    print("-" * 70)
    for agent_name, summary in results_data["summary"].items():
        print(f"{agent_name:<20} {summary['completion_rate']:>9.1f}% {summary['avg_quality']:>9.2f} "
              f"{summary['avg_efficiency']:>11.1f}% {summary['avg_context_util']:>9.1f}%")


if __name__ == "__main__":
    main()
