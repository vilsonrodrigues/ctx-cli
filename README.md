# ctx-cli

Context management for LLM agents. Persistent memory that survives context limits.

## The Problem

Long-running LLM agents face context window limits. When context is truncated, the model loses track of what it learned, what decisions it made, and why.

## The Solution

Give the model a memory system:
- **Scopes** = Isolated reasoning spaces (like mental workspaces)
- **Notes** = Episodic memory (what the model learned/decided)
- **Transitions** = Explicit context switches with explanations

The model manages its own context via `ctx_cli`, a single tool with 4 core commands.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     Context Window                          │
├─────────────────────────────────────────────────────────────┤
│  System Prompt (fixed)                                      │
├─────────────────────────────────────────────────────────────┤
│  Transition Note: [← step-1] Task model complete            │
├─────────────────────────────────────────────────────────────┤
│  Notes (episodic memory):                                   │
│    - [abc123] Created Task with id, title, done             │
│    - [def456] Added validation for required fields          │
├─────────────────────────────────────────────────────────────┤
│  Working Messages:                                          │
│    User: Now create the repository                          │
│    Assistant: I'll create TaskRepository...                 │
└─────────────────────────────────────────────────────────────┘
```

Key insight:
- `scope` note explains WHY you're leaving current scope
- `goto` note explains WHAT you bring to destination
- This prevents "mental gaps" when switching contexts

## Commands

### Core Commands (4 total)

| Command | Description |
|---------|-------------|
| `scope <name> -m "why"` | Create new scope. Note stays in CURRENT (origin). |
| `goto <name> -m "result"` | Switch to scope. Note goes to DESTINATION. |
| `note -m "what"` | Save learning in current scope. Be detailed! |
| `scopes` | List all scopes |
| `notes [scope]` | Show notes in scope (default: current) |

### Example Workflow

```
[in main]
ctx_cli scope step-1 -m "Creating Task model"     # main gets this note
[work: read files, write code]
ctx_cli note -m "Created Task: id, title, done"   # step-1 gets this note
ctx_cli goto main -m "Task model complete"        # main gets this note
[back in main, ready for next step]
```

### Result in main:

```
[→ step-1] Creating Task model
[← step-1] Task model complete
[→ step-2] Creating TaskRepository
[← step-2] Repository with atomic writes
...
```

Main always knows: why you left, what you brought back.

## Token Economics

**12-step coding task comparison:**

| Metric | LINEAR | BRANCH | Improvement |
|--------|--------|--------|-------------|
| Total Input Tokens | 431,528 | 137,025 | **68% savings** |
| Peak Input Tokens | 23,249 | 6,353 | **73% lower** |
| Steps Completed | 12 | 12 | ✓ |

The branch approach uses more iterations (scope/note/goto overhead) but saves massively on tokens.

## Installation

```bash
pip install ctx-cli
```

## Quick Start

```python
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

# Create store
store = ContextStore()

# Start a scope
execute_command(store, 'scope fix-login -m "Investigating login bug"')

# Add messages (simulating conversation)
store.add_message(Message(role="user", content="Check the auth module"))
store.add_message(Message(role="assistant", content="Found the issue..."))

# Save what you learned
execute_command(store, 'note -m "Bug caused by session timeout config"')

# Return to main with findings
execute_command(store, 'goto main -m "Fixed: session timeout was 1s, changed to 3600s"')

# Get context for API call
context = store.get_context("You are a helpful assistant.")
```

## With OpenAI

```python
from openai import OpenAI
from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

client = OpenAI()
store = ContextStore()

# Include CTX_CLI_TOOL in your tools
response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=store.get_context(system_prompt),
    tools=[CTX_CLI_TOOL],
)

# Handle ctx_cli tool calls
for tool_call in response.choices[0].message.tool_calls:
    if tool_call.function.name == "ctx_cli":
        args = json.loads(tool_call.function.arguments)
        result, event = execute_command(store, args["command"])
```

## Why This Works

1. **Isolated reasoning**: Each scope has its own context, preventing confusion
2. **Persistent memory**: Notes survive when messages are cleared
3. **Explicit transitions**: No "mental gaps" - origin knows why you left, destination knows what you brought
4. **Lower peak context**: 73% reduction means staying further from limits

## Architecture

```
┌────────────────┐     ┌─────────────┐     ┌──────────────┐
│   LLM Model    │────▶│   ctx_cli   │────▶│ ContextStore │
│                │     │   (tool)    │     │              │
└────────────────┘     └─────────────┘     └──────────────┘
        │                     │                    │
        ▼                     ▼                    ▼
   Uses tool           Parses command       Manages state
   to manage           and executes         (scopes, notes,
   own context                               messages)
```

## Philosophy

1. **Model as curator**: The model decides what's worth remembering
2. **Explicit transitions**: scope/goto notes preserve reasoning chains
3. **No mental gaps**: Origin and destination always have context
4. **Token-efficient**: Notes preserve insights, working messages can be cleared

## License

MIT
