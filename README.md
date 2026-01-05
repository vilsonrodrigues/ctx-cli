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
    *   Creates a new reasoning scope (branch) and switches to it.
    *   Best Practice: Use Git-style namespaces like `plan/task-x`, `fix/issue-y`.
*   **`goto <name> -m "<summary>"`**
    *   Switches back to an existing scope.
*   **`status`**
    *   Shows current scope, all scopes (grouped by project), and memory stats with action hints.

### 2. Knowledge Persistence
Save technical knowledge before clearing the context.

*   **`note -m "<message>"`** (Episodic)
    *   Scope: Local to the current scope.
    *   Usage: Record specific technical details, file paths, or intermediate results.
*   **`insight -m "<message>"`** (Semantic)
    *   Scope: Global. Visible from any scope.
    *   Usage: Record project-wide rules, architecture patterns, or universal truths discovered.

### 3. Memory Retrieval (The "Pull")
Load knowledge into working memory only when needed.

*   **`notes`** — Returns all episodic notes from all scopes.
*   **`notes <scope>`** — Returns notes from a specific scope.
*   **`insights`** — Returns all global semantic insights.

---

## Project Management (Developer API)

For multi-project workflows, developers can use the `new_project()` API:

```python
from ctx_store import ContextStore

store = ContextStore()
# ... agent works on Project A ...

store.new_project("project-b")  # Developer calls this
# - Marks existing scopes as "previous project"
# - Clears main working messages (notes preserved)
# - Agent can still access previous project's notes via `notes <scope>`
```

The `status` command shows scopes grouped by project:

```
On scope: product-model
Working messages: 0

Current Project: ecommerce-api
  Scopes:
    - main
    ● product-model (1 notes)

Previous Projects:
  [auth-service]
    Scopes:
      - user-model (1 notes)

Memory:
  Insights: 1
  Notes: 2

Actions:
  note -m "..."       Record to current scope
  insight -m "..."    Record global pattern
  notes               Recall all episodic memory
  notes <scope>       Recall scope episodic memory
  insights            Recall semantic memory
```

---

## Strategic Workflow: The Planning Loop

1.  **Check Status:** `status` — See available scopes and memory
2.  **Pull Knowledge:** `notes`, `insights` — Load relevant context
3.  **Open Scope:** `scope plan/fix-auth -m "Reasoning about auth bug"`
4.  **Synthesize:** Reasoning happens in this clean, isolated space
5.  **Record:** `note -m "..."` — Save what you learned
6.  **Return:** `goto main -m "Plan ready: ..."`

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

