import json, os, sys, time
from openai import OpenAI

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from prompts import SYSTEM_PROMPT_ECM

def run():
    client = OpenAI()
    store = ContextStore()
    model = "gpt-4o-mini"
    
    print("\n=== PHASE 1: INSTRUCTION ===", flush=True)
    rule = "CRITICAL RULE: All database timestamps must be stored in UTC, but displayed in 'America/New_York' timezone. Never use naive datetimes."
    store.add_message(Message(role="user", content=f"Golden rule: {rule}. Save this as an insight."))
    
    # Save insight
    res = client.chat.completions.create(model=model, messages=store.get_context(SYSTEM_PROMPT_ECM), tools=[CTX_CLI_TOOL], temperature=0)
    msg = res.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"      Action: {cmd}", flush=True)
            res_text, _ = execute_command(store, cmd)
            store.add_message(Message(role="assistant", content=msg.content or "", tool_calls=[tc.model_dump()]))
            store.add_message(Message(role="tool", content=res_text, tool_call_id=tc.id))

    print("\n=== PHASE 2: DISTRACTION (Massive Noise) ===", flush=True)
    for i in range(5):
        store.add_message(Message(role="user", content=f"Noise {i}"))
        store.add_message(Message(role="assistant", content=f"Reply {i}"))

    print("\n=== PHASE 3: RECALL ===", flush=True)
    store.add_message(Message(role="user", content="Task: Create a timestamp function log_event(). Use planning scope first."))
    
    # Step 1: Planning
    res = client.chat.completions.create(model=model, messages=store.get_context(SYSTEM_PROMPT_ECM), tools=[CTX_CLI_TOOL], temperature=0)
    msg = res.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"      Step 1 Action: {cmd}", flush=True)
            res_text, _ = execute_command(store, cmd)
            store.add_message(Message(role="assistant", content="", tool_calls=[tc.model_dump()]))
            store.add_message(Message(role="tool", content=res_text, tool_call_id=tc.id))

    # Step 2: Retrieval
    res = client.chat.completions.create(model=model, messages=store.get_context(SYSTEM_PROMPT_ECM), tools=[CTX_CLI_TOOL], temperature=0)
    msg = res.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            print(f"      Step 2 Action: {cmd}", flush=True)
            res_text, _ = execute_command(store, cmd)
            print(f"      Memory Output:\n{res_text}", flush=True)
            
            if "UTC" in res_text and "America/New_York" in res_text:
                print("\n>>> SUCCESS!", flush=True)
            else:
                print("\n>>> FAILURE!", flush=True)

if __name__ == "__main__": run()
