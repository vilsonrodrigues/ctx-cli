# Figure 5: Comparison with Related Work

## Approach Comparison Matrix

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT MANAGEMENT APPROACHES COMPARISON                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│              │ Training │ External │ Context   │ Explicit │ Complexity │         │
│   Approach   │ Required │ Infra    │ Reduction │ Control  │            │         │
│ ─────────────┼──────────┼──────────┼───────────┼──────────┼────────────┤         │
│              │          │          │           │          │            │         │
│ MemGPT      │    No    │   Yes    │ Unbounded │    No    │   High     │         │
│ [13]        │          │ (DB)     │ (external)│          │            │         │
│              │          │          │           │          │            │         │
│ ─────────────┼──────────┼──────────┼───────────┼──────────┼────────────┤         │
│              │          │          │           │          │            │         │
│ Mem0        │    No    │   Yes    │    ~90%   │    No    │   Medium   │         │
│ [16]        │          │ (Vector) │           │(implicit)│            │         │
│              │          │          │           │          │            │         │
│ ─────────────┼──────────┼──────────┼───────────┼──────────┼────────────┤         │
│              │          │          │           │          │            │         │
│ Context-    │   RL     │    No    │    10×    │    No    │   High     │         │
│ Folding [2] │          │          │           │(learned) │            │         │
│              │          │          │           │          │            │         │
│ ─────────────┼──────────┼──────────┼───────────┼──────────┼────────────┤         │
│              │          │          │           │          │            │         │
│ AgentFold   │  Fine-   │    No    │   High    │    No    │   High     │         │
│ [1]         │  tuning  │          │           │(learned) │            │         │
│              │          │          │           │          │            │         │
│ ─────────────┼──────────┼──────────┼───────────┼──────────┼────────────┤         │
│              │          │          │           │          │            │         │
│ HiAgent     │    No    │    No    │    35%    │ Partial  │   Medium   │         │
│ [3]         │          │          │           │(subgoal) │            │         │
│              │          │          │           │          │            │         │
│ ─────────────┼──────────┼──────────┼───────────┼──────────┼────────────┤         │
│              │          │          │           │          │            │         │
│ ████████████│██████████│██████████│███████████│██████████│████████████│         │
│ ██ OURS ████│███ No ███│███ No ███│███ 68% ███│███ Yes ██│███ Low ████│         │
│ ████████████│██████████│██████████│███████████│██████████│████████████│         │
│              │          │          │           │          │            │         │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Design Space Positioning

```
                            Implicit ◀─────────────────────────▶ Explicit
                                         Control Paradigm
                                               │
                    High │    ┌─────────────┐  │
                         │    │ AgentFold   │  │
                         │    │             │  │
          Training       │    │ Context-    │  │
          Complexity     │    │ Folding     │  │
                         │    └─────────────┘  │
                         │                     │
                         │    ┌─────────────┐  │    ┌─────────────┐
                    Med  │    │   MemGPT    │  │    │   HiAgent   │
                         │    │             │  │    │             │
                         │    │    Mem0     │  │    │             │
                         │    └─────────────┘  │    └─────────────┘
                         │                     │
                         │                     │    ╔═════════════╗
                    Low  │                     │    ║    OURS     ║
                         │                     │    ║  (ctx-cli)  ║
                         │                     │    ╚═════════════╝
                         │                     │
                         └─────────────────────┴─────────────────────
                                               │
                                    Most Explicit,
                                    Least Complex
```

## Feature Matrix

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         FEATURE COMPARISON                                 │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   Feature                    │ Fold │ Mem0 │ HiAgent │ MemGPT │  OURS    │
│  ────────────────────────────┼──────┼──────┼─────────┼────────┼──────────│
│                              │      │      │         │        │          │
│   No fine-tuning required    │  ✗   │  ✓   │    ✓    │   ✓    │    ✓     │
│                              │      │      │         │        │          │
│   No RL training required    │  ✗   │  ✓   │    ✓    │   ✓    │    ✓     │
│                              │      │      │         │        │          │
│   No external database       │  ✓   │  ✗   │    ✓    │   ✗    │    ✓     │
│                              │      │      │         │        │          │
│   In-context management      │  ✓   │  ✓   │    ✓    │   ✗    │    ✓     │
│                              │      │      │         │        │          │
│   Agent-controlled           │  ✗   │  ✗   │    ~    │   ~    │    ✓     │
│                              │      │      │         │        │          │
│   Transparent/debuggable     │  ✗   │  ✗   │    ~    │   ✗    │    ✓     │
│                              │      │      │         │        │          │
│   Minimal interface (≤4 cmd) │  ✗   │  ✗   │    ✗    │   ✗    │    ✓     │
│                              │      │      │         │        │          │
│   Works with any LLM         │  ✗   │  ✓   │    ✓    │   ✓    │    ✓     │
│                              │      │      │         │        │          │
└───────────────────────────────────────────────────────────────────────────┘

         ✓ = Yes     ✗ = No     ~ = Partial
```

## Trade-off Analysis

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           TRADE-OFF SPECTRUM                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   SOPHISTICATION ◀═══════════════════════════════════════▶ SIMPLICITY        │
│                                                                               │
│   ┌─────────────┐                                    ┌─────────────┐         │
│   │  Learned    │                                    │  Explicit   │         │
│   │  Policies   │                                    │  Commands   │         │
│   │             │                                    │             │         │
│   │ • Optimal   │                                    │ • Interpret │         │
│   │   decisions │                                    │   able      │         │
│   │ • Requires  │                                    │ • No train  │         │
│   │   training  │                                    │   required  │         │
│   │ • Black box │                                    │ • Depends   │         │
│   │             │                                    │   on prompt │         │
│   └─────────────┘                                    └─────────────┘         │
│         │                                                    │                │
│         │            The "Sweet Spot" depends on:            │                │
│         │            • Development resources                 │                │
│         │            • Interpretability needs                │                │
│         │            • Task complexity                       │                │
│         │            • Deployment constraints                │                │
│         │                                                    │                │
│         ▼                                                    ▼                │
│   AgentFold                                              ctx-cli              │
│   Context-Folding                                        (OURS)               │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```
