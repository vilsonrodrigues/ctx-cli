"""Tests for ctx_cli context management."""

import pytest
from ctx_store import ContextStore, Message
from ctx_cli import parse_command, execute_command


class TestParseCommand:
    """Test command parsing."""

    def test_parse_commit(self):
        result = parse_command('commit -m "test message"')
        assert result.action == "commit"
        assert result.args["message"] == "test message"

    def test_parse_commit_missing_message(self):
        result = parse_command("commit")
        assert result.action == "error"
        assert "requires -m" in result.error

    def test_parse_checkout_with_create(self):
        result = parse_command('checkout -b new-branch -m "going to do X"')
        assert result.action == "checkout"
        assert result.args["branch"] == "new-branch"
        assert result.args["note"] == "going to do X"
        assert result.args["create"] is True

    def test_parse_checkout_existing(self):
        result = parse_command('checkout main -m "back to main"')
        assert result.action == "checkout"
        assert result.args["branch"] == "main"
        assert result.args["create"] is False

    def test_parse_checkout_missing_note(self):
        result = parse_command("checkout some-branch")
        assert result.action == "error"
        assert "note is mandatory" in result.error

    def test_parse_branch_list(self):
        result = parse_command("branch")
        assert result.action == "branch"
        assert result.args["name"] is None

    def test_parse_branch_create(self):
        result = parse_command("branch feature-x")
        assert result.action == "branch"
        assert result.args["name"] == "feature-x"

    def test_parse_tag(self):
        result = parse_command('tag v1 -m "first version"')
        assert result.action == "tag"
        assert result.args["name"] == "v1"
        assert result.args["description"] == "first version"

    def test_parse_tag_no_description(self):
        result = parse_command("tag v2")
        assert result.action == "tag"
        assert result.args["name"] == "v2"
        assert result.args["description"] == ""

    def test_parse_log(self):
        result = parse_command("log")
        assert result.action == "log"

    def test_parse_status(self):
        result = parse_command("status")
        assert result.action == "status"

    def test_parse_diff(self):
        result = parse_command("diff other-branch")
        assert result.action == "diff"
        assert result.args["branch"] == "other-branch"

    def test_parse_history(self):
        result = parse_command("history")
        assert result.action == "history"

    def test_parse_stash_push(self):
        result = parse_command('stash push -m "work in progress"')
        assert result.action == "stash"
        assert result.args["subaction"] == "push"
        assert result.args["message"] == "work in progress"

    def test_parse_stash_pop(self):
        result = parse_command("stash pop")
        assert result.action == "stash"
        assert result.args["subaction"] == "pop"

    def test_parse_stash_list(self):
        result = parse_command("stash list")
        assert result.action == "stash"
        assert result.args["subaction"] == "list"


