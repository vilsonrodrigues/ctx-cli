# ECM Visualization

Visual representation of Explicit Context Management commands and state transitions.

## Legend

```
●  Current scope (HEAD)
○  Other scope
□  Note (episodic memory)
◇  Insight (semantic memory)
───  Working messages flow
- -  Memory reference
```

---

## 1. Initial State

```
                         ┌─────────────────────┐
                         │   SEMANTIC MEMORY   │
                         │    (Global Pool)    │
                         │                     │
                         │   (empty)           │
                         └─────────────────────┘

                         ┌─────────────────────┐
Project: default         │       main          │
                         │         ●           │
                         │                     │
                         │   messages: 0       │
                         │   notes: 0          │
                         └─────────────────────┘
```

---

## 2. After: `scope user-model -m "Building User model"`

```
                         ┌─────────────────────┐
                         │   SEMANTIC MEMORY   │
                         │                     │
                         │   (empty)           │
                         └─────────────────────┘

                         ┌─────────────────────┐
Project: default         │       main          │
                         │         ○           │
                         │                     │
                         │   messages: 0       │
                         └─────────────────────┘
                                   │
                                   │ scope
                                   ▼
                         ┌─────────────────────┐
                         │    user-model       │
                         │         ●           │◄─── HEAD
                         │                     │
                         │   messages: 0       │
                         │   notes: 0          │
                         └─────────────────────┘
```

---

## 3. After: `note -m "Created User dataclass with validation"`

```
                         ┌─────────────────────┐
                         │   SEMANTIC MEMORY   │
                         │                     │
                         │   (empty)           │
                         └─────────────────────┘

                         ┌─────────────────────┐
Project: default         │       main          │
                         │         ○           │
                         └─────────────────────┘
                                   │
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │    user-model       │
                         │         ●           │◄─── HEAD
                         │                     │
                         │   messages: N       │
                         │   ┌───────────────┐ │
                         │   │ □ Created     │ │◄─── note added
                         │   │   User...     │ │
                         │   └───────────────┘ │
                         └─────────────────────┘
```

---

## 4. After: `insight -m "Pattern: dataclass with validate_X methods"`

```
                         ┌─────────────────────┐
                         │   SEMANTIC MEMORY   │
                         │                     │
                         │ ┌─────────────────┐ │
                         │ │ ◇ Pattern:      │ │◄─── insight (GLOBAL)
                         │ │   dataclass...  │ │
                         │ └─────────────────┘ │
                         └─────────────────────┘
                                   │
                            visible from ALL scopes
                                   │
                         ┌─────────────────────┐
Project: default         │       main          │
                         │         ○           │
                         └─────────────────────┘
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │    user-model       │
                         │         ●           │◄─── HEAD
                         │   ┌───────────────┐ │
                         │   │ □ Created     │ │
                         │   │   User...     │ │
                         │   └───────────────┘ │
                         └─────────────────────┘
```

---

## 5. After: `goto main -m "User model complete"`

```
                         ┌─────────────────────┐
                         │   SEMANTIC MEMORY   │
                         │ ┌─────────────────┐ │
                         │ │ ◇ Pattern:      │ │
                         │ │   dataclass...  │ │
                         │ └─────────────────┘ │
                         └─────────────────────┘

                         ┌─────────────────────┐
Project: default         │       main          │
                         │         ●           │◄─── HEAD (returned)
                         │                     │
                         │   messages: 1       │◄─── "[Returning from user-model]..."
                         │   ┌───────────────┐ │
                         │   │ □ Summary...  │ │◄─── transition note
                         │   └───────────────┘ │
                         └─────────────────────┘
                                   │
                                   │
                         ┌─────────────────────┐
                         │    user-model       │
                         │         ○           │
                         │   ┌───────────────┐ │
                         │   │ □ Created     │ │◄─── preserved
                         │   │   User...     │ │
                         │   └───────────────┘ │
                         └─────────────────────┘
```

---

## 6. After: `new_project("ecommerce-api")`

**Developer API call - not visible to model**

```
                         ┌─────────────────────┐
                         │   SEMANTIC MEMORY   │
                         │ ┌─────────────────┐ │
                         │ │ ◇ Pattern:      │ │◄─── persists across projects!
                         │ │   dataclass...  │ │
                         │ └─────────────────┘ │
                         └─────────────────────┘


═══════════════════════════════════════════════════════════
Project: ecommerce-api   (NEW - current)
═══════════════════════════════════════════════════════════

                         ┌─────────────────────┐
                         │       main          │
                         │         ●           │◄─── HEAD (fresh)
                         │                     │
                         │   messages: 0       │
                         │   notes: 0          │
                         └─────────────────────┘


───────────────────────────────────────────────────────────
Project: default         (PREVIOUS - archived with @suffix)
───────────────────────────────────────────────────────────

        ┌─────────────────────┐     ┌─────────────────────┐
        │   main@default      │     │ user-model@default  │
        │         ○           │     │         ○           │
        │   ┌───────────────┐ │     │   ┌───────────────┐ │
        │   │ □ Summary...  │ │     │   │ □ Created     │ │
        │   └───────────────┘ │     │   │   User...     │ │
        └─────────────────────┘     │   └───────────────┘ │
                                    └─────────────────────┘
                 │                            │
                 └────────────────────────────┘
                              │
                    Accessible via:
                    notes main@default
                    notes user-model@default
```

---

## 7. Memory Retrieval Commands

### `notes` - Recall ALL episodic memory

```
┌─────────────────────────────────────────────────────────────┐
│ [EPISODIC MEMORY - Journal]                                 │
│                                                             │
│ Date:   Mon Jan 05 16:00:00 2026 -0300                      │
│     [product-model] Applied validation pattern              │
│                                                             │
│ Date:   Mon Jan 05 15:30:00 2026 -0300                      │
│     [user-model@default] Created User dataclass...          │
│     [main@default] Summary: User model complete             │
└─────────────────────────────────────────────────────────────┘
```

### `notes user-model@default` - Recall specific scope

```
┌─────────────────────────────────────────────────────────────┐
│ Notes in 'user-model@default':                              │
│                                                             │
│ Date:   Mon Jan 05 15:30:00 2026 -0300                      │
│     Created User dataclass with validation                  │
└─────────────────────────────────────────────────────────────┘
```

### `insights` - Recall semantic memory

```
┌─────────────────────────────────────────────────────────────┐
│ [SEMANTIC MEMORY - Global Insights]                         │
│                                                             │
│ Date:   Mon Jan 05 15:35:00 2026 -0300                      │
│     Pattern: dataclass with validate_X methods              │
└─────────────────────────────────────────────────────────────┘
```

---

## Command Flow Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                         ECM COMMAND FLOW                         │
└──────────────────────────────────────────────────────────────────┘

    status ────────────────► View current state + available actions
       │
       ▼
    scope ─────────────────► Create new isolated workspace
       │                            │
       │                            ▼
       │                     note ──► Save local finding
       │                            │
       │                     insight ► Save global pattern
       │                            │
       ▼                            ▼
    goto main ─────────────► Return with summary
       │
       ▼
    notes / insights ──────► Pull knowledge into context

┌──────────────────────────────────────────────────────────────────┐
│                     MEMORY ARCHITECTURE                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   WORKING MEMORY (RAM)      │  EPISODIC (Notes)  │  SEMANTIC    │
│   ─────────────────────     │  ──────────────────│  ──────────  │
│   Conversation messages     │  Scope-local facts │  Global      │
│   Cleared on scope switch   │  Persist forever   │  patterns    │
│   Not persisted             │  Pull with `notes` │  Pull with   │
│                             │                    │  `insights`  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
