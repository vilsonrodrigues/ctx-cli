# ctx-cli

Context management for LLM agents. Persistent memory that survives context limits.

## The Problem

Long-running LLM agents face context window limits. When context is truncated, the model loses track of what it learned, what decisions it made, and why.

## The Solution

Give the model a memory system with **scope isolation** and **episodic notes**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CONTEXT STORE                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│   │    main     │    │   step-1    │    │   step-2    │                 │
│   ├─────────────┤    ├─────────────┤    ├─────────────┤                 │
│   │ notes:      │    │ notes:      │    │ notes:      │                 │
│   │  [→ step-1] │    │  [abc123]   │    │  [def456]   │                 │
│   │  [← step-1] │    │  Task model │    │  Repository │                 │
│   │  [→ step-2] │    │             │    │             │                 │
│   │  [← step-2] │    ├─────────────┤    ├─────────────┤                 │
│   ├─────────────┤    │ messages:   │    │ messages:   │                 │
│   │ messages:   │    │  (cleared)  │    │  (cleared)  │                 │
│   │  User: next │    │             │    │             │                 │
│   │  Asst: ok   │    └─────────────┘    └─────────────┘                 │
│   └─────────────┘                                                        │
│         ▲                                                                │
│         │ current_scope = "main"                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Message Visibility (Attention Mask)

When you switch scopes, only messages from the **current scope** are visible:

```
SCOPE: main                          SCOPE: step-1
┌─────────────────────────────┐      ┌─────────────────────────────┐
│ messages:                   │      │ messages:                   │
│  ■ User: start task        │      │  □ User: start task        │  ← hidden
│  ■ Asst: creating scope    │      │  □ Asst: creating scope    │  ← hidden
│  ■ [tool] scope step-1     │      │  □ [tool] scope step-1     │  ← hidden
│  □ User: read the file     │      │  ■ User: read the file     │  ← visible
│  □ Asst: file contains...  │      │  ■ Asst: file contains...  │  ← visible
│  □ [tool] note -m "..."    │      │  ■ [tool] note -m "..."    │  ← visible
│  □ [tool] goto main        │      │  □ [tool] goto main        │  ← hidden
│  ■ User: next step         │      │  □ User: next step         │  ← hidden
└─────────────────────────────┘      └─────────────────────────────┘
  ■ = visible in this scope            ■ = visible in this scope
  □ = hidden (other scope)             □ = hidden (other scope)
```

## Notes Persist Across Scopes

Notes are **always visible** in their scope, even when messages are cleared:

```
After completing step-1 and step-2, messages cleared:

SCOPE: main (current)
┌────────────────────────────────────────────────────────────────┐
│ NOTES (persistent):                                            │
│   [→ step-1] Creating Task model                               │
│   [← step-1] Task model complete: id, title, done, created_at  │
│   [→ step-2] Creating TaskRepository                           │
│   [← step-2] Repository complete with CRUD operations          │
├────────────────────────────────────────────────────────────────┤
│ MESSAGES (working memory):                                     │
│   User: Now let's create the service layer                     │
│   Assistant: I'll create TaskService...                        │
└────────────────────────────────────────────────────────────────┘

Total context = Notes + Current Messages (not all historical messages)
```

## Context Window Composition

```
┌─────────────────────────────────────────────────────────────┐
│                     API Request Context                      │
├─────────────────────────────────────────────────────────────┤
│  1. System Prompt (fixed)                          ~500 tk  │
├─────────────────────────────────────────────────────────────┤
│  2. Transition Note (if just switched scope)       ~50 tk   │
│     [← step-1] Task model complete                          │
├─────────────────────────────────────────────────────────────┤
│  3. All Notes in Current Scope                     ~200 tk  │
│     [abc123] Created Task with id, title, done              │
│     [def456] Added validation for required fields           │
├─────────────────────────────────────────────────────────────┤
│  4. Working Messages (only current scope)          ~1000 tk │
│     User: Now create the repository                         │
│     Assistant: I'll create TaskRepository...                │
│     [tool result] ...                                       │
├─────────────────────────────────────────────────────────────┤
│  TOTAL: ~1750 tokens (vs ~8000+ in linear approach)         │
└─────────────────────────────────────────────────────────────┘
```

## Commands (4 total)

| Command | Description | Note Placement |
|---------|-------------|----------------|
| `scope <name> -m "why"` | Create new scope | Note stays in **ORIGIN** |
| `goto <name> -m "result"` | Switch to scope | Note goes to **DESTINATION** |
| `note -m "what"` | Save learning | Current scope |
| `scopes` / `notes` | List scopes/notes | - |

