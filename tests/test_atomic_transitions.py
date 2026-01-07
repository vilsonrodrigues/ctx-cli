
import pytest
from ctx_store import ContextStore, Message
from ctx_cli import execute_command

class TestAtomicTransitions:
    """Test atomic transitions (return + scope) and harness logic."""

    def test_execute_tool_call_compound_return_scope(self):
        """Test 'return; scope' chained command using execute_tool_call harness."""
        store = ContextStore()
        
        # Setup: Start in a scope
        store.checkout("task-1", "starting task 1", create=True)
        assert store.current_branch == "task-1"
        
        # Add some history to task-1
        store.add_message(Message(role="user", content="do something"))
        store.add_message(Message(role="assistant", content="doing it"))
        
        # Execute atomic transition: return to main AND start task-2
        # This simulates what the LLM does: one tool call with multiple commands
        tool_call_id = "call_123"
        command = 'return -m "task 1 done"; scope task-2 -m "starting task 2"'
        
        result = store.execute_tool_call(
            tool_call_id=tool_call_id,
            command=command,
            assistant_content="Finished task 1, moving to task 2"
        )
        
        # 1. Verify we ended up in task-2
        assert store.current_branch == "task-2"
        
        # 2. Verify task-1 is finalized
        assert store.branches["task-1"].finalized is True
        
        # 3. Verify main branch state
        main_msgs = store.branches["main"].messages
        # Should contain:
        # - Initial Checkout (assistant + tool) from task-1 creation? 
        #   (Wait, checkout doesn't add msgs to main unless requested? checkout adds to main only if it was in main... wait.
        #    checkout from main adds msgs to new scope, not main. 
        #    But the checkout command itself was run? 
        #    Let's check setup again. 'store.checkout("task-1")' adds NO messages to main if called programmatically?
        #    Ah, store.checkout returns (str, event). It doesn't auto-add messages unless via execute_tool_call.
        #    In setup we called checkout directly. So main is empty of messages initially.)
        
        # The atomic transition added:
        # - 1 assistant msg (the compound command)
        # - 1 tool response (the compound result)
        assert len(main_msgs) == 2
        assert main_msgs[-2].role == "assistant"
        assert main_msgs[-1].role == "tool"
        assert main_msgs[-1].tool_call_id == tool_call_id
        
        # 4. Verify task-2 state (CRITICAL VALIDATION)
        task2_msgs = store.branches["task-2"].messages
        
        # task-2 should inherit from main.
        # Since main has the assistant msg for the compound command...
        # AND the tool response was added to main AFTER execution...
        # Does task-2 have the tool response?
        
        tool_response_in_task2 = any(
            m.role == "tool" and m.tool_call_id == tool_call_id 
            for m in task2_msgs
        )
        
        # If this fails, we have the "orphan tool call" issue in the new scope
        if not tool_response_in_task2:
             # Check if it has the assistant message
             has_assistant = any(
                 m.role == "assistant" and tool_call_id in str(m.tool_calls)
                 for m in task2_msgs
             )
             if has_assistant:
                 pytest.fail("task-2 has the assistant tool_call but missing the tool_response! Invalid state.")

    def test_simple_return_harness(self):
        """Test simple 'return' command using harness."""
        store = ContextStore()
        store.checkout("task-a", "start", create=True)
        
        tool_id = "call_ret"
        store.execute_tool_call(tool_id, 'return -m "done"')
        
        assert store.current_branch == "main"
        assert store.branches["task-a"].finalized is True
        
        # Check main has the interaction
        assert len(store.branches["main"].messages) == 2
        assert store.branches["main"].messages[-1].tool_call_id == tool_id

