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

    type: Literal["commit", "checkout", "branch", "tag", "log", "status", "diff", "history", "stash", "pop"]
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
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    head_note: str | None = None  # Note from checkout transition

    def get_last_commit_hash(self) -> str | None:
        return self.commits[-1].hash if self.commits else None

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def get_messages_for_api(self, system_prompt: str | None = None) -> list[dict]:
        """Get messages in OpenAI API format."""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        # Add head note if exists (from checkout transition)
        if self.head_note:
            result.append({
                "role": "system",
                "content": f"[TRANSITION NOTE] {self.head_note}"
            })

        # Add commit summaries as context
        if self.commits:
            commit_context = "[EPISODIC MEMORY - Previous commits in this branch]\n"
            for c in self.commits[-5:]:  # Last 5 commits
                commit_context += f"- [{c.hash[:7]}] {c.message}\n"
            result.append({"role": "system", "content": commit_context})

        # Add working messages
        for msg in self.messages:
            result.append(msg.to_openai_format())

        return result


@dataclass
class ContextStore:
    """
    The main context store - manages branches, commits, tags, and events.
    Think of it as the .git directory for LLM context.
    """

    branches: dict[str, Branch] = field(default_factory=dict)
    tags: dict[str, Tag] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    stash: list[StashEntry] = field(default_factory=list)
    current_branch: str = "main"
    command_history: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Always ensure main branch exists
        if "main" not in self.branches:
            self.branches["main"] = Branch(name="main")

    def _generate_hash(self, content: str) -> str:
        """Generate a short hash for commits."""
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

    def commit(self, message: str) -> tuple[str, Event]:
        """
        Commit current reasoning state.
        Saves messages as episodic memory and clears working messages.
        """
        branch = self._get_current_branch()

        # Create commit from current messages
        messages_snapshot = [m.to_openai_format() for m in branch.messages]
        parent_hash = branch.get_last_commit_hash()

        commit_hash = self._generate_hash(
            f"{message}{datetime.now().isoformat()}{parent_hash or ''}"
        )

        commit = Commit(
            hash=commit_hash,
            message=message,
            timestamp=datetime.now().isoformat(),
            messages_snapshot=messages_snapshot,
            parent_hash=parent_hash,
        )

        branch.commits.append(commit)

        # Clear working messages after commit
        branch.messages = []

        # Emit event
        event = self._emit_event("commit", {
            "message": message,
            "hash": commit_hash,
            "messages_count": len(messages_snapshot),
        })

        self.command_history.append(f"commit -m \"{message}\"")

        return f"[{commit_hash[:7]}] {message}", event

    def checkout(self, branch_name: str, note: str, create: bool = False) -> tuple[str, Event]:
        """
        Switch to another branch with a mandatory transition note.
        The note becomes the HEAD of the new branch's context.
        """
        from_branch = self.current_branch

        # Create branch if needed
        if branch_name not in self.branches:
            if create:
                self.branches[branch_name] = Branch(name=branch_name)
            else:
                return f"error: branch '{branch_name}' does not exist. Use -b to create.", None

        # Switch branch
        self.current_branch = branch_name
        target_branch = self._get_current_branch()

        # Set the transition note as HEAD
        target_branch.head_note = f"[From {from_branch}] {note}"

        # Emit event
        event = self._emit_event("checkout", {
            "from_branch": from_branch,
            "note": note,
        })

        self.command_history.append(f"checkout {branch_name} -m \"{note}\"")

        return f"Switched to branch '{branch_name}'", event

    def branch(self, name: str | None = None) -> tuple[str, Event | None]:
        """Create a new branch or list branches."""
        if name is None:
            # List branches
            lines = []
            for b_name, b in self.branches.items():
                prefix = "* " if b_name == self.current_branch else "  "
                commit_count = len(b.commits)
                msg_count = len(b.messages)
                lines.append(f"{prefix}{b_name} ({commit_count} commits, {msg_count} working messages)")

            self.command_history.append("branch")
            return "\n".join(lines), None

        # Create new branch
        if name in self.branches:
            return f"error: branch '{name}' already exists", None

        self.branches[name] = Branch(name=name)

        event = self._emit_event("branch", {
            "name": name,
            "from_branch": self.current_branch,
        })

        self.command_history.append(f"branch {name}")

        return f"Created branch '{name}'", event

    def tag(self, name: str, description: str = "") -> tuple[str, Event]:
        """Create an immutable tag on current commit."""
        branch = self._get_current_branch()
        commit_hash = branch.get_last_commit_hash()

        if not commit_hash:
            return "error: no commits to tag. Make a commit first.", None

        if name in self.tags:
            return f"error: tag '{name}' already exists (tags are immutable)", None

        tag = Tag(
            name=name,
            commit_hash=commit_hash,
            description=description,
            timestamp=datetime.now().isoformat(),
            branch=self.current_branch,
        )

        self.tags[name] = tag

        event = self._emit_event("tag", {
            "name": name,
            "commit_hash": commit_hash,
            "description": description,
        })

        self.command_history.append(f"tag {name}")

        return f"Created tag '{name}' at {commit_hash[:7]}", event

    def log(self, limit: int = 10) -> tuple[str, Event]:
        """Show commit history for current branch."""
        branch = self._get_current_branch()

        if not branch.commits:
            return "No commits yet.", self._emit_event("log", {"commits": []})

        lines = [f"Commit history for '{self.current_branch}':\n"]

        for commit in reversed(branch.commits[-limit:]):
            # Check if this commit has a tag
            tag_names = [t.name for t in self.tags.values() if t.commit_hash == commit.hash]
            tag_str = f" (tag: {', '.join(tag_names)})" if tag_names else ""

            lines.append(f"  [{commit.hash[:7]}]{tag_str} {commit.message}")
            lines.append(f"    {commit.timestamp}")

        self.command_history.append("log")

        return "\n".join(lines), self._emit_event("log", {
            "commits": [c.to_dict() for c in branch.commits[-limit:]]
        })

    def status(self) -> tuple[str, Event]:
        """Show current context status."""
        branch = self._get_current_branch()

        lines = [
            f"On branch: {self.current_branch}",
            f"Working messages: {len(branch.messages)}",
            f"Commits: {len(branch.commits)}",
        ]

        if branch.head_note:
            lines.append(f"Head note: {branch.head_note}")

        if branch.commits:
            last = branch.commits[-1]
            lines.append(f"Last commit: [{last.hash[:7]}] {last.message}")

        # Show stash if any
        if self.stash:
            lines.append(f"Stash: {len(self.stash)} entries")

        self.command_history.append("status")

        return "\n".join(lines), self._emit_event("status", {
            "branch": self.current_branch,
            "messages": len(branch.messages),
            "commits": len(branch.commits),
        })

    def diff(self, other_branch: str) -> tuple[str, Event]:
        """Show difference between current branch and another."""
        if other_branch not in self.branches:
            return f"error: branch '{other_branch}' does not exist", None

        current = self._get_current_branch()
        other = self.branches[other_branch]

        lines = [f"Diff: {self.current_branch} vs {other_branch}\n"]

        lines.append(f"[{self.current_branch}]")
        lines.append(f"  Commits: {len(current.commits)}")
        for c in current.commits[-3:]:
            lines.append(f"    [{c.hash[:7]}] {c.message}")

        lines.append(f"\n[{other_branch}]")
        lines.append(f"  Commits: {len(other.commits)}")
        for c in other.commits[-3:]:
            lines.append(f"    [{c.hash[:7]}] {c.message}")

        self.command_history.append(f"diff {other_branch}")

        return "\n".join(lines), self._emit_event("diff", {
            "other_branch": other_branch,
            "current_commits": len(current.commits),
            "other_commits": len(other.commits),
        })

    def history(self, limit: int = 20) -> tuple[str, Event]:
        """Show recent commands."""
        lines = ["Recent commands:\n"]

        for i, cmd in enumerate(self.command_history[-limit:], 1):
            lines.append(f"  {i}. ctx_cli {cmd}")

        return "\n".join(lines), self._emit_event("history", {
            "commands": self.command_history[-limit:]
        })

    def stash_push(self, message: str = "WIP") -> tuple[str, Event]:
        """Stash current working state."""
        branch = self._get_current_branch()

        if not branch.messages:
            return "Nothing to stash.", None

        stash_id = self._generate_hash(f"stash{datetime.now().isoformat()}")[:8]

        entry = StashEntry(
            id=stash_id,
            message=message,
            timestamp=datetime.now().isoformat(),
            branch=self.current_branch,
            messages=[m.to_openai_format() for m in branch.messages],
            commits=list(branch.commits),
        )

        self.stash.append(entry)
        branch.messages = []

        event = self._emit_event("stash", {
            "message": message,
            "stash_id": stash_id,
        })

        self.command_history.append(f"stash push -m \"{message}\"")

        return f"Saved working directory to stash@{{{stash_id}}}", event

    def stash_pop(self, stash_id: str | None = None) -> tuple[str, Event]:
        """Pop stashed state."""
        if not self.stash:
            return "No stash entries.", None

        # Find entry
        if stash_id:
            entry = next((s for s in self.stash if s.id == stash_id), None)
            if not entry:
                return f"Stash entry '{stash_id}' not found.", None
            self.stash.remove(entry)
        else:
            entry = self.stash.pop()

        # Restore to current branch
        branch = self._get_current_branch()
        branch.messages = [
            Message(
                role=m["role"],
                content=m.get("content", ""),
                tool_call_id=m.get("tool_call_id"),
                tool_calls=m.get("tool_calls"),
                name=m.get("name"),
            )
            for m in entry.messages
        ]

        event = self._emit_event("pop", {"stash_id": entry.id})

        self.command_history.append(f"stash pop {entry.id}")

        return f"Restored stash@{{{entry.id}}} ({entry.message})", event

    def stash_list(self) -> tuple[str, None]:
        """List stash entries."""
        if not self.stash:
            return "No stash entries.", None

        lines = ["Stash entries:\n"]
        for i, entry in enumerate(self.stash):
            lines.append(f"  stash@{{{entry.id}}}: [{entry.branch}] {entry.message}")

        self.command_history.append("stash list")
        return "\n".join(lines), None

    # =========================================================================
    # Context Building
    # =========================================================================

    def add_message(self, message: Message) -> None:
        """Add a message to current branch's working memory."""
        self._get_current_branch().add_message(message)

    def get_context(self, system_prompt: str | None = None) -> list[dict]:
        """Get the current context for API call."""
        return self._get_current_branch().get_messages_for_api(system_prompt)

    def get_token_estimate(self) -> int:
        """Rough estimate of tokens in current context."""
        # Very rough: ~4 chars per token
        context = self.get_context()
        total_chars = sum(len(str(m)) for m in context)
        return total_chars // 4

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """Serialize store to dict."""
        return {
            "current_branch": self.current_branch,
            "branches": {
                name: {
                    "name": b.name,
                    "messages": [m.to_openai_format() for m in b.messages],
                    "commits": [c.to_dict() for c in b.commits],
                    "created_at": b.created_at,
                    "head_note": b.head_note,
                }
                for name, b in self.branches.items()
            },
            "tags": {name: t.to_dict() for name, t in self.tags.items()},
            "events": [e.to_dict() for e in self.events],
            "stash": [
                {
                    "id": s.id,
                    "message": s.message,
                    "timestamp": s.timestamp,
                    "branch": s.branch,
                    "messages": s.messages,
                }
                for s in self.stash
            ],
            "command_history": self.command_history,
        }

    def save(self, path: str) -> None:
        """Save store to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ContextStore":
        """Load store from JSON file."""
        with open(path) as f:
            data = json.load(f)

        store = cls()
        store.current_branch = data["current_branch"]
        store.command_history = data.get("command_history", [])

        # Load branches
        store.branches = {}
        for name, b_data in data["branches"].items():
            branch = Branch(
                name=b_data["name"],
                created_at=b_data["created_at"],
                head_note=b_data.get("head_note"),
            )
            branch.messages = [
                Message(
                    role=m["role"],
                    content=m.get("content", ""),
                    tool_call_id=m.get("tool_call_id"),
                    tool_calls=m.get("tool_calls"),
                    name=m.get("name"),
                )
                for m in b_data["messages"]
            ]
            # Reconstruct commits (without full snapshot for space)
            branch.commits = [
                Commit(
                    hash=c["hash"],
                    message=c["message"],
                    timestamp=c["timestamp"],
                    messages_snapshot=[],  # Not stored in serialized form
                    parent_hash=c.get("parent_hash"),
                )
                for c in b_data["commits"]
            ]
            store.branches[name] = branch

        # Load tags
        for name, t_data in data.get("tags", {}).items():
            store.tags[name] = Tag(
                name=t_data["name"],
                commit_hash=t_data["commit_hash"],
                description=t_data["description"],
                timestamp=t_data["timestamp"],
                branch=t_data["branch"],
            )

        return store
