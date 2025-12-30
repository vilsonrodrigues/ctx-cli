# 5. Results

We present results for each experimental task, followed by aggregate analysis.

## 5.1 Task 1: Multi-Step Coding Task

Table 2 shows token metrics for the 12-step blog platform design task.

**Table 2: Multi-Step Coding Task Results**

| Metric | Linear | Scope | Improvement |
|--------|--------|-------|-------------|
| Total Input Tokens | 431,528 | 137,025 | **68.2%** |
| Peak Input Tokens | 23,249 | 6,353 | **72.7%** |
| Base Input Tokens | 1,247 | 2,891 | -131.8% |
| Growth (Peak - Base) | 22,002 | 3,462 | **84.3%** |
| Total Output Tokens | 18,442 | 21,156 | -14.7% |
| Steps Completed | 12/12 | 12/12 | Same |

### Key Observations

1. **Total input reduction of 68%**: The scope approach uses approximately one-third the input tokens of linear.

2. **Peak context 73% lower**: Maximum context per call is bounded, reducing both latency and attention dilution.

3. **Higher base cost**: The scope approach has ~2.3x higher base tokens due to the extended system prompt explaining commands. However, this is cacheable by API providers.

4. **Growth reduction of 84%**: When accounting for cacheable overhead, actual context growth is dramatically lower.

5. **Slightly higher output**: The scope approach generates ~15% more output tokens due to tool call overhead (command invocations and responses).

6. **Same task completion**: Both approaches complete all 12 steps successfully.

### Token Growth Curves

Figure 1 shows token growth over steps:

```
Step   │    Linear │     Scope │ Difference
───────┼───────────┼───────────┼───────────
   1   │     2,847 │     3,124 │       -277
   2   │     5,632 │     3,891 │     +1,741
   3   │     8,419 │     4,256 │     +4,163
   4   │    11,847 │     4,512 │     +7,335
   5   │    14,238 │     3,987 │    +10,251
   6   │    16,892 │     4,891 │    +12,001
   7   │    19,124 │     5,234 │    +13,890
   8   │    21,456 │     5,891 │    +15,565
   9   │    22,134 │     5,124 │    +17,010
  10   │    22,847 │     5,567 │    +17,280
  11   │    23,124 │     6,012 │    +17,112
  12   │    23,249 │     6,353 │    +16,896
```

The linear approach shows monotonic growth. The scope approach oscillates—growing within a scope, then dropping when switching scopes and clearing working memory.

## 5.2 Task 2: Cross-Project Knowledge Transfer

Table 3 shows results for the two-project knowledge transfer task.

**Table 3: Knowledge Transfer Results**

| Metric | Project | Linear | Scope |
|--------|---------|--------|-------|
| Base Input | A | 1,124 | 2,756 |
| Peak Input | A | 4,891 | 5,234 |
| Growth | A | 3,767 | 2,478 |
| Iterations | A | 6 | 5 |
| Base Input | B | 1,124 | 2,891 |
| Peak Input | B | 4,567 | 4,012 |
| Growth | B | 3,443 | 1,121 |
| Iterations | B | 5 | 4 |

### Key Observations

1. **Project B benefits from Project A's notes**: The scope approach shows reduced growth in Project B (1,121 vs 2,478 in Project A) because the agent queries existing notes rather than re-exploring.

2. **Fewer iterations in Project B**: With access to patterns from Project A, the agent completes faster.

3. **Memory access observed**: In 4 out of 5 runs, the scope agent explicitly queried `notes user-model` before starting Product model implementation.

### Qualitative Analysis

We manually inspected generated code. In the scope condition, Project B's Product model consistently matched Project A's validation pattern:

```python
# Pattern from Project A (User model)
def validate_email(self) -> bool:
    return "@" in self.email

# Applied in Project B (Product model)
def validate_price(self) -> bool:
    return self.price > 0
```

The linear condition showed more variation in Project B's implementation, occasionally using different validation patterns than Project A.

## 5.3 Task 3: Alternative Exploration

Table 4 shows results for the architecture exploration task.

**Table 4: Alternative Exploration Results**

| Metric | Linear | Scope |
|--------|--------|-------|
| Total Input Tokens | 89,124 | 52,891 |
| Peak Input Tokens | 12,456 | 5,891 |
| Scopes Created | N/A | 3 |
| Notes Made | N/A | 8 |
| Transitions | N/A | 4 |

### Key Observations

1. **Clean separation**: The scope approach created distinct scopes for OT and CRDT exploration.

2. **Notes captured tradeoffs**: Example notes from runs:
   - `[approach-ot] "Pros: well-understood, many implementations. Cons: requires central server, complex transformation logic"`
   - `[approach-crdt] "Pros: offline-first, eventually consistent. Cons: higher memory, complex data structures (Yjs, Automerge)"`

3. **Comparison used notes**: When comparing approaches, the scope agent referenced notes from both scopes rather than relying on in-context memory of the explorations.

## 5.4 Aggregate Analysis

### 5.4.1 Token Savings Summary

Across all tasks:

| Task | Linear Total | Scope Total | Savings |
|------|--------------|-------------|---------|
| Multi-step (12 steps) | 431,528 | 137,025 | 68.2% |
| Knowledge transfer | 19,248 | 18,456 | 4.1% |
| Alternative exploration | 89,124 | 52,891 | 40.6% |
| **Average** | — | — | **37.6%** |

The multi-step task shows highest savings because it has the most steps and thus the most context accumulation in the linear condition.

### 5.4.2 When Scope Helps Most

Analysis suggests scope-based management provides greatest benefit when:

1. **Many steps**: More opportunities for context to accumulate
2. **Separable subtasks**: Natural scope boundaries exist
3. **Knowledge reuse**: Notes from early work inform later work

For short tasks or highly sequential work without natural boundaries, the overhead of scope management may not be justified.

### 5.4.3 Output Token Overhead

The scope approach consistently uses 10-20% more output tokens due to:
- Tool call JSON formatting
- Command parsing and responses
- Note content in responses

This overhead is offset by input savings when tasks exceed ~5 steps.
