
import pytest
from ctx_store import ContextStore, Message
from ctx_cli import execute_command

class TestECMRules:
    """Tests for the Enforced Context Management (ECM) rules."""

    def test_prevent_nested_scope_creation(self):
        """Rule: One cannot create a new scope from within a non-main scope."""
        store = ContextStore()
        
        # 1. Start in a valid scope
        store.execute_tool_call("call_1", 'scope task-1 -m "start"')
        assert store.current_branch == "task-1"
        
        # 2. Try to create nested scope
        result = store.execute_tool_call("call_2", 'scope task-2 -m "nested attempt"')
        
        # 3. Assert failure and guidance
        assert "ERROR" in result
        assert "return" in result.lower()
        assert store.current_branch == "task-1" # Should not have moved
        
    def test_prevent_reopening_finalized_scope(self):
        """Rule: A finalized scope cannot be reopened."""
        store = ContextStore()
        
        # 1. Create and finish task-1
        store.execute_tool_call("call_1", 'scope task-1 -m "start"')
        store.execute_tool_call("call_2", 'return -m "done"')
        assert store.branches["task-1"].finalized is True
        
        # 2. Try to reopen task-1
        result = store.execute_tool_call("call_3", 'scope task-1 -m "reopen"')
        
        # 3. Assert failure
        assert "ERROR" in result
        assert "finalized" in result.lower()
        assert store.current_branch == "main"
        
    def test_note_persistence_on_return(self):
        """Rule: Notes in return command should be accessible in main."""
        store = ContextStore()
        store.execute_tool_call("call_1", 'scope task-1 -m "start"')
        
        # Return with a summary note
        summary = "Key insight for main"
        store.execute_tool_call("call_2", f'return -m "{summary}"')
        
        # Assert main has the note (either as a Note object or in the Return message)
        # In current implementation, return -m adds a Note AND a message.
        
        # Check messages
        last_msg = store.branches["main"].messages[-1]
        assert summary in last_msg.content
        
        # Check notes list (if implemented usage of Note objects in return_to_main)
        # Let's check store notes or branch notes
        # return_to_main: "if note: main_branch.notes.append(Note...)"
        main_notes = store.branches["main"].notes
        assert len(main_notes) > 0
        assert summary in main_notes[-1].content

    def test_compound_execution_order(self):
        """Test multiple commands executing in order: note then return."""
        store = ContextStore()
        store.execute_tool_call("call_1", 'scope task-1 -m "start"')
        
        # Execute note THEN return
        # note should go to task-1, return should verify task-1 is done
        store.execute_tool_call("call_2", 'note -m "detail before exit"; return -m "exiting"')
        
        # Verify task-1 has the note
        task1_msgs = store.branches["task-1"].messages
        # We need to find the note tool response or the assistant call
        # execute_tool_call logic adds assistant msg to... wait.
        # If "return" is in command, start_branch = main.
        # So assistant msg (with both commands) goes to MAIN.
        
        # But execution of "note" happens.
        # "note" command output?
        # execute_command splits and runs. "note" usually adds a message to current scope OR returns string.
        # "note" command: returns string "Note recorded...".
        # It does NOT verify adding a message to scope explicitly unless harness does it.
        # BUT harness adds ONE tool response with aggregated result.
        
        # Since start_branch=main (due to return), and final_branch=main.
        # The tool response (containing "Note recorded" + "Returned") goes to MAIN.
        
        # DOES task-1 get the note?
        # "note" command implementation logic:
        # It appends to current_branch.notes list?
        task1_notes = store.branches["task-1"].notes
        assert any("detail before exit" in n.content for n in task1_notes)
        
        # Verify status
        assert store.current_branch == "main"
        assert store.branches["task-1"].finalized is True

    def test_idempotent_return_from_main(self):
        """Rule: returning from main should be safe/no-op."""
        store = ContextStore()
        assert store.current_branch == "main"
        
        result = store.execute_tool_call("call_1", 'return -m "already home"')
        
        assert "Already in main" in result
        assert store.current_branch == "main"
