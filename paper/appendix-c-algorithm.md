# Appendix C: Context Management Algorithm

This appendix details the implementation of the **SPACE** protocol within the `ctx_cli` reference implementation.

## C.1 Core Data Structures

The system state is encapsulated in two primary classes:

```python
class Scope:
    """Represents a single reasoning partition."""
    name: str
    messages: List[Message]      # Working Memory (Ephemeral)
    notes: List[Note]            # Episodic Memory (Persistent)
    finalized: bool = False      # State flag

class ContextStore:
    """Global state manager."""
    current_scope: str = "main"
    scopes: Dict[str, Scope] = {"main": Scope("main")}
    insights: List[Insight] = [] # Semantic Memory (Global)
```

## C.2 Command Execution Logic

### Algorithm 1: Command Dispatch
**Input**: `command` string, `store` ContextStore
**Output**: `result` string

The system operates as a deterministic state machine. Each tool call triggers a transition:

1.  **Parse** `command` $\rightarrow$ `op`, `args`
2.  **Dispatch** based on `op`:
    *   `scope` $\rightarrow$ `ExecuteScope(args)`
    *   `return` $\rightarrow$ `ExecuteReturn(args)`
    *   `note` $\rightarrow$ `ExecuteNote(args)`
    *   `insight` $\rightarrow$ `ExecuteInsight(args)`
    *   `status` $\rightarrow$ `ExecuteStatus()`

## C.3 Scope Management Algorithms

### Algorithm 2: Scope Initiation (`scope`)
**Input**: `target_scope`, `departure_reason`
**Invariant**: Must originate from `main`.

1.  **Verify Precondition**:
    If `store.current_scope != "main"`, raise `IllegalTransitionError`.
2.  **Verify Uniqueness**:
    If `target_scope` exists in `store.scopes`, raise `ScopeExistsError`.
3.  **Initialize**:
    `S_new` $\leftarrow$ `Scope(target_scope)`
4.  **Record Departure**:
    Append `departure_reason` to `store.scopes["main"].notes`
    *Matches Definition 2: Episodic trace in parent.*
5.  **Transition**:
    `store.current_scope` $\leftarrow$ `target_scope`
6.  **Record Arrival**:
    Inject system message: "Entered scope `target_scope`."

### Algorithm 3: Scope Termination (`return`)
**Input**: `summary`
**Invariant**: Must not be in `main`.

1.  **Verify Precondition**:
    If `store.current_scope == "main"`, raise `IllegalTransitionError`.
2.  **Finalize**:
    `S_curr` $\leftarrow$ `store.scopes[store.current_scope]`
    `S_curr.finalized` $\leftarrow$ `True`
3.  **Transition**:
    `store.current_scope` $\leftarrow$ "main"
4.  **Consolidate**:
    Append `summary` to `store.scopes["main"].notes`
    *Crucial Step: This summary becomes the permanent record.*
5.  **Cleanup**:
    The working memory of `S_curr` is now effectively unreachable for context construction.

## C.4 Context Construction (Pull-Based)

### Algorithm 4: ConstructPrompt
**Input**: `system_prompt`
**Output**: List of Messages

Unlike standard RAG, this algorithm performs **Scope Filtering**:

1.  `S_active` $\leftarrow$ `store.scopes[store.current_scope]`
2.  `context` $\leftarrow$ `[SystemMessage(system_prompt)]`
3.  **For each** `msg` in `S_active.messages`:
    *   **Filter**: Validate tool call integrity (ensure no orphaned outputs).
    *   `context.append(msg)`
4.  **Return** `context`

*Note*: Messages from other scopes are strictly excluded. Historical notes are included only if a `notes` tool call is present in `S_active.messages`.
