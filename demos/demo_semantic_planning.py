"""
Demo: Semantic Planning Workflow.
This demo shows how the agent uses 'insights' (Semantic Memory) 
to inform planning in a new isolated scope.
"""

import json
import os
import sys
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

def run_semantic_demo():
    client = OpenAI()
    store = ContextStore()
    model = "gpt-4o-mini"
    
    system_prompt = """You are a software engineer. Use ECM.
    
# COMMANDS (Pass ONLY the command string to ctx_cli)
- scope <name> -m "<note>"
- goto <name> -m "<note>"
- note -m "<message>"
- insight -m "<message>"
- notes
- insights

# WORKFLOW
To plan complex tasks:
1. scope planning -m "objective"
2. insights (check global facts)
3. notes (check history)
4. Build plan
5. goto main -m "Summary of plan"
"""

    print("\n=== Phase 1: Knowledge Discovery ===")
    user_1 = "Explore the codebase. You'll find that all database models must inherit from 'BaseModel' and use 'self.safe_save()' instead of 'save()'. Record this as a global insight."
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_1}]
    
    # Discovery Turn
    res = client.chat.completions.create(model=model, messages=messages, tools=[CTX_CLI_TOOL])
    msg = res.choices[0].message
    print(f"Assistant: {msg.content or '(tool call)'}")
    
    if msg.tool_calls:
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"Executing: {cmd}")
            result, _ = execute_command(store, cmd)
            print(f"Result: {result}")
            store.add_message(Message(role="assistant", content=msg.content or "", tool_calls=[tc.model_dump()]))
            store.add_message(Message(role="tool", content=result, tool_call_id=tc.id))

    print("\n=== Phase 2: Planning with Semantic Memory ===")
    user_2 = "TASK: Create a new 'User' model. Follow the architecture rules discovered earlier. Start by creating a planning scope to review your insights."
    
    # Get clean context from store (working memory was reset by the store logic if we used scope/goto)
    ctx = store.get_context(system_prompt)
    ctx.append({"role": "user", "content": user_2})
    
    # Planning Turn
    res = client.chat.completions.create(model=model, messages=ctx, tools=[CTX_CLI_TOOL])
    msg = res.choices[0].message
    print(f"Assistant: {msg.content or '(tool call)'}")
    
    if msg.tool_calls:
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"Executing: {cmd}")
            result, _ = execute_command(store, cmd)
            print(f"Result: {result}")
            # Here the agent would typically call 'insights' next in the new scope
            
    print("\nDemo finished. Check how the agent naturally uses the new commands.")

if __name__ == "__main__":
    run_semantic_demo()
