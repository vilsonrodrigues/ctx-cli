# 3. Method

We present explicit context management through scope isolation. Section 3.1 defines the core data structures. Section 3.2 describes the attention mask mechanism. Section 3.3 details the command interface. Section 3.4 explains note placement semantics. Section 3.5 covers context composition for API calls.

## 3.1 Data Structures

The system maintains a **ContextStore** containing isolated reasoning contexts called **scopes** (internally represented as branches for implementation convenience with version control semantics).

### 3.1.1 Message

A message represents a single turn in the conversation:

```
Message = {
    role: "system" | "user" | "assistant" | "tool",
    content: string,
    tool_call_id?: string,      // For tool responses
    tool_calls?: ToolCall[]     // For assistant tool requests
}
```

Messages are ephemeral—they exist only in the current working context and may be cleared when transitioning between scopes.

### 3.1.2 Note (Commit)

A note captures episodic knowledge that persists across scope transitions:

```
Note = {
    hash: string,               // Short identifier (SHA256 prefix)
    message: string,            // Semantic description of the learning
    timestamp: string,
    messages_snapshot: Message[], // Full context at note creation
    parent_hash?: string        // For note history
}
```

Notes serve as compressed episodic memory. While the full message snapshot is stored for potential reconstruction, only the semantic message is typically included in API context—achieving compression from potentially hundreds of tokens to a single descriptive line.

### 3.1.3 Scope (Branch)

A scope represents an isolated reasoning context:

```
Scope = {
    name: string,
    messages: Message[],        // Working memory (ephemeral)
    notes: Note[],              // Episodic memory (persistent)
    created_at: string,
    head_note?: string          // Transition context from previous scope
}
```

The key insight is the **separation of working and episodic memory**. Messages capture the ongoing reasoning process; notes capture what was learned. Messages can be cleared without losing accumulated knowledge.

### 3.1.4 ContextStore

The top-level container managing all scopes:

```
ContextStore = {
    scopes: Map<string, Scope>,
    current_scope: string,      // Currently active scope
    events: Event[],            // Audit trail
    command_history: string[]   // For reconstruction
}
```

The store always contains a "main" scope, initialized on creation. All operations emit events for debugging and reconstruction.

## 3.2 Attention Mask Mechanism

The core mechanism enabling bounded context is **scope isolation through attention masking**. When the model receives context, it sees only:

1. Messages from the current scope
2. Notes from the current scope

Messages from other scopes are hidden—they exist in the store but are not included in API calls. This creates an effective attention mask where the model can only attend to current-scope information.

Formally, let $M$ be all messages across all scopes and $S$ be the current scope. The visible message set is:

$$V = \{m \in M : \text{scope}(m) = S\}$$

The context sent to the API is:

$$\text{Context} = \text{SystemPrompt} \oplus \text{Notes}(S) \oplus V$$

where $\oplus$ denotes concatenation in message order.

This creates **bounded context within each scope**: regardless of total accumulated messages across all scopes, each API call includes only current-scope content. Context growth is O(1) per scope rather than O(n) globally.

### Visual Representation

```
SCOPE: main                          SCOPE: step-1
┌─────────────────────────────┐      ┌─────────────────────────────┐
│  ■ User: start task        │      │  □ User: start task        │  ← hidden
│  ■ Asst: creating scope    │      │  □ Asst: creating scope    │  ← hidden
│  □ User: read the file     │      │  ■ User: read the file     │  ← visible
│  □ Asst: file contains...  │      │  ■ Asst: file contains...  │  ← visible
│  ■ User: next step         │      │  □ User: next step         │  ← hidden
└─────────────────────────────┘      └─────────────────────────────┘
  ■ = visible in this scope            ■ = visible in this scope
  □ = hidden (other scope)             □ = hidden (other scope)
```

## 3.3 Command Interface

The system exposes four commands through a tool interface:

### 3.3.1 scope

```
scope <name> -m "<note>"
```

Creates a new isolated scope and switches to it. The note is saved in the **origin** scope before switching, explaining why the agent is leaving.

**Semantics:**
1. Create note in current scope: `[→ {name}] {note}`
2. Create new scope (inheriting notes from main)
3. Switch current_scope to new scope

### 3.3.2 goto

```
goto <name> -m "<note>"
```

Switches to an existing scope. The note is saved in the **destination** scope after switching, explaining what the agent brings.

**Semantics:**
1. Preserve pending tool_call chains (for API compatibility)
2. Switch current_scope to destination
3. Create note in destination: `[← {origin}] {note}`

