"""
Locomo Semantic Benchmark - Testing Global Insight Retention.
"""

import json
import os
import sys
import time
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

def run_locomo_semantic():
    client = OpenAI()
    store = ContextStore()
    model = "gpt-4o-mini"
    
    system_prompt = """You are a software engineer. Use ECM.
    
# COMMANDS
- scope <name> -m "<note>"
- goto <name> -m "<note>"
- note -m "<message>"
- insight -m "<message>"
- notes
- insights

# PLANNING WORKFLOW
1. scope planning -m "objective"
2. insights
3. notes
4. Build plan
5. goto main -m "Summary"
"""

    print("\n--- Phase 1: Injecting Global Insight ---")
    user_1 = "IMPORTANT ARCHITECTURE RULE: In this project, all API endpoints MUST use the '@authenticated' decorator and return JSON only. Record this as a global insight."
    
    ctx = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_1}]
    res = client.chat.completions.create(model=model, messages=ctx, tools=[CTX_CLI_TOOL], temperature=0)
    msg = res.choices[0].message
    
    if msg.tool_calls:
        tc_data = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
        store.add_message(Message(role="assistant", content="", tool_calls=tc_data))
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"      Action: {cmd}")
            res_text, _ = execute_command(store, cmd)
            store.add_message(Message(role="tool", content=res_text, tool_call_id=tc.id))

    print("\n--- Phase 2: Injecting Massive Noise (Context Pollution) ---")
    for i in range(5):
        store.add_message(Message(role="user", content=f"Random talk {i}: How is the weather in Seattle?"))
        store.add_message(Message(role="assistant", content=f"Response {i}: It is probably raining, as usual."))

    print(f"      Current Working Messages in Main: {len(store.branches['main'].messages)}")

    print("\n--- Phase 3: Testing Retention in a New Scope ---")
    user_test = "TASK: Design a new API endpoint for 'GetUserDetails'. Create a planning scope first to ensure you follow all project rules."
    
    store.add_message(Message(role="user", content=user_test))
    ctx_test = store.get_context(system_prompt)
    
    res_test = client.chat.completions.create(model=model, messages=ctx_test, tools=[CTX_CLI_TOOL], temperature=0)
    msg_test = res_test.choices[0].message
    
    if msg_test.tool_calls:
        tc_data = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg_test.tool_calls]
        store.add_message(Message(role="assistant", content=msg_test.content or "", tool_calls=tc_data))
        for tc in msg_test.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"      Step 1: {cmd}")
            res_text, _ = execute_command(store, cmd)
            store.add_message(Message(role="tool", content=res_text, tool_call_id=tc.id))
            
            # Step 2: Second turn in the new scope
            print("      Step 2: Model should now call 'insights'...")
            ctx_step2 = store.get_context(system_prompt)
            res2 = client.chat.completions.create(model=model, messages=ctx_step2, tools=[CTX_CLI_TOOL], temperature=0)
            msg2 = res2.choices[0].message
            
            if msg2.tool_calls:
                tc_data2 = [{"id": tc2.id, "type": "function", "function": {"name": tc2.function.name, "arguments": tc2.function.arguments}} for tc2 in msg2.tool_calls]
                store.add_message(Message(role="assistant", content="", tool_calls=tc_data2))
                for tc2 in msg2.tool_calls:
                    cmd2 = json.loads(tc2.function.arguments)["command"]
                    print(f"      Action: {cmd2}")
                    final_res, _ = execute_command(store, cmd2)
                    print(f"      Output from Insights:\n{final_res}")
                    
                    if "@authenticated" in final_res and "JSON" in final_res:
                        print("\nSUCCESS: Global insight was successfully retrieved despite context noise!")
                    else:
                        print("\nFAILURE: Insight not found or ignored.")

if __name__ == "__main__":
    run_locomo_semantic()