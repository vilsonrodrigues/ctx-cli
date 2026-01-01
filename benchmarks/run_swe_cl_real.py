#!/usr/bin/env python3
import argparse, json, os, subprocess, sys, tempfile, time, datetime, threading
from typing import Literal
from openai import OpenAI
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker
from prompts import SYSTEM_PROMPT_ECM, SYSTEM_PROMPT_LINEAR

# Tools Configuration
BASH_TOOL = {"type": "function", "function": {"name": "bash", "description": "Execute bash command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
READ_FILE_TOOL = {"type": "function", "function": {"name": "read_file", "description": "Read file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
WRITE_FILE_TOOL = {"type": "function", "function": {"name": "write_file", "description": "Write file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}}
LIST_FILES_TOOL = {"type": "function", "function": {"name": "list_files", "description": "List files.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}}}

def execute_tool_demo(tool_name, args, workdir):
    try:
        if tool_name == "bash":
            result = subprocess.run(args["command"], shell=True, capture_output=True, text=True, timeout=60, cwd=workdir)
            return (result.stdout + result.stderr)[:4000] or "(no output)"
        elif tool_name == "read_file":
            p = os.path.join(workdir, args["path"])
            with open(p) as f: return f.read()[:8000]
        elif tool_name == "write_file":
            p = os.path.join(workdir, args["path"])
            os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) else None
            with open(p, "w") as f: f.write(args["content"])
            return f"Written {len(args['content'])} bytes"
        elif tool_name == "list_files":
            p = os.path.join(workdir, args.get("path", "."))
            return "\n".join(os.listdir(p)) if os.path.exists(p) else "Not found"
        return f"Unknown tool: {tool_name}"
    except Exception as e: return f"Error: {str(e)}"

def run_benchmark(client, model, tasks, repo, workdir, approach: Literal["linear", "scope"]):
    print(f"\n--- Running {approach.upper()} approach ---", flush=True)
    store = ContextStore() if approach == "scope" else None
    sys_prompt = SYSTEM_PROMPT_ECM if approach == "scope" else SYSTEM_PROMPT_LINEAR
    linear_msgs = [{"role": "system", "content": sys_prompt}]
    task_results = []
    turn_by_turn_metrics = []
    
    for i, task in enumerate(tasks):
        instance_id = task["metadata"]["instance_id"]
        print(f"\n[Task {i+1}/{len(tasks)}] {instance_id}", flush=True)
        done = False
        
        user_msg = f"TASK {i+1}: {task['task']['problem_statement']}"
        if approach == "scope": store.add_message(Message(role="user", content=user_msg))
        else: linear_msgs.append({"role": "user", "content": user_msg})
        
        for turn in range(15):
            if done: break
            ctx = store.get_context(sys_prompt) if approach == "scope" else linear_msgs
            print(f"      T{turn+1:02d} API call...", end="", flush=True)
            
            t0 = time.time()
            tools_to_use = [BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL]
            if approach == "scope": tools_to_use.append(CTX_CLI_TOOL)
            
            try:
                res = client.chat.completions.create(model=model, messages=ctx, tools=tools_to_use, temperature=0, max_tokens=4000)
            except Exception as e:
                print(f" API Error: {e}", flush=True)
                break
                
            lat = time.time() - t0
            msg = res.choices[0].message
            in_t = res.usage.prompt_tokens if res.usage else 0
            out_t = res.usage.completion_tokens if res.usage else 0
            
            turn_by_turn_metrics.append({"task_idx": i, "turn_idx": turn, "input_tokens": in_t, "output_tokens": out_t, "latency": lat})
            print(f" done (in={in_t}, out={out_t})", flush=True)
            
            if approach == "scope":
                tc_data = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in (msg.tool_calls or [])]
                store.add_message(Message(role="assistant", content=msg.content or "", tool_calls=tc_data))
            else:
                m_dict = msg.model_dump()
                linear_msgs.append({k: v for k, v in m_dict.items() if v is not None})
            
            if not msg.tool_calls: break
            for tc in msg.tool_calls:
                name = tc.function.name
                try: args = json.loads(tc.function.arguments)
                except: r = "Error: JSON"
                else:
                    print(f"      [{name}]", end="", flush=True)
                                    if name == "ctx_cli" and approach == "scope":
                                        cmd = args.get("command", "")
                                        print(f"      [ctx_cli] {cmd[:50]}...", end="", flush=True)
                                        r, _ = execute_command(store, cmd)
                                        if "goto main" in cmd: done = True
                                        print(f" ok", flush=True)
                    
                if approach == "scope": store.add_message(Message(role="tool", content=r, tool_call_id=tc.id))
                else: linear_msgs.append({"role": "tool", "content": r, "tool_call_id": tc.id})
                
        task_results.append({"id": instance_id, "final_in": in_t})
    return {"tasks": task_results, "turns": turn_by_turn_metrics}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approach", choices=["linear", "scope", "both"], default="scope")
    parser.add_argument("--tasks", type=int, default=15)
    args = parser.parse_args()

    data = json.load(open("benchmarks/data/swe-bench-cl.json"))
    seq = next(s for s in data["sequences"] if "django" in s["repo"])
    tasks = seq["tasks"][:args.tasks]
    client = OpenAI()
    
    results = {"repo": seq["repo"]}
    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = setup_repo(seq["repo"], tasks[0]["metadata"]["base_commit"], tmp)
        
        if args.approach in ["linear", "both"]:
            results["linear"] = run_benchmark(client, "gpt-4o-mini", tasks, seq["repo"], repo_dir, "linear")
        
        if args.approach in ["scope", "both"]:
            results["scope"] = run_benchmark(client, "gpt-4o-mini", tasks, seq["repo"], repo_dir, "scope")
        
    out_path = f"benchmarks/results/swe_cl_{args.approach}_{datetime.datetime.now().strftime('%H%M%S')}.json"
    os.makedirs("benchmarks/results", exist_ok=True)
    json.dump(results, open(out_path, "w"), indent=2)
    print(f"\nSaved to {out_path}")

def setup_repo(repo, commit, workdir):
    d = os.path.join(workdir, repo.replace("/", "_"))
    if not os.path.exists(d): subprocess.run(f"git clone https://github.com/{repo}.git {d}", shell=True, capture_output=True)
    subprocess.run(f"git checkout -f {commit}", shell=True, cwd=d, capture_output=True)
    return d

if __name__ == "__main__": main()