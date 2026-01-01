"""
Context Store - Git-like context management for LLM agents.

This module implements the core data structures and storage for managing
LLM conversation context using Git-like semantics.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypedDict


# =============================================================================
# Event Types
# =============================================================================

class CommitPayload(TypedDict):
    message: str
    hash: str
    messages_count: int


class CheckoutPayload(TypedDict):
    from_branch: str
    note: str


class BranchPayload(TypedDict):
    name: str
    from_branch: str


class TagPayload(TypedDict):
    name: str
    commit_hash: str
    description: str


class StashPayload(TypedDict):
    message: str
    stash_id: str


class PopPayload(TypedDict):
    stash_id: str


@dataclass
class Event:
    """Represents a context management event."""

    type: Literal[
        "commit", "checkout", "branch", "tag", "log", "status", "diff",
        "history", "stash", "pop", "merge", "cherry-pick", "bisect", "reset",
        "insight", "note"
    ]
    timestamp: str
    branch: str
    payload: dict

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "branch": self.branch,
            "payload": self.payload,
        }


# =============================================================================
# Core Data Structures
# =============================================================================

@dataclass
class Message:
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_calls: list | None = None
    name: str | None = None

    def to_openai_format(self) -> dict:
        msg = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass
class Note:
    """A persistent technical note associated with a branch/scope (Episodic Memory)."""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class Insight:
    """A global technical discovery or pattern (Semantic Memory)."""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class Commit:
    """A commit represents a snapshot of reasoning/learning."""

    hash: str
    message: str
    timestamp: str
    messages_snapshot: list[dict]  # The messages at time of commit
    parent_hash: str | None = None

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "message": self.message,
            "timestamp": self.timestamp,
            "parent_hash": self.parent_hash,
            "messages_count": len(self.messages_snapshot),
        }


@dataclass
class Tag:
    """An immutable reference to a specific commit."""

    name: str
    commit_hash: str
    description: str
    timestamp: str
    branch: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "commit_hash": self.commit_hash,
            "description": self.description,
            "timestamp": self.timestamp,
            "branch": self.branch,
        }


@dataclass
class StashEntry:
    """A stashed context state."""

    id: str
    message: str
    timestamp: str
    branch: str
    messages: list[dict]
    commits: list[Commit]


@dataclass
class Branch:
    """A branch contains working messages and commits."""

    name: str
    messages: list[Message] = field(default_factory=list)
    commits: list[Commit] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    head_note: str | None = None  # Note from checkout transition

    def get_last_commit_hash(self) -> str | None:
        return self.commits[-1].hash if self.commits else None

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def get_messages_for_api(self, system_prompt: str | None = None) -> list[dict]:
        """Get messages in OpenAI API format. Pure context without automatic injections."""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        # Add working messages with validation
        validated_messages = self._validate_tool_call_sequence(self.messages)
        for msg in validated_messages:
            result.append(msg.to_openai_format())

        return result

    def _validate_tool_call_sequence(self, messages: list) -> list:
        """Validate and fix tool_call sequences to ensure API compatibility."""
        if not messages:
            return messages

        result = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg.role == "assistant" and msg.tool_calls:
                expected_ids = set()
                for tc in msg.tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id:
                        expected_ids.add(tc_id)

                tool_responses = []
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    tool_responses.append(messages[j])
                    j += 1

                actual_ids = {tr.tool_call_id for tr in tool_responses if tr.tool_call_id}

                if expected_ids == actual_ids:
                    result.append(msg)
                    result.extend(tool_responses)
                    i = j
                elif j == len(messages):
                    result.append(msg)
                    result.extend(tool_responses)
                    i = j
                else:
                    i = j
            elif msg.role == "tool":
                i += 1
            else:
                result.append(msg)
                i += 1

        return result


@dataclass
class ContextStore:
    """
    The main context store - manages branches, commits, tags, and events.
    Also handles Episodic Memory (Notes) and Semantic Memory (Insights).
    """

    branches: dict[str, Branch] = field(default_factory=dict)
    tags: dict[str, Tag] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    stash: list[StashEntry] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    current_branch: str = "main"
    command_history: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Always ensure main branch exists
        if "main" not in self.branches:
            self.branches["main"] = Branch(name="main")

    def _generate_hash(self, content: str) -> str:
        """Generate a short hash."""
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _emit_event(self, event_type: str, payload: dict) -> Event:
        """Create and store an event."""
        event = Event(
            type=event_type,
            timestamp=datetime.now().isoformat(),
            branch=self.current_branch,
            payload=payload,
        )
        self.events.append(event)
        return event

    def _get_current_branch(self) -> Branch:
        return self.branches[self.current_branch]

    # =========================================================================
    # Git-like Commands
    # =========================================================================

    def note(self, message: str) -> tuple[str, Event]:
        """Record an episodic note in the current scope."""
        branch = self._get_current_branch()
        note = Note(content=message)
        branch.notes.append(note)
        
        event = self._emit_event("note", {"message": message})
        self.command_history.append(f"note -m \"{message}\"")
        return f"Note recorded in '{self.current_branch}'", event

    def insight(self, message: str) -> tuple[str, Event]:
        """Record a global semantic insight (Memory persistence)."""
        insight = Insight(content=message)
        self.insights.append(insight)
        
        event = self._emit_event("insight", {"message": message})
        self.command_history.append(f"insight -m \"{message}\"")
        return f"Global insight recorded", event

    def get_insights(self) -> str:
        """Return all semantic insights."""
        if not self.insights:
            return "No global insights recorded."
        
        lines = ["[SEMANTIC MEMORY - Global Insights]\n"]
        for i in self.insights:
            lines.append(f"- ({i.timestamp.strftime('%Y-%m-%d %H:%M:%S')}) {i.content}")
        return "\n".join(lines)

    def get_all_notes(self) -> str:
        """Return episodic notes from ALL scopes."""
        lines = ["[EPISODIC MEMORY - All Scope Notes]\n"]
        found = False
        for b_name, b in self.branches.items():
            if b.notes:
                found = True
                lines.append(f"Scope: {b_name}")
                for n in b.notes:
                    lines.append(f"  - ({n.timestamp.strftime('%Y-%m-%d %H:%M:%S')}) {n.content}")
        
        return "\n".join(lines) if found else "No notes found in any scope."

    def commit(self, message: str) -> tuple[str, Event]:
        """Commit current reasoning state."""
        branch = self._get_current_branch()
        messages_snapshot = [m.to_openai_format() for m in branch.messages]
        parent_hash = branch.get_last_commit_hash()
        commit_hash = self._generate_hash(f"{message}{datetime.now().isoformat()}{parent_hash or ''}")

        commit = Commit(
            hash=commit_hash,
            message=message,
            timestamp=datetime.now().isoformat(),
            messages_snapshot=messages_snapshot,
            parent_hash=parent_hash,
        )
        branch.commits.append(commit)

        if branch.messages:
            last_msg = branch.messages[-1]
            if last_msg.role == "assistant" and last_msg.tool_calls:
                pass
            else:
                branch.messages = []

        event = self._emit_event("commit", {
            "message": message,
            "hash": commit_hash,
            "messages_count": len(messages_snapshot),
        })
        self.command_history.append(f"commit -m \"{message}\"")
        return f"[{commit_hash[:7]}] {message}", event

    def checkout(self, branch_name: str, note: str, create: bool = False) -> tuple[str, Event]:
        """Switch scope with transition note."""
        from_branch = self.current_branch
        source_branch = self._get_current_branch()
        pending_messages = []

        if source_branch.messages:
            assistant_msg = None
            assistant_idx = -1
            for i in range(len(source_branch.messages) - 1, -1, -1):
                msg = source_branch.messages[i]
                if msg.role == "assistant" and msg.tool_calls:
                    assistant_msg = msg
                    assistant_idx = i
                    break
            if assistant_msg:
                tool_responses = [m for m in source_branch.messages[assistant_idx + 1:] if m.role == "tool"]
                pending_messages = [assistant_msg] + tool_responses

        if branch_name not in self.branches:
            if create:
                main_branch = self.branches.get("main", source_branch)
                inherited_messages = [
                    Message(role=m.role, content=m.content, 
                            tool_calls=m.tool_calls.copy() if m.tool_calls else None,
                            tool_call_id=m.tool_call_id)
                    for m in main_branch.messages
                ]
                self.branches[branch_name] = Branch(name=branch_name, messages=inherited_messages)
            else:
                return f"error: branch '{branch_name}' does not exist.", None
        
        self.current_branch = branch_name
        target_branch = self._get_current_branch()

        if pending_messages:
            existing_ids = {m.tool_call_id for m in target_branch.messages if m.role == "tool"}
            for msg in pending_messages:
                if msg.role == "assistant" or (msg.role == "tool" and msg.tool_call_id not in existing_ids):
                    target_branch.messages.append(msg)

        if not create:
            target_branch.messages.append(Message(role="assistant", content=f"[Returning from {from_branch}] {note}"))

        target_branch.head_note = f"[From {from_branch}] {note}"
        event = self._emit_event("checkout", {"from_branch": from_branch, "note": note})
        self.command_history.append(f"checkout {branch_name} -m \"{note}\"")
        return f"Switched to branch '{branch_name}'", event

    # ... rest of the methods (tag, log, status, diff, history, stash, merge, etc.) follow similar pattern ...
    def status(self) -> tuple[str, Event]:
        branch = self._get_current_branch()
        lines = [f"On branch: {self.current_branch}", f"Working messages: {len(branch.messages)}", f"Notes: {len(branch.notes)}"]
        return "\n".join(lines), self._emit_event("status", {})

    def add_message(self, message: Message) -> None:
        self._get_current_branch().add_message(message)

    def get_context(self, system_prompt: str | None = None) -> list[dict]:
        return self._get_current_branch().get_messages_for_api(system_prompt)

    def to_dict(self) -> dict:
        return {
            "current_branch": self.current_branch,
            "insights": [i.to_dict() for i in self.insights],
            "branches": {
                name: {
                    "name": b.name,
                    "messages": [m.to_openai_format() for m in b.messages],
                    "notes": [n.to_dict() for n in b.notes],
                    "commits": [c.to_dict() for c in b.commits],
                }
                for name, b in self.branches.items()
            }
        }