#!/usr/bin/env python3
"""
BrowseComp-Style Benchmark for ECM (Simulated).

Simulates OpenAI's BrowseComp benchmark which tests persistent browsing 
and multi-hop reasoning.
"""

import os
import sys
import json
import time
import argparse
from typing import Literal, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.adapters.ecm_adapter import ECMAgentWrapper
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore

# =============================================================================
# Simulated Web Content (The "Internet")
# =============================================================================

WEB_CONTENT = {
    # Task 1: 2004 Olympics Mayor
    "https://google.com/search?q=2004+olympics+city": {
        "title": "Google Search - 2004 olympics city",
        "content": """
Search Results:
1. [2004 Summer Olympics - Wikipedia](https://wikipedia.org/wiki/2004_Summer_Olympics)
   The 2004 Summer Olympics were held in Athens, Greece, from 13 to 29 August 2004.
2. [Athens 2004 - Olympic Games](https://olympics.com/en/olympic-games/athens-2004)
   Official website of the Athens 2004 Olympic Games.
"""
    },
    "https://wikipedia.org/wiki/2004_Summer_Olympics": {
        "title": "2004 Summer Olympics - Wikipedia",
        "content": """
The 2004 Summer Olympics, officially known as the Games of the XXVIII Olympiad, took place in Athens, Greece.
The games were opened by President Konstantinos Stephanopoulos.
The mayor of Athens at the time played a key role in the closing ceremony. 
(See also: [List of mayors of Athens](https://wikipedia.org/wiki/List_of_mayors_of_Athens))
"""
    },
    "https://google.com/search?q=mayor+of+athens+2004": {
         "title": "Google Search - mayor of athens 2004",
         "content": """
Search Results:
1. [Dora Bakoyannis - Wikipedia](https://wikipedia.org/wiki/Dora_Bakoyannis)
   Dora Bakoyannis served as the Mayor of Athens from 2003 to 2006. She was the first female mayor of the city.
2. [List of mayors of Athens](https://wikipedia.org/wiki/List_of_mayors_of_Athens)
   Chronological list of mayors.
"""
    },
    "https://wikipedia.org/wiki/Dora_Bakoyannis": {
        "title": "Dora Bakoyannis - Wikipedia",
        "content": """
Theodora "Dora" Bakoyannis (born 1954) is a Greek politician.
She was the Mayor of Athens from 2003 to 2006, encompassing the 2004 Summer Olympics.
She was heavily involved in the organization of the games.
"""
    },

    # Task 2: Apple Stock 2007
    "https://google.com/search?q=when+was+iphone+announced": {
        "title": "Google Search - when was iphone announced",
        "content": """
Search Results:
1. [History of iPhone - Wikipedia](https://wikipedia.org/wiki/History_of_iPhone)
   Steve Jobs announced the first iPhone at Macworld on January 9, 2007.
"""
    },
    "https://google.com/search?q=apple+stock+price+january+9+2007": {
        "title": "Google Search - apple stock price january 9 2007",
        "content": """
Search Results:
1. [AAPL Historical Data](https://finance.yahoo.com/quote/AAPL/history)
   On Jan 9, 2007, Apple (AAPL) opened at $12.11 and closed at $13.22 (split-adjusted). Note: Original price was around $92.57 before splits.
2. [Apple Stock Soars on iPhone News](https://fake-news.com/apple-2007)
   Apple shares jumped on the news of the iPhone announcement. Closing price was $92.57.
"""
    },

    # Task 3: Scientist born in same city as Marie Curie
    "https://google.com/search?q=marie+curie+birthplace": {
        "title": "Google Search - marie curie birthplace",
        "content": """
Search Results:
1. [Marie Curie - Wikipedia](https://wikipedia.org/wiki/Marie_Curie)
   Marie Skłodowska Curie was born in Warsaw, Poland, on 7 November 1867.
"""
    },
    "https://google.com/search?q=famous+scientists+born+in+warsaw": {
        "title": "Google Search - famous scientists born in warsaw",
        "content": """
Search Results:
1. [List of people from Warsaw - Wikipedia](https://wikipedia.org/wiki/List_of_people_from_Warsaw)
   Notable people include Marie Curie, Frédéric Chopin, and Benoît Mandelbrot.
2. [Benoît Mandelbrot](https://wikipedia.org/wiki/Benoit_Mandelbrot)
   Mathematician known for fractal geometry. Born in Warsaw in 1924.
"""
    }
}

# =============================================================================
# Benchmarking Infrastructure
# =============================================================================

@dataclass
class BrowserState:
    current_url: str = "about:blank"
    history: list[str] = field(default_factory=list)
    content: str = ""

@dataclass
class BenchmarkResult:
    approach: Literal["explicit"]
    model: str
    num_tasks: int
    tasks_completed: int = 0
    elapsed_seconds: float = 0.0
    task_results: list = field(default_factory=list)
    total_tokens: int = 0

