# Figure 3: Token Growth Comparison

## Linear vs Scope-Based Token Growth

```
Tokens (thousands)
    │
 25 ┤                                          ╭── LINEAR ──╮
    │                                     ●────●            │
 20 ┤                               ●────●                  │
    │                         ●────●                        │ 23,249 peak
 15 ┤                   ●────●                              │
    │             ●────●                                    │
 10 ┤       ●────●                                          │
    │  ●────●                                               │
  5 ┤  ●                                                    ╯
    │  ╭── SCOPE ──╮
    │  ●──●──●──●──●──●──●──●──●──●──●──●  6,353 peak
    │                                      (bounded)
  0 ┼──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──▶ Steps
       1  2  3  4  5  6  7  8  9 10 11 12
```

## Detailed Growth Curves

```
Step │  LINEAR  │   SCOPE   │  Savings
─────┼──────────┼───────────┼──────────
  1  │   2,847  │    3,124  │   -9.7%   ← overhead visible early
  2  │   5,632  │    3,891  │   30.9%
  3  │   8,419  │    4,256  │   49.4%
  4  │  11,847  │    4,512  │   61.9%
  5  │  14,238  │    3,987  │   72.0%   ← scope switch
  6  │  16,892  │    4,891  │   71.0%
  7  │  19,124  │    5,234  │   72.6%
  8  │  21,456  │    5,891  │   72.5%
  9  │  22,134  │    5,124  │   76.9%   ← scope switch
 10  │  22,847  │    5,567  │   75.6%
 11  │  23,124  │    6,012  │   74.0%
 12  │  23,249  │    6,353  │   72.7%
─────┴──────────┴───────────┴──────────
PEAK │  23,249  │    6,353  │   72.7%
```

## Growth Rate Analysis

```
                    LINEAR                          SCOPE

Context     │  ████████████████████      │  ████████░░░░░░░░░░░░░░
Growth      │  ████████████████████      │  ████████░░░░░░░░░░░░░░
Rate        │  Unbounded O(n)            │  Bounded O(n/s + k)
            │                            │
            │  Every message             │  Only current scope
            │  stays in context          │  messages + notes
            │                            │
Risk        │  ⚠️ OVERFLOW               │  ✓ BOUNDED
```

## Cumulative Token Usage

```
                         Total Input Tokens Over Task
    │
500K┤  ╭─────────────────────────────── LINEAR: 431,528
    │  │
400K┤  │
    │  │
300K┤  │
    │  │
200K┤  │
    │  ╰─────────────────────────────── SCOPE: 137,025
100K┤
    │
  0 ┼──────────────────────────────────────────────────▶
       Start                                        End

                     68.2% REDUCTION
```

## Why Scope Wins

```
┌──────────────────────────────────────────────────────────────┐
│                    TOKEN ECONOMICS                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  LINEAR:                                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Context = Σ (all messages from t=0 to t=now)            │ │
│  │                                                          │ │
│  │ Growth = O(n) where n = total messages                   │ │
│  │                                                          │ │
│  │ Problem: Every historical message competes for           │ │
│  │          attention with current reasoning                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  SCOPE:                                                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Context = current_scope.messages + current_scope.notes   │ │
│  │                                                          │ │
│  │ Growth = O(n/s + k)                                      │ │
│  │          where s = scopes, k = notes per scope           │ │
│  │                                                          │ │
│  │ Benefit: Only relevant context visible                   │ │
│  │          Notes compress historical knowledge             │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Compression ratio: notes ≈ 10-15x smaller than messages    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```
