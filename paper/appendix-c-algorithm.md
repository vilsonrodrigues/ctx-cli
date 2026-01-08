# Appendix C: Context Management Algorithm

This appendix provides the formal algorithm for the **SPACE** (Self-Partitioned Agent Context Environment) context management system, implemented in `ctx_cli`.

## C.1 Core Data Structures

```python
class Scope:
    name: str
    messages: List[Message]      # Working Memory (Ephemeral)
    notes: List[Note]            # Episodic Memory (Persistent)
    finalized: bool = False      # Closed state

class ContextStore:
    current_scope: str = "main"
    scopes: Dict[str, Scope] = {"main": Scope("main")}
    insights: List[Insight] = [] # Semantic Memory (Global)
```

## C.2 Command Execution Algorithm

The system operates as a state machine where transitions are triggered by tool calls.

### Algorithm 1: Execute Command

**Input**: `command` string, `store` ContextStore
**Output**: `result` string, `event` (optional)

1.  **Parse** `command` into `tokens`
2.  **Switch** `tokens[0]`:
    *   **Case** `scope`: Call `CreateScope(tokens[1], message)`
    *   **Case** `goto`: Call `SwitchScope(tokens[1], message)`
    *   **Case** `return`: Call `ReturnToMain(message)`
    *   **Case** `note`: Call `AddNote(message)`
    *   **Case** `insight`: Call `AddInsight(message)`
    *   **Case** `status`: Call `GetStatus()`

## C.3 Scope Management Algorithms

### Algorithm 2: Create Scope (`scope`)

**Input**: `name` (target scope), `note` (departure reason)
**Precondition**: `store.current_scope == "main"`

1.  **If** `store.current_scope != "main"`:
    *   **Return** Error: "Scopes must be created from main"
2.  **If** `name` in `store.scopes`:
    *   **Return** Error: "Scope already exists, use goto"
3.  **Let** `S_new` = New `Scope(name)`
4.  **Let** `S_main` = `store.scopes["main"]`
5.  **Record Departure**:
    *   `S_main.notes.append("[To " + name + "] " + note)`
6.  **Switch Context**:
    *   `store.scopes[name] = S_new`
    *   `store.current_scope = name`
7.  **Record Arrival**:
    *   `S_new.messages.append(SystemMessage("Switched to " + name))`
8.  **Return** Success

### Algorithm 3: Switch Scope (`goto`)

**Input**: `name` (target scope), `note` (transition reason)

1.  **If** `name` not in `store.scopes`:
    *   **Return** Error: "Scope does not exist"
2.  **If** `store.scopes[name].finalized`:
    *   **Return** Error: "Scope is finalized"
3.  **Handle Pending Tool Calls**:
    *   **Let** `pending` = `store.scopes[current].get_pending_tool_calls()`
    *   **If** `pending`: `store.scopes[name].messages.extend(pending)`
        *   *Rationale: Maintains API validity by carrying over un-responded calls*
4.  **Switch Context**:
    *   `store.current_scope = name`
5.  **Record Arrival**:
    *   `store.scopes[name].messages.append(AssistantMessage("[From " + prev + "] " + note))`
6.  **Return** Success

### Algorithm 4: Return to Main (`return`)

**Input**: `summary` (conclusion of scope)

1.  **If** `store.current_scope == "main"`:
    *   **Return** Error: "Already in main"
2.  **Let** `S_current` = `store.scopes[current]`
3.  **Finalize**:
    *   `S_current.finalized = True`
4.  **Switch Context**:
    *   `store.current_scope = "main"`
5.  **Persist Summary**:
    *   `store.scopes["main"].notes.append("[" + prev + "] " + summary)`
6.  **Return** Success: "Scope finalized"

## C.4 Memory Persistence Algorithms

### Algorithm 5: Add Note (`note`)

**Input**: `content`

1.  **Let** `S` = `store.scopes[current]`
2.  `S.notes.append(Note(content, timestamp))`
3.  **Return** Success

### Algorithm 6: Context Construction (Pull-Based)

**Input**: `system_prompt`
**Output**: `messages` for LLM API

1.  **Let** `S` = `store.scopes[current]`
2.  **Let** `messages` = `[SystemMessage(system_prompt)]`
3.  **For** `msg` in `S.messages`:
    *   **If** `msg` is valid (no orphan tool calls):
        *   `messages.append(msg)`
4.  **Return** `messages`
    *   *Note: Only messages from the CURRENT scope are included. History from other scopes is invisible unless explicitly retrieved via `notes` tool.*
