# Figure 4: Workflow and Command Semantics

## Complete Workflow Example

```
                        ┌─────────────────────────────────────────┐
                        │                 main                     │
                        │                                         │
    ════════════════════╪═════════════════════════════════════════╪═══════════
                        │                                         │
    Step 1:             │  [→ step-1] "Creating Task model"       │
    scope step-1        │            │                            │
                        │            ▼                            │
                        │     ┌─────────────────┐                 │
                        │     │    step-1       │                 │
                        │     │                 │                 │
                        │     │ [abc] "Task     │                 │
                        │     │  model with     │                 │
                        │     │  validation"    │                 │
                        │     └────────┬────────┘                 │
                        │              │                          │
    Step 2:             │              │ goto main                │
    goto main           │  [← step-1] "Task model complete"       │
                        │                                         │
    ════════════════════╪═════════════════════════════════════════╪═══════════
                        │                                         │
    Step 3:             │  [→ step-2] "Creating Repository"       │
    scope step-2        │            │                            │
                        │            ▼                            │
                        │     ┌─────────────────┐                 │
                        │     │    step-2       │                 │
                        │     │                 │                 │
                        │     │ [def] "CRUD     │                 │
                        │     │  operations     │                 │
                        │     │  implemented"   │                 │
                        │     └────────┬────────┘                 │
                        │              │                          │
    Step 4:             │              │ goto main                │
    goto main           │  [← step-2] "Repository complete"       │
                        │                                         │
    ════════════════════╪═════════════════════════════════════════╪═══════════
                        │                                         │
                        │  RESULT: main has complete trail:       │
                        │  • [→ step-1] Creating Task model       │
                        │  • [← step-1] Task model complete       │
                        │  • [→ step-2] Creating Repository       │
                        │  • [← step-2] Repository complete       │
                        │                                         │
                        └─────────────────────────────────────────┘
```

## Command Semantics: Note Placement

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NOTE PLACEMENT SEMANTICS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │   scope <name> -m "note"                                               │  │
│  │   ══════════════════════                                               │  │
│  │                                                                        │  │
│  │   ┌─────────┐                    ┌─────────┐                          │  │
│  │   │ CURRENT │ ──── note ────▶   │ CURRENT │                          │  │
│  │   │ (main)  │     [→ name]      │ (main)  │                          │  │
│  │   │         │                    │ + note  │                          │  │
│  │   └─────────┘                    └────┬────┘                          │  │
│  │                                       │                                │  │
│  │                                       │ switch                         │  │
│  │                                       ▼                                │  │
│  │                                 ┌─────────┐                           │  │
│  │                                 │   NEW   │                           │  │
│  │                                 │ (name)  │ ◀── current               │  │
│  │                                 └─────────┘                           │  │
│  │                                                                        │  │
│  │   Note stays in ORIGIN → explains WHY leaving                         │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │   goto <name> -m "note"                                                │  │
│  │   ═════════════════════                                                │  │
│  │                                                                        │  │
│  │   ┌─────────┐                                                         │  │
│  │   │ CURRENT │                                                         │  │
│  │   │ (step-1)│                                                         │  │
│  │   └────┬────┘                                                         │  │
│  │        │                                                               │  │
│  │        │ switch                                                        │  │
│  │        ▼                                                               │  │
│  │   ┌─────────┐                    ┌─────────┐                          │  │
│  │   │  DEST   │ ──── note ────▶   │  DEST   │                          │  │
│  │   │ (name)  │    [← step-1]     │ (name)  │ ◀── current              │  │
│  │   │         │                    │ + note  │                          │  │
│  │   └─────────┘                    └─────────┘                          │  │
│  │                                                                        │  │
│  │   Note goes to DESTINATION → explains WHAT bringing                   │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Why asymmetric?                                                             │
│  • Departure notes contextualize the transition for origin scope            │
│  • Arrival notes ground the context for destination scope                   │
│  • Creates complete audit trail without redundancy                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## State Machine

```
                              ┌─────────────────┐
                              │                 │
                              │      MAIN       │
                              │    (initial)    │
                              │                 │
                              └────────┬────────┘
                                       │
                     ┌─────────────────┼─────────────────┐
                     │                 │                 │
              scope step-1      scope step-2      scope step-N
              -m "why"          -m "why"          -m "why"
                     │                 │                 │
                     ▼                 ▼                 ▼
              ┌──────────┐      ┌──────────┐      ┌──────────┐
              │  STEP-1  │      │  STEP-2  │      │  STEP-N  │
              │          │      │          │      │          │
              │  note    │      │  note    │      │  note    │
              │  -m "x"  │      │  -m "y"  │      │  -m "z"  │
              │          │      │          │      │          │
              └────┬─────┘      └────┬─────┘      └────┬─────┘
                   │                 │                 │
                   └─────────────────┼─────────────────┘
                                     │
                              goto main
                              -m "result"
                                     │
                                     ▼
                              ┌─────────────────┐
                              │                 │
                              │      MAIN       │
                              │  (accumulated)  │
                              │                 │
                              └─────────────────┘
```