class BrowserSimulator:
    """Simulates a browser accessing WEB_CONTENT."""
    
    def __init__(self):
        self.state = BrowserState()
        
    def reset(self):
        self.state = BrowserState()
        
    def navigate(self, url: str) -> str:
        """Visit a URL."""
        self.state.history.append(self.state.current_url)
        self.state.current_url = url
        
        # Check simulated web
        if url in WEB_CONTENT:
            page = WEB_CONTENT[url]
            self.state.content = f"# {page['title']}\n\n{page['content']}"
            return f"Navigated to {url}.\nPage Content Loaded."
        
        # Soft match for searches (simulated dynamic search)
        if "google.com/search" in url:
            # Try to find closest match or generic result
            best_match = None
            max_overlap = 0
            
            # Simple keyword matching
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query).get('q', [''])[0].lower()
            query_words = set(query.split())
            
            for known_url, data in WEB_CONTENT.items():
                 if "google.com/search" in known_url:
                     known_q = urllib.parse.parse_qs(urllib.parse.urlparse(known_url).query).get('q', [''])[0].lower()
                     known_words = set(known_q.split())
                     overlap = len(query_words & known_words)
                     if overlap > max_overlap:
                         max_overlap = overlap
                         best_match = data
            
            if best_match and max_overlap >= 1: # At least one word match
                 self.state.content = f"# {best_match['title']}\n\n{best_match['content']}"
                 return f"Navigated to {url}.\nPage Content Loaded."

        self.state.content = "Error: 404 Not Found. This URL is not in the simulated internet."
        return "404 Not Found"

    def read_page(self) -> str:
        return self.state.content
    
    def get_links(self) -> list[str]:
        # Simple extraction of markdown links (title)[url]
        import re
        links = re.findall(r'\[(.*?)\]\((.*?)\)', self.state.content)
        return [f"{title}: {url}" for title, url in links]

# =============================================================================
# Agent
# =============================================================================

class BrowseCompExplicitAgent(ECMAgentWrapper):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser = None
        
    def _run_tool_loop(self, messages: list[dict], max_rounds: int = 15) -> str:
        
        BROWSER_TOOL = {
            "type": "function",
            "function": {
                "name": "browser",
                "description": "Interact with the web browser.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["search", "visit", "read", "history"],
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
            if response.usage:
                # Naive token tracking update if we had a tracker
                pass

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
                        url = f"https://google.com/search?q={query.replace(' ', '+')}"
                        output = self.browser.navigate(url)
                    elif action == "visit":
                        url = args.get("url", "")
                        output = self.browser.navigate(url)
                    elif action == "read":
                        output = self.browser.read_page()
                    elif action == "history":
                        output = "\n".join(self.browser.state.history)
                        
                    self.logger.log("WEB", f"{action} query={args.get('query')} url={args.get('url')}")
                    print(f"[BROWSER] {action} -> Done")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": output
                    })
                    
        return messages[-1].get("content", "")

    def run_task(self, task: dict, browser: BrowserSimulator) -> dict:
        self.browser = browser
        
        if self.store.current_project != "browsecomp_session":
            self.store.new_project("browsecomp_session")
            self.store.checkout("main", note="Starting BrowseComp", create=True)
            
        from prompts import SYSTEM_PROMPT_ECM_MEMORY
        
        system_prompt = SYSTEM_PROMPT_ECM_MEMORY + """
# ENVIRONMENT
You are in a Web Browser environment.
You have a `browser` tool to search, visit URLs, and read pages.

# MISSION
You are solving a "BrowseComp" task. This requires:
1. **Persistent Browsing**: You usually need to visit MULTIPLE pages to find the answer.
2. **Multi-hop Reasoning**: Finding A helps you find B, which gives you the Answer.
3. **Explicit Memory**: When you find a partial clue (e.g., "Olympics were in Athens"), SAVE IT as a `note` so you don't lose it when navigating to the next page.
4. **Answer**: When you have the final answer, output it clearly.

# TOOL USAGE
- `browser(action="search", query="...")`
- `browser(action="visit", url="...")`
- `browser(action="read")`

Manage your memory explicitly.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Use the browser to answer this question:\n{task['question']}"}
        ]
        
        response = self._run_tool_loop(messages)
        print(f"\nFinal Answer: {response}")
        
        # Simple string matching for evaluation
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
    
    agent = BrowseCompExplicitAgent(agent_config, dataset_config)
    browser = BrowserSimulator()
    
    tasks = [
        {
            "id": 1,
            "question": "Which specific individual was the Mayor of the host city of the 2004 Summer Olympics at the time of the games?",
            "answers": ["Dora Bakoyannis", "Bakoyannis"],
        },
        {
            "id": 2,
            "question": "What was the closing price of Apple stock on the day the first iPhone was announced?",
            "answers": ["$13.22", "13.22", "$92.57", "92.57"],
        },
        {
             "id": 3,
             "question": "Name a famous mathematician born in the same city as Marie Curie.",
             "answers": ["Mandelbrot", "Benoît Mandelbrot", "Benoit Mandelbrot", "Sierpinski", "Tarski"],
        }
    ]
    
    print(f"🚀 Starting BrowseComp Benchmark (Explicit ECM) - {len(tasks)} tasks")
    
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

if __name__ == "__main__":
    main()
