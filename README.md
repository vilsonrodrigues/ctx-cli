# ctx-cli: Explicit Context Management (ECM)

**SPACE Architecture** (Self-Partitioned Agent Context Environment).
A **Cognitive Stabilization System** for long-running LLM agents.

> *"Explicit Context Management reframes test-time compute from unstructured token expenditure into a sequence of explicit, irreversible cognitive state transitions."*

---

## ⚡ Key Results (SWE-Bench-CL)

| Metric | Linear Agent | SPACE Agent | Impact |
| :--- | :--- | :--- | :--- |
| **Peak Context** | 12,059 tokens | **1,402 tokens** | **-88% Attention Load** |
| **Growth Rate** | O(n) Quadratic Cost | **O(1) Constant Cost** | **Infinite Horizons** |
| **Execution Time** | 121.5s | **80.5s** | **34% Faster** |
| **Cognitive State** | Drifts / Ruminates | **Stabilized** | **Anti-Hallucination** |

---

## The Problem: "Cognitive Waste"

Modern agents (especially those using Reasoning Models like o1) suffer from a paradox:
1.  **Thinking costs tokens:** Complex problems require long Chain-of-Thought (CoT) traces.
2.  **Context is finite:** Keeping these traces fills the window with "cognitive waste"—intermediate errors and dead ends.
3.  **Attention Dilution:** As context fills, the model "forgets" initial instructions and "ruminates" on past errors visible in history.

## The Solution: SPACE

`ctx-cli` implements **SPACE**, an architecture that treats context as **Versioned State**, not a chat log.

### 1. Structured Test-Time Compute
Instead of letting the model think indefinitely in a linear stream, SPACE enforces **Compute Budgets** via Scopes.
*   **Scope:** An isolated environment for reasoning. The agent "checks out" a branch to think.
*   **Return:** A forced **Cognitive Commit**. The agent *must* summarize its decision and discard the raw thought process.

### 2. Anti-Rumination Mechanism
When an agent leaves a scope (`return`), the raw messages (including errors and failed tool calls) are **physically deleted** from the working memory.
*   **Effect:** The agent cannot "ruminate" on past failures because they no longer exist in its perceptual field. Only the distilled lesson (`note`) remains.

---

## Architecture: The Graph

SPACE replaces the stack (LIFO) with a **Radial Navigation** model.

```
        ┌─── research/approach-A
main ───┼─── research/approach-B
        └─── implement/chosen
```

1.  **Main:** The stable core. Contains high-level decisions and the "head" of the project.
2.  **Scopes:** Ephemeral workspaces. Created for specific tasks (`fix/auth-bug`, `plan/migration`).
3.  **Notes:** The edges of the graph. Information preserved across transitions.

---

## Command Reference

### Navigation (The "Where")

*   **`scope <name> -m "<reason>"`**
    *   **Action:** Create & Enter a new workspace.
    *   **Semantics:** "I am allocating a budget to think about X."
    *   *Rule:* Only valid from `main`.
*   **`return -m "<summary>"`**
    *   **Action:** Finalize & Destroy current workspace.
    *   **Semantics:** "I have decided Y. Discard the process."
    *   *Effect:* Working memory is wiped. Summary is saved to `main`.

### Persistence (The "What")

*   **`note -m "<fact>"`** (Episodic)
    *   **Storage:** Local to current scope.
    *   **Use Case:** "Test failed at line 42", "File path is /src/app.py".
*   **`insight -m "<pattern>"`** (Semantic)
    *   **Storage:** Global (visible everywhere).
    *   **Use Case:** "The project uses Factory Pattern for all DAOs."

### Inspection (The "Meta")

*   **`status`** — Show current scope, memory stats, and available actions.
*   **`notes`** — Read the episodic journal.
*   **`insights`** — Read global knowledge.

---

## Workflow Example

The agent doesn't just "chat"; it **navigates**:

1.  **Main:** `scope plan/db-migration -m "Analyze schema changes"`
2.  **Scope (plan/db-migration):**
    *   *Reads files... (5000 tokens)*
    *   *Thinks... (2000 tokens)*
    *   `note -m "Strategy: Use Alembic for auto-generation"`
    *   `return -m "Plan approved. Use Alembic."`
3.  **Main:** (Context is clean. Only the note exists.)
    *   `scope act/execute-migration -m "Running Alembic"`

---

## Installation

```bash
pip install ctx-cli
```

## Citation

If you use SPACE in your research, please cite our paper:

```bibtex
@article{ctx-cli2026,
  title={Explicit Context Management for Long-Horizon Agents},
  author={Rodrigues, Vilson},
  journal={arXiv preprint},
  year={2026}
}
```

## License

MIT