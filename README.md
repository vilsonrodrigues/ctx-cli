# ctx-cli

Git-like context management for LLM agents.

## The Problem

Long-running LLM agents face context window limits. Traditional solutions (summarization, RAG) either lose critical details or add latency.

## The Solution

Treat context like a Git repository:
- **Working memory** = Current branch messages (RAM)
- **Episodic memory** = Commits (what the model learned/decided)
- **Milestones** = Tags (immutable reference points)

The model manages its own context via `ctx_cli`, a single tool that accepts Git-like commands.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     Context Window                          │
├─────────────────────────────────────────────────────────────┤
│  System Prompt (fixed)                                      │
├─────────────────────────────────────────────────────────────┤
│  Head Note: [From main] Working on bug fix                  │
├─────────────────────────────────────────────────────────────┤
│  Episodic Memory (commits):                                 │
│    - [abc123] Identified root cause in parser               │
│    - [def456] Fixed validation logic                        │
├─────────────────────────────────────────────────────────────┤
│  Working Messages:                                          │
│    User: Can you also add error handling?                   │
│    Assistant: Sure, I'll add try-catch blocks...            │
│    Tool: [file edit result]                                 │
└─────────────────────────────────────────────────────────────┘
```

When context grows too large:
1. Model calls `ctx_cli commit -m "Added error handling with custom exceptions"`
2. Working messages are cleared
3. Commit message becomes episodic memory

## Commands

### Basic Commands

| Command | Description |
|---------|-------------|
| `commit -m "message"` | Save reasoning, clear working memory |
| `checkout -b branch -m "note"` | Switch to new branch with transition note |
| `checkout branch -m "note"` | Switch to existing branch |
| `branch [name]` | List branches or create new |
| `tag name -m "desc"` | Create immutable milestone |
| `log` | Show commit history |
| `status` | Show current state |
| `diff branch` | Compare with another branch |
| `stash push -m "msg"` | Save work temporarily |
| `stash pop` | Restore stashed work |
| `history` | Show recent commands |

### Advanced Commands

| Command | Description |
|---------|-------------|
| `merge branch` | Merge commits from another branch |
| `cherry-pick hash` | Apply specific commit to current branch |
| `reset hash [--hard]` | Go back to a previous state |
| `bisect start/good/bad/reset` | Binary search for reasoning errors |

## Token Economics

Without ctx-cli:
```
Start → 2k tokens → work → 50k tokens → work → 100k tokens → LIMIT
```

With ctx-cli:
```
Start → 2k → work → 50k → commit → 5k → work → 60k → commit → 8k → ...
```

Each commit flattens the curve while preserving key insights.

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

# Add messages (simulating conversation)
store.add_message(Message(role="user", content="Help me fix the login bug"))
store.add_message(Message(role="assistant", content="I found the issue..."))

# Commit reasoning
execute_command(store, 'commit -m "Login bug caused by session timeout"')

# Start new task
execute_command(store, 'checkout -b add-tests -m "Going to add unit tests"')

# Get context for API call
context = store.get_context("You are a helpful assistant.")
```

## With OpenAI

```python
from agent import ContextManagedAgent

agent = ContextManagedAgent(model="gpt-4.1-mini")

# The model will automatically use ctx_cli to manage its context
response = agent.run("Build a REST API with CRUD operations for todos")
```

## Event System

Every `ctx_cli` command produces an event:

```python
{
    "type": "commit",
    "timestamp": "2024-01-15T10:30:00",
    "branch": "fix-parser",
    "payload": {
        "message": "Fixed JSON parsing for nested objects",
        "hash": "abc123def456",
        "messages_count": 12
    }
}
```

Use events to:
- Reconstruct context state
- Monitor agent behavior
- Debug reasoning chains

## Architecture

```
┌────────────────┐     ┌─────────────┐     ┌──────────────┐
│   LLM Model    │────▶│   ctx_cli   │────▶│ ContextStore │
│                │     │   (tool)    │     │              │
└────────────────┘     └─────────────┘     └──────────────┘
        │                     │                    │
        │                     │                    │
        ▼                     ▼                    ▼
   Uses tool           Parses command       Manages state
   to manage           and executes         (branches, commits,
   own context                               tags, messages)
```

## Philosophy

1. **Model as curator**: The model decides what's worth remembering
2. **Intentional transitions**: Checkout notes preserve reasoning chains
3. **Immutable milestones**: Tags mark approved decisions
4. **Token-efficient**: Commits preserve insights, discard noise

## License

MIT