### 3.3.3 note

```
note -m "<message>"
```

Creates a note in the current scope without switching. Used to checkpoint learnings during work.

**Semantics:**
1. Snapshot current messages
2. Create note with message
3. Optionally clear working messages (configurable)

### 3.3.4 Inspection Commands

```
scopes    # List all scopes
notes     # List notes in current scope
notes <scope>  # List notes in specified scope
```

Read-only commands for inspecting state.

## 3.4 Note Placement Semantics

A critical design decision is **asymmetric note placement**:

| Command | Note Location | Purpose |
|---------|---------------|---------|
| `scope X -m "..."` | Origin (current) | Explains WHY leaving |
| `goto X -m "..."` | Destination (X) | Explains WHAT bringing |

This asymmetry prevents reasoning gaps during context switches:

**Example workflow:**

```
[main] scope step-1 -m "Investigating authentication bug"
    → Note "[→ step-1] Investigating authentication bug" saved in main
    → Switched to step-1

[step-1] ... work happens ...

[step-1] note -m "Found: session timeout was 1s instead of 3600s"
    → Note saved in step-1

[step-1] goto main -m "Fixed: session timeout corrected to 3600s"
    → Switched to main
    → Note "[← step-1] Fixed: session timeout corrected to 3600s" saved in main
```

When the agent later reviews main's notes, it sees:
- `[→ step-1] Investigating authentication bug` (why it left)
- `[← step-1] Fixed: session timeout corrected to 3600s` (what it brought back)

This creates a complete reasoning trail without requiring the agent to recall details from step-1's messages.

## 3.5 Context Composition

When preparing context for an API call, the system constructs a three-layer composition:

### Layer 1: System Prompt

The base system prompt, typically including task instructions and available tools.

### Layer 2: Episodic Memory

Notes from the current scope, formatted as:

```
[EPISODIC MEMORY]
- [abc123] Created User model with validation
- [def456] Added email and password validators
- [→ step-2] Starting repository implementation
```

Only the most recent N notes are included (configurable, default 5) to bound this layer.

### Layer 3: Working Messages

Current scope's messages, validated for tool call sequence integrity.

### Composition Algorithm

```python
def get_context(system_prompt: str) -> list[Message]:
    result = []

    # Layer 1: System prompt
    if system_prompt:
        result.append({"role": "system", "content": system_prompt})

    # Layer 2: Episodic memory
    scope = self.scopes[self.current_scope]
    if scope.notes:
        memory = "[EPISODIC MEMORY]\n"
        for note in scope.notes[-5:]:
            memory += f"- [{note.hash[:7]}] {note.message}\n"
        result.append({"role": "system", "content": memory})

    # Layer 3: Working messages
    validated = self._validate_tool_call_sequence(scope.messages)
    for msg in validated:
        result.append(msg.to_dict())

    return result
```

### Tool Call Validation

The OpenAI API requires that every tool response has a matching preceding assistant message with the corresponding tool_call_id. During scope switches, this invariant can be violated if the agent switches mid-tool-call.

The system handles this by:
1. Detecting pending tool_call chains (assistant with tool_calls but missing responses)
2. Carrying these chains across scope switches
3. Validating sequences before API calls, removing incomplete chains in the middle of context

## 3.6 Token Economics

The architecture achieves token reduction through two mechanisms:

### 3.6.1 Scope Isolation

Within each scope, only current-scope messages are included. For a 12-step task split across 4 scopes:

- **Linear**: All 12 steps in context → O(12) messages
- **Scope**: Only current scope's ~3 steps → O(3) messages

### 3.6.2 Note Compression

Notes compress detailed message histories into single-line summaries:

- **Full messages**: "User asked about X. Assistant analyzed Y, found Z, then tried W..."  → 200+ tokens
- **Note**: "Found: Z is caused by W" → 15 tokens

This compression ratio of 10-15x compounds across notes.

### 3.6.3 Bounded Growth

Let $n$ = total interactions, $s$ = number of scopes, $k$ = notes per scope.

- **Linear context**: O(n) tokens per call
- **Scope context**: O(n/s + k) tokens per call, where k << n

For our 12-step experiment: n=60 messages, s=4 scopes, k=3 notes average.
- Linear: ~60 messages in context
- Scope: ~15 messages + 3 notes ≈ 18 items

This explains the observed 68% reduction in total tokens and 73% reduction in peak context.
