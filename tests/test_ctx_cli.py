"""Tests for ctx_cli context management."""

import pytest
from datetime import datetime, timezone
from ctx_store import ContextStore, Message
from ctx_cli import execute_command

class TestTieredMemory:
    """Test the new Tiered Memory (Semantic vs Episodic)."""

    def test_insight_storage(self):
        store = ContextStore()
        msg = "Architecture rule: use safe_save()"
        result, event = store.insight(msg)
        
        assert "Global insight recorded" in result
        assert len(store.insights) == 1
        assert store.insights[0].content == msg
        assert isinstance(store.insights[0].timestamp, datetime)

    def test_get_insights_git_format(self):
        store = ContextStore()
        store.insight("Rule 1")
        output = store.get_insights()
        
        assert "[SEMANTIC MEMORY - Global Insights]" in output
        assert "Date:" in output
        assert "Rule 1" in output

    def test_notes_grouping_by_day(self):
        store = ContextStore()
        # Mocking different days is complex, let's at least test same-day grouping
        store.note("First event")
        store.note("Second event")
        
        output = store.get_all_notes()
        assert "EPISODIC MEMORY - Journal" in output
        # Should have one "Date:" line for both since they are seconds apart
        assert output.count("Date:") == 1
        assert "First event" in output
        assert "Second event" in output

    def test_pull_based_memory_isolation(self):
        """Verify that notes are NOT automatically injected into the API context."""
        store = ContextStore()
        store.add_message(Message(role="user", content="hello"))
        store.note("Secret technical detail")
        
        ctx = store.get_context("System prompt")
        # Context should contain only System + User message, no notes
        assert len(ctx) == 2
        assert ctx[0]["role"] == "system"
        assert ctx[1]["content"] == "hello"
        assert not any("Secret technical detail" in str(m) for m in ctx)

class TestGitStyleCLI:
    """Test the CLI commands with new Git-style features."""

    def test_notes_global_vs_local(self):
        store = ContextStore()
        store.checkout("scope-a", "starting a", create=True)
        store.note("note in a")
        
        store.checkout("scope-b", "starting b", create=True)
        store.note("note in b")
        
        # Test Global Pull
        global_output, _ = execute_command(store, "notes")
        assert "note in a" in global_output
        assert "note in b" in global_output
        
        # Test Local Pull
        local_output, _ = execute_command(store, "notes scope-a")
        assert "note in a" in local_output
        assert "note in b" not in local_output

    def test_insight_cli(self):
        store = ContextStore()
        res, _ = execute_command(store, 'insight -m "Global Fact"')
        assert "Global insight recorded" in res
        
        insights_res, _ = execute_command(store, "insights")
        assert "Global Fact" in insights_res

    def test_scope_with_namespaces(self):
        store = ContextStore()
        res, _ = execute_command(store, 'scope plan/my-task -m "thinking"')
        assert "Switched to branch 'plan/my-task'" in res
        assert store.current_branch == "plan/my-task"

def test_git_date_format_precision():
    """Verify the exact Git date format: Day Mon DD HH:MM:SS YYYY ZZZZ"""
    store = ContextStore()
    store.note("test")
    output = store.get_all_notes()
    
    # Example: Fri Jan 02 14:30:00 2026 -0300
    # We check for the presence of the GMT offset (the 4 digits at the end)
    import re
    # Matches +0000 or -0300 etc at the end of the date line
    assert re.search(r"Date:   \w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2} \d{4} [+-]\d{4}", output)