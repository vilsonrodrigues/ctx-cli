"""
Research Agent Demo: Agent researches a topic, committing discoveries incrementally.

This demo simulates a research scenario where:
1. Agent receives a research topic
2. Explores different aspects, committing findings as it goes
3. Uses branches for different research angles
4. Merges findings into a comprehensive summary

Shows how episodic memory preserves research while exploring new angles.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a research assistant investigating a technical topic.

You have ctx_cli for context management. This is essential for research:

## Research Strategy:
1. Create a scope for the research topic
2. For each sub-topic, either:
   - Take notes directly if staying on same angle
   - Create a new scope if exploring a tangent
3. Return to main with synthesis

## Your workflow:
- scope research-topic -m "Starting research on X" - Begin research
- note -m "Finding: [key insight]" - Save a discovery
- goto main -m "Research complete: [summary]" - Return with findings
- scope sub-topic -m "Exploring Y angle" - Dive into sub-topic

## Research best practices:
- Take notes after each significant finding
- Use descriptive notes (they become your memory)
- Create scopes when exploring tangential topics
- Return to main with synthesis

Think of notes as your research notebook - they persist your discoveries."""

# Simulated research sources (in real scenario, could use web search)
RESEARCH_SOURCES = {
    "overview": """
    WebAssembly (Wasm) is a binary instruction format designed as a portable
    compilation target for programming languages. Key facts:
    - Created by W3C in 2017
    - Runs in all major browsers
    - Near-native performance
    - Language agnostic (C, C++, Rust, Go can compile to it)
    - Sandboxed execution model
    """,
    "performance": """
    WebAssembly Performance Characteristics:
    - 10-800% faster than JavaScript for compute-heavy tasks
    - Predictable performance (no JIT warmup)
    - Efficient memory usage with linear memory model
    - SIMD support for parallel operations
    - Limitations: DOM access requires JS interop, adding overhead
    Benchmarks show biggest gains in: image processing, cryptography, games
    """,
    "use_cases": """
    WebAssembly Use Cases in Production:
    1. Figma - Design tool, 3x performance improvement
    2. Google Earth - Complex 3D rendering
    3. AutoCAD - CAD software in browser
    4. Blazor - .NET in the browser
    5. PyScript - Python in the browser
    6. Game engines: Unity, Unreal export to Wasm
    Emerging: Edge computing, serverless (Cloudflare Workers)
    """,
    "future": """
    WebAssembly Roadmap and Future:
    - WASI (WebAssembly System Interface) - run outside browser
    - Component Model - better module composition
    - Garbage Collection - native GC support
    - Exception Handling - proper try/catch
    - Threads - shared memory multithreading
    Docker founder: "If Wasm existed in 2008, we wouldn't have needed Docker"
    """
}


def run_research():
    """Run research agent demo."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, label: str = "") -> str:
        if label:
            print(f"\n{'━' * 60}")
            print(f"  {label}")
            print(f"{'━' * 60}")

        store.add_message(Message(role="user", content=user_message))

        for _ in range(10):
            context = store.get_context(SYSTEM_PROMPT)

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=context,
                tools=tools,
            )

            message = response.choices[0].message

            if message.tool_calls:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                    tool_calls=[tc.model_dump() for tc in message.tool_calls]
                ))

                tool_results = []
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "ctx_cli":
                        args = json.loads(tool_call.function.arguments)
                        result, _ = execute_command(store, args["command"])
                        cmd = args["command"]
                        if "commit" in cmd:
                            print(f"  📝 {cmd[11:70]}...")
                        elif "checkout" in cmd:
                            print(f"  🔀 {cmd[:60]}")
                        elif "merge" in cmd:
                            print(f"  🔗 {cmd}")
                        elif "tag" in cmd:
                            print(f"  🏷️  {cmd}")
                        else:
                            print(f"  [ctx] {cmd[:50]}")
                        tool_results.append((tool_call.id, result))

                for tool_id, result in tool_results:
                    store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_id,
                    ))
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                response_short = (message.content or "")[:250]
                if len(message.content or "") > 250:
                    response_short += "..."
                print(f"\n  {response_short}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("RESEARCH AGENT DEMO: Investigating WebAssembly")
    print("=" * 70)
    print("\nAgent will research WebAssembly, committing findings as it discovers...")

    # Start research
    chat("""
    I need you to research WebAssembly (Wasm) comprehensively.

    Start by creating a research branch, then begin investigating.
    Commit your initial understanding.
    """, label="PHASE 1: Initial Overview")

    chat(f"""
    Here's background information on WebAssembly:

    {RESEARCH_SOURCES['overview']}

    Analyze this and commit your key findings.
    """, label="SOURCE: Overview")

    # Performance deep-dive
    chat(f"""
    Now let's explore performance characteristics:

    {RESEARCH_SOURCES['performance']}

    This might warrant a separate branch for performance research.
    Commit your analysis.
    """, label="PHASE 2: Performance Analysis")

    # Use cases
    chat(f"""
    Let's look at real-world applications:

    {RESEARCH_SOURCES['use_cases']}

    Commit the most significant use cases.
    """, label="PHASE 3: Use Cases")

    # Future and synthesis
    chat(f"""
    Finally, the future of WebAssembly:

    {RESEARCH_SOURCES['future']}

    Commit these findings, then synthesize everything.
    """, label="PHASE 4: Future Roadmap")

    chat("""
    Now synthesize all your research:
    1. Review your commits (use log)
    2. Create a final summary commit
    3. Tag this research as complete with key conclusions

    What are the 3 most important things you learned?
    """, label="SYNTHESIS: Final Summary")

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("RESEARCH RESULTS")
    print("=" * 70)

    print("\n📚 Research Log (Episodic Memory):")
    for branch_name, branch in store.branches.items():
        if branch.commits:
            print(f"\n  Branch: {branch_name}")
            for commit in branch.commits:
                print(f"    [{commit.hash[:7]}] {commit.message[:60]}...")

    print("\n🏷️  Conclusions Tagged:")
    if store.tags:
        for name, tag in store.tags.items():
            print(f"  {name}: {tag.description[:70]}...")
    else:
        print("  (no tags)")

    print("\n📊 Research Statistics:")
    total_commits = sum(len(b.commits) for b in store.branches.values())
    print(f"  Branches explored: {len(store.branches)}")
    print(f"  Findings committed: {total_commits}")
    print(f"  Sources analyzed: {len(RESEARCH_SOURCES)}")
    print(f"  Total operations: {len(store.events)}")

    # Show knowledge preserved
    print("\n💡 Knowledge Preserved in Commits:")
    for branch in store.branches.values():
        for commit in branch.commits[-3:]:  # Last 3 per branch
            if len(commit.message) > 20:  # Skip trivial commits
                print(f"  • {commit.message[:80]}")


if __name__ == "__main__":
    run_research()
