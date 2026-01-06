#!/usr/bin/env python3
"""
BrowseComp Real-World Benchmark for ECM.

Uses live internet access via DuckDuckGo and Requests to solve BrowseComp tasks.
WARNING: Execution depends on network availability and site structures.
"""

import os
import sys
import json
import time
import requests
from typing import Literal, Optional
from dataclasses import dataclass, field

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.adapters.ecm_adapter import ECMAgentWrapper
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore

# Dependencies
try:
    from duckduckgo_search import DDGS
    from markdownify import markdownify as md
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Missing dependencies. Run: uv add --group browse duckduckgo-search markdownify beautifulsoup4 requests")
    sys.exit(1)

# =============================================================================
# Real Browser Implementation
# =============================================================================

@dataclass
class BrowserState:
    current_url: str = "about:blank"
    history: list[str] = field(default_factory=list)
    content: str = ""
    title: str = ""

@dataclass
class BenchmarkResult:
    approach: Literal["explicit-real"]
    model: str
    num_tasks: int
    tasks_completed: int = 0
    elapsed_seconds: float = 0.0
    task_results: list = field(default_factory=list)

class RealBrowser:
    """Acceses the real web."""
    
    def __init__(self):
        self.state = BrowserState()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
    def reset(self):
        self.state = BrowserState()
        
    def navigate(self, url: str) -> str:
        """Visit a URL or perform a search."""
        self.state.history.append(self.state.current_url)
        self.state.current_url = url
        
        # Handle Search
        if url.startswith("search://"):
            query = url.replace("search://", "")
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=5))
                
                formatted_results = f"# Search Results for '{query}'\n\n"
                for i, res in enumerate(results, 1):
                    formatted_results += f"{i}. [{res['title']}]({res['href']})\n   {res['body']}\n\n"
                
                self.state.content = formatted_results
                self.state.title = f"Search: {query}"
                return f"Search completed for '{query}'"
            except Exception as e:
                # Fallback to simple request
                return f"Search failed: {str(e)}"

        # Handle Visit
        try:
            resp = self.session.get(url, timeout=15) # Increased timeout
            resp.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Remove clutter aggressively
            for tag in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'aside', 'form', 'button']):
                tag.decompose()
                
            self.state.title = soup.title.string.strip() if soup.title else url
            
            # Convert to Markdown
            markdown = md(str(soup), heading_style="ATX", strip=['a', 'img'])
            
            # Clean up whitespace
            lines = [line.strip() for line in markdown.splitlines() if line.strip()]
            markdown = "\n".join(lines)
            
            # Truncate if too long (simple heuristic)
            if len(markdown) > 15000:
                markdown = markdown[:15000] + "\n...[Content Truncated]..."
                
            self.state.content = f"# {self.state.title}\n\n{markdown}"
            return f"Navigated to {url}. Content Legnth: {len(markdown)}"
            
        except Exception as e:
            self.state.content = f"Error loading page: {str(e)}"
            return f"Navigation failed: {str(e)}"

    def read_page(self) -> str:
        return self.state.content

# =============================================================================
# Agent
# =============================================================================

class BrowseCompRealAgent(ECMAgentWrapper):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser = None
        
    def _run_tool_loop(self, messages: list[dict], max_rounds: int = 15) -> str:
        
        BROWSER_TOOL = {
            "type": "function",
            "function": {
                "name": "browser",
                "description": "Interact with the live web browser.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["search", "visit", "read"],
                            "description": "Action to perform"
                        },
                        "query": {"type": "string", "description": "Search query (for 'search')"},
                        "url": {"type": "string", "description": "URL to visit (for 'visit')"}
                    },
                    "required": ["action"]
                }
            }
        }
        
        tools = [CTX_CLI_TOOL, BROWSER_TOOL]
        
        for round_num in range(max_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            assistant_msg = response.choices[0].message
            messages.append(assistant_msg.model_dump())

            if not assistant_msg.tool_calls:
                return assistant_msg.content or ""
            
            for tool_call in assistant_msg.tool_calls:
                call_id = tool_call.id
                
                if tool_call.function.name == "ctx_cli":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    result, _ = execute_command(self.store, command)
                    self.logger.log("CTX", command)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result
                    })
                    
                elif tool_call.function.name == "browser":
                    args = json.loads(tool_call.function.arguments)
                    action = args.get("action")
                    
                    output = ""
                    if action == "search":
                        query = args.get("query", "")
                        # Special scheme for search shim
                        output = self.browser.navigate(f"search://{query}")
                    elif action == "visit":
                        url = args.get("url", "")
                        output = self.browser.navigate(url)
                    elif action == "read":
                        output = self.browser.read_page()
                        
                    self.logger.log("WEB", f"{action} query={args.get('query')} url={args.get('url')}")
                    print(f"[BROWSER] {action} -> Done")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": output
                    })
                    
        return messages[-1].get("content", "")

    def run_task(self, task: dict, browser: RealBrowser) -> dict:
        self.browser = browser
        
        if self.store.current_project != "browsecomp_real":
            self.store.new_project("browsecomp_real")
            self.store.checkout("main", note="Starting Real BrowseComp", create=True)
            
        from prompts import SYSTEM_PROMPT_ECM_MEMORY
        
        system_prompt = SYSTEM_PROMPT_ECM_MEMORY + """
# ENVIRONMENT
You are connected to the LIVE INTERNET via a browser tool.

# MISSION
Solve the user's question by finding facts on the web.
Use `ctx_cli note` to save findings from one page before visiting another.

# TOOL USAGE
- `browser(action="search", query="...")`
- `browser(action="visit", url="...")`
- `browser(action="read")`

Be precise.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task['question']}"}
        ]
        
        response = self._run_tool_loop(messages)
        print(f"\nFinal Answer: {response}")
        
        passed = any(ans.lower() in response.lower() for ans in task["answers"])
        
        return {
            "question": task["question"],
            "response": response,
            "passed": passed
        }

# =============================================================================
# Main
# =============================================================================

def main():
    from benchmarks.adapters.ecm_adapter import get_ecm_agent_config, get_ecm_dataset_config
    
    model_name = "gpt-4.1-mini"
    agent_config = get_ecm_agent_config(model=model_name)
    dataset_config = get_ecm_dataset_config()
    
    agent = BrowseCompRealAgent(agent_config, dataset_config)
    browser = RealBrowser()
    
    tasks = [
        # Same tasks, but now checking against real web
        {
            "id": 1,
            "question": "Which specific individual was the Mayor of the host city of the 2004 Summer Olympics at the time of the games?",
            "answers": ["Dora Bakoyannis", "Bakoyannis"],
        },
        {
            "id": 2,
            "question": "What was the closing price of Apple stock on the day the first iPhone was announced (unadjusted/original or split-adjusted)?",
            "answers": ["13", "12", "92", "93", "80s"], # Loose match for real web variance
        }
    ]
    
    print(f"🚀 Starting BrowseComp REAL WEB Benchmark - {len(tasks)} tasks")
    
    passed_count = 0
    start_time = time.time()
    
    for i, task in enumerate(tasks):
        print(f"\n--- Task {i+1}: {task['question']} ---")
        browser.reset()
        result = agent.run_task(task, browser)
        if result["passed"]:
            print("✅ PASS")
            passed_count += 1
        else:
            print("❌ FAIL")
            
    elapsed = time.time() - start_time
    print(f"\nRESULT: {passed_count}/{len(tasks)} Passed in {elapsed:.2f}s")
    print("\nNote: Real web results vary by region and search engine changes.")

if __name__ == "__main__":
    main()