class TestContextStore:
    """Test ContextStore operations."""

    def test_initial_state(self):
        store = ContextStore()
        assert store.current_branch == "main"
        assert "main" in store.branches
        assert len(store.events) == 0

    def test_add_message(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="hello"))
        branch = store.branches["main"]
        assert len(branch.messages) == 1
        assert branch.messages[0].content == "hello"

    def test_commit(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.add_message(Message(role="assistant", content="response"))

        result, event = store.commit("Test commit")

        assert "Test commit" in result
        assert event.type == "commit"
        assert event.payload["message"] == "Test commit"

        # Messages should be cleared
        branch = store.branches["main"]
        assert len(branch.messages) == 0
        assert len(branch.commits) == 1
        assert branch.commits[0].message == "Test commit"

    def test_checkout_new_branch(self):
        store = ContextStore()
        result, event = store.checkout("feature", "Starting feature work", create=True)

        assert store.current_branch == "feature"
        assert "feature" in store.branches
        assert event.type == "checkout"
        assert event.payload["from_branch"] == "main"

        # Check head note is set
        branch = store.branches["feature"]
        assert "Starting feature work" in branch.head_note

    def test_checkout_nonexistent_without_create(self):
        store = ContextStore()
        result, event = store.checkout("nonexistent", "note", create=False)

        assert "does not exist" in result
        assert event is None
        assert store.current_branch == "main"

    def test_tag(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("Initial commit")

        result, event = store.tag("v1", "Version 1")

        assert "v1" in result
        assert event.type == "tag"
        assert "v1" in store.tags
        assert store.tags["v1"].description == "Version 1"

    def test_tag_without_commit(self):
        store = ContextStore()
        result, event = store.tag("v1", "No commits yet")

        assert "no commits" in result.lower()
        assert event is None

    def test_tag_immutable(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("Initial")
        store.tag("v1", "First")

        result, event = store.tag("v1", "Second attempt")

        assert "already exists" in result
        assert event is None

    def test_log(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("First")
        store.add_message(Message(role="user", content="more"))
        store.commit("Second")

        result, event = store.log()

        assert "First" in result
        assert "Second" in result
        assert event.type == "log"

    def test_status(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))

        result, event = store.status()

        assert "main" in result
        assert "1" in result  # 1 working message
        assert event.type == "status"

    def test_diff(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("Main commit")

        store.checkout("feature", "New feature", create=True)
        store.add_message(Message(role="user", content="feature work"))
        store.commit("Feature commit")

        result, event = store.diff("main")

        assert "main" in result
        assert "feature" in result
        assert event.type == "diff"

    def test_stash_and_pop(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test1"))
        store.add_message(Message(role="user", content="test2"))

        result, event = store.stash_push("WIP")

        assert "stash" in result.lower()
        assert len(store.branches["main"].messages) == 0
        assert len(store.stash) == 1

        result, event = store.stash_pop()

        assert len(store.branches["main"].messages) == 2
        assert len(store.stash) == 0

    def test_history(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("First")
        store.checkout("feat", "Feature", create=True)

        result, event = store.history()

        assert "commit" in result
        assert "checkout" in result

    def test_get_context(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("First commit")
        store.add_message(Message(role="user", content="second"))

        context = store.get_context("You are helpful.")

        # Should have: system prompt, episodic memory, user message
        assert len(context) >= 3
        assert context[0]["role"] == "system"
        assert "helpful" in context[0]["content"]

    def test_get_context_with_head_note(self):
        store = ContextStore()
        store.checkout("feature", "Working on feature X", create=True)
        store.add_message(Message(role="user", content="test"))

        context = store.get_context("System")

        # Should contain transition note
        has_transition = any("TRANSITION NOTE" in str(m) for m in context)
        assert has_transition


class TestExecuteCommand:
    """Test command execution."""

    def test_execute_commit(self):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))

        result, event = execute_command(store, 'commit -m "Test message"')

        assert "Test message" in result
        assert event is not None
        assert len(store.branches["main"].commits) == 1

    def test_execute_checkout(self):
        store = ContextStore()

        result, event = execute_command(store, 'checkout -b feature -m "New feature"')

        assert store.current_branch == "feature"
        assert event is not None

    def test_execute_invalid_command(self):
        store = ContextStore()

        result, event = execute_command(store, "invalid-command")

        assert "Unknown command" in result
        assert event is None


class TestSerialization:
    """Test save/load functionality."""

    def test_save_and_load(self, tmp_path):
        store = ContextStore()
        store.add_message(Message(role="user", content="test"))
        store.commit("First commit")
        store.tag("v1", "Version 1")  # Tag before checkout (main has commits)
        store.checkout("feature", "Feature branch", create=True)

        # Save
        path = tmp_path / "state.json"
        store.save(str(path))

        # Load
        loaded = ContextStore.load(str(path))

        assert loaded.current_branch == "feature"
        assert "main" in loaded.branches
        assert "feature" in loaded.branches
        assert "v1" in loaded.tags
        assert len(loaded.branches["main"].commits) == 1