## Workflow Example

```
                    ┌─────────────────────────────────────┐
                    │              main                    │
                    │                                     │
  ──────────────────┼─────────────────────────────────────┼──────────────────
                    │                                     │
  Step 1:           │  [→ step-1] Creating Task model     │
  scope step-1      │           │                         │
                    │           ▼                         │
                    │    ┌─────────────┐                  │
                    │    │   step-1    │                  │
                    │    │             │                  │
                    │    │ [abc] Task  │                  │
                    │    │   created   │                  │
                    │    └──────┬──────┘                  │
                    │           │                         │
  Step 2:           │           │ goto main               │
  goto main         │  [← step-1] Task complete           │
                    │                                     │
  ──────────────────┼─────────────────────────────────────┼──────────────────
                    │                                     │
  Step 3:           │  [→ step-2] Creating Repository     │
  scope step-2      │           │                         │
                    │           ▼                         │
                    │    ┌─────────────┐                  │
                    │    │   step-2    │                  │
                    │    │             │                  │
                    │    │ [def] Repo  │                  │
                    │    │   created   │                  │
                    │    └──────┬──────┘                  │
                    │           │                         │
  Step 4:           │           │ goto main               │
  goto main         │  [← step-2] Repository complete     │
                    │                                     │
  ──────────────────┴─────────────────────────────────────┴──────────────────

  Result: main has complete history of transitions and outcomes
```

## Token Economics

**12-step coding task comparison:**

| Metric | LINEAR | SCOPE | Improvement |
|--------|--------|-------|-------------|
| Total Input Tokens | 431,528 | 137,025 | **68% savings** |
| Peak Input Tokens | 23,249 | 6,353 | **73% lower peak** |
| Steps Completed | 12 | 12 | Same |

Why SCOPE wins:
- LINEAR: Every message stays in context forever → unbounded growth
- SCOPE: Only current scope's messages + notes → bounded growth

```
Token Growth Over Time:

LINEAR:     ████████████████████████████████████████░░░░ (overflow risk)
            ↑ grows with every message

SCOPE:      ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ (bounded)
            ↑ notes compress, messages reset per scope
```

## Installation

```bash
pip install ctx-cli
```

## Quick Start

```python
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

store = ContextStore()

# Start isolated work
execute_command(store, 'scope fix-bug -m "Investigating login timeout"')

# Work happens here...
store.add_message(Message(role="user", content="Check auth module"))
store.add_message(Message(role="assistant", content="Found issue in session config"))

# Save what you learned (this persists!)
execute_command(store, 'note -m "Bug: session timeout was 1s instead of 3600s"')

# Return with results
execute_command(store, 'goto main -m "Fixed login timeout issue"')

# Get context for API call (only includes: notes + current messages)
context = store.get_context("You are a helpful assistant.")
```

## With OpenAI

```python
from openai import OpenAI
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
import json

client = OpenAI()
store = ContextStore()

SYSTEM_PROMPT = """You are a developer. Use ctx_cli to manage context:
- scope <name> -m "why" - Start focused work
- note -m "what" - Save findings
- goto main -m "result" - Return with results"""

# Agent loop
while True:
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=store.get_context(SYSTEM_PROMPT),
        tools=[CTX_CLI_TOOL],
    )

    msg = response.choices[0].message

    if msg.tool_calls:
        for tc in msg.tool_calls:
            if tc.function.name == "ctx_cli":
                args = json.loads(tc.function.arguments)
                result, _ = execute_command(store, args["command"])
                store.add_message(Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id
                ))
    else:
        break  # No more tool calls
```

## Why This Works

1. **Attention mask per scope**: Messages are isolated, no cross-contamination
2. **Notes = compressed memory**: Key learnings persist, verbose messages don't
3. **Explicit transitions**: `[→ scope]` and `[← scope]` prevent mental gaps
4. **Bounded growth**: Peak context stays low even for long tasks

## Demos

```bash
# Compare LINEAR vs SCOPE token usage
python demos/demo_comparison.py

# Real coding task with 12 steps
python demos/demo_long_coding_task.py

# Cross-project knowledge transfer
python demos/demo_knowledge_retention.py

# Explore alternatives in parallel
python demos/demo_planning.py

# Automatic note policies
python demos/demo_policies.py
```

## License

MIT
