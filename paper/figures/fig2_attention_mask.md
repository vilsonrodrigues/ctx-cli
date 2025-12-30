# Figure 2: Attention Mask Mechanism

## Scope Isolation - Message Visibility

```
                    SCOPE: main                              SCOPE: step-1
         ┌────────────────────────────────┐       ┌────────────────────────────────┐
         │                                │       │                                │
    t=1  │  ■ User: Start the task       │       │  □ User: Start the task       │
         │                                │       │                                │
    t=2  │  ■ Asst: I'll create a scope  │       │  □ Asst: I'll create a scope  │
         │                                │       │                                │
    t=3  │  ■ [tool] scope step-1 -m ... │       │  □ [tool] scope step-1 -m ... │
         │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │       │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
    t=4  │  □ User: Read the config      │       │  ■ User: Read the config      │
         │                                │       │                                │
    t=5  │  □ Asst: Config contains...   │       │  ■ Asst: Config contains...   │
         │                                │       │                                │
    t=6  │  □ [tool] note -m "Found..."  │       │  ■ [tool] note -m "Found..."  │
         │                                │       │                                │
    t=7  │  □ [tool] goto main -m ...    │       │  □ [tool] goto main -m ...    │
         │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │       │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
    t=8  │  ■ User: What did you find?   │       │  □ User: What did you find?   │
         │                                │       │                                │
    t=9  │  ■ Asst: I found that...      │       │  □ Asst: I found that...      │
         │                                │       │                                │
         └────────────────────────────────┘       └────────────────────────────────┘

                    ■ = VISIBLE                            ■ = VISIBLE
                    □ = HIDDEN                             □ = HIDDEN
                    ─ = scope boundary                     ─ = scope boundary
```

## Formal Attention Mask

```
Let M = {m₁, m₂, ..., mₙ} be all messages
Let S(mᵢ) = scope of message mᵢ
Let C = current scope

Visibility function:
                    ┌ 1  if S(mᵢ) = C
    V(mᵢ, C) =     │
                    └ 0  otherwise

API Context = { mᵢ ∈ M : V(mᵢ, C) = 1 }
```

## Attention Matrix Visualization

```
            Messages in Context Window
         ┌─────────────────────────────────┐
         │  m1   m2   m3   m4   m5   m6    │
      ───┼─────────────────────────────────┤
      m1 │  ■    ■    ■    □    □    □     │  ← main scope
      m2 │  ■    ■    ■    □    □    □     │  ← main scope
Queries  ────────────────────────────────────
      m3 │  □    □    □    ■    ■    ■     │  ← step-1 scope
      m4 │  □    □    □    ■    ■    ■     │  ← step-1 scope
      m5 │  □    □    □    ■    ■    ■     │  ← step-1 scope
         └─────────────────────────────────┘

         ■ = attention allowed (same scope)
         □ = attention blocked (different scope)
```

## Context Composition per API Call

```
┌─────────────────────────────────────────────────────────────┐
│                     API REQUEST CONTEXT                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 1: System Prompt                           ~500 tk   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ "You are a developer. Use ctx_cli for context..."      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  LAYER 2: Episodic Memory (Notes)                  ~50 tk   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [NOTES]                                                 │ │
│  │ - [abc123] Found: session timeout was 1s               │ │
│  │ - [← step-1] Fixed authentication bug                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  LAYER 3: Working Memory (Messages)               ~400 tk   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ User: "Now let's work on the API"                      │ │
│  │ Assistant: "I'll create the endpoints..."              │ │
│  │ [tool_call] write_file(...)                            │ │
│  │ [tool_result] "File written"                           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ═══════════════════════════════════════════════════════════│
│  TOTAL: ~950 tokens (vs ~3000+ in linear approach)          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```
