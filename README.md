# ctx-cli

**Explicit Context Management (ECM)** for LLM Agents.
A memory architecture that decouples *reasoning history* from *knowledge retention*.

## The Problem: Context Saturation & Drift

As LLM agents work on long tasks, their context window fills up with:
1.  **Noise:** Typos, failed attempts, and verbose tool outputs.
2.  **Episodic History:** Every interaction remains "active," confusing the model about what is currently relevant.

This leads to **Context Drift** (forgetting instructions) and **Exponential Cost**.

## The Solution: Tiered & Pull-Based Memory

`ctx-cli` implements a memory system inspired by Endel Tulving's theory of human memory:

*   **Working Memory (RAM):** Ephemeral conversation messages. Automatically cleared when switching scopes.
*   **Episodic Memory (Journal):** A chronological, persistent log of technical events and findings (`notes`).
*   **Semantic Memory (Facts):** A global, persistent repository of architectural rules and discovered patterns (`insights`).

**Key Innovation:** Memory is **Pull-Based**. The agent starts with a clean slate and *deliberately* calls tools to load specific memories into its working context.

---

## Command Reference

### 1. Context Switching
Manage the agent's active reasoning space.

*   **`scope <name> -m "<reason>"`**
    *   **Action:** Creates a new reasoning scope (branch) and switches to it.
    *   **Behavior:** The current working memory is cleared. The new scope inherits only the high-level history.
    *   **Best Practice:** Use Git-style namespaces like `plan/task-x`, `fix/issue-y`, or `research/lib-z`.
*   **`goto <name> -m "<summary>"`**
    *   **Action:** Switches back to an existing scope.
    *   **Behavior:** Restores the target's working memory. The summary message is recorded in the target scope's journal to ensure continuity.
*   **`scopes`**
    *   **Action:** Lists all active reasoning scopes.
*   **`status`**
    *   **Action:** Shows current scope, working message count, and memory statistics (insights/notes count).

### 2. Knowledge Persistence
Save technical knowledge before clearing the context.

*   **`note -m "<message>"`** (Episodic)
    *   **Scope:** Local to the current scope.
    *   **Usage:** Record specific technical details, file paths, or intermediate results.
*   **`insight -m "<message>"`** (Semantic)
    *   **Scope:** Global. Visible from any scope.
    *   **Usage:** Record project-wide rules, architecture patterns, or universal truths discovered.
    *   **Hygiene:** If discovered during a task, open the task scope first, then record the insight to keep the `main` scope clean.

### 3. Memory Retrieval (The "Pull")
Load knowledge into working memory only when needed.

*   **`notes [scope]`**
    *   **Behavior:** Returns the "Journal" of episodic notes. If no scope is provided, returns notes from **all scopes** grouped by day in Git-log style.
    *   **Format:** `Date: Day Mon DD HH:MM:SS YYYY ZZZZ`
*   **`insights`**
    *   **Behavior:** Returns all global semantic insights grouped by day.

---

## Strategic Workflow: The Planning Loop

To solve complex engineering tasks without context bloat, agents follow this pattern:

1.  **Open thinking space:** `scope plan/fix-auth -m "Reasoning about authentication bug"`
2.  **Pull Knowledge:** 
    *   `insights` (Check architectural rules)
    *   `notes` (Check past attempts or related work)
3.  **Synthesize Plan:** Reasoning happens in this clean, isolated space.
4.  **Commit Result:** `goto main -m "Plan ready: Apply @authenticated decorator to all endpoints."`
5.  **Execute Fix:** `scope fix/auth-decorator -m "Implementing the synthesized plan"`

---

## Token Economics

**Benchmark: SWE-bench-CL (Django Sequence)**

| Metric | Standard Linear Agent | ECM Agent (ctx-cli) | Improvement |
| :--- | :--- | :--- | :--- |
| **Input Token Growth** | O(n) (Monotonic) | O(1) (Sawtooth) | **Constant Cost** |
| **Peak Context** | 35,000+ tokens | ~2,500 tokens | **-92%** |
| **Latency** | 60s+ per turn | ~1.5s per turn | **40x Faster** |
| **Reliability** | Drops as context grows | Remains stable | **Long-Term** |

---

## Installation

```bash
pip install ctx-cli
```

## License

MIT
