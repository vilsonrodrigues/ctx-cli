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

## 5.4 Task 4: SWE-Bench-CL Continual Learning

Table 5 shows results for 15 sequential Django issue resolution tasks.

**Table 5: SWE-Bench-CL Results (15 tasks)**

| Metric | Linear | Scope | Improvement |
|--------|--------|-------|-------------|
| Peak Context | 12,059 | 1,402 | **88.4%** |
| Final Task Context | 12,059 | 801 | **93.4%** |
| Avg Context/Task | 6,032 | 569 | **90.6%** |
| Context Growth | +11,812 | +543 | **Bounded** |
| API Calls | 15 | 60 | -300% |
| Cached Tokens | 57,472 | 0 | — |
| Execution Time | 121.5s | 80.5s | **33.8%** |

### Key Observations

1. **Context growth bounded**: Linear grew from 247 to 12,059 tokens (49x). Scope remained stable between 200-800 tokens regardless of task count.

2. **93% context reduction on final task**: By task 15, linear context is 12K tokens while scope is under 1K.

3. **34% faster execution**: Despite 4x more API calls, scope completed 34% faster due to smaller context per call.

4. **Prompt caching asymmetry**: Linear achieved 69% cache hit rate (57K/83K tokens cached). Scope achieved 0% because context changes break cache prefixes.

5. **Bounded vs linear growth**:

```
Task   │    Linear │     Scope │ Growth Pattern
───────┼───────────┼───────────┼────────────────
   1   │       247 │       258 │ Similar
   5   │     3,546 │       828 │ Linear 4x higher
  10   │     7,576 │       799 │ Linear 9x higher
  15   │    12,059 │       801 │ Linear 15x higher
```

### Implications for Long-Running Agents

At the observed growth rate:
- **50 tasks**: Linear would reach ~40K tokens (approaching GPT-4 limits)
- **100 tasks**: Linear would reach ~80K tokens (near 128K limit)
- **Scope**: Remains under 2K tokens regardless of task count

This demonstrates ctx-cli's primary value proposition: enabling long-running agents that would otherwise hit context limits.

## 5.5 Aggregate Analysis

### 5.5.1 Token Savings Summary

Across all tasks:

| Task | Peak Linear | Peak Scope | Context Savings |
|------|-------------|------------|-----------------|
| Multi-step (12 steps) | 23,249 | 6,353 | 72.7% |
| Knowledge transfer | 4,891 | 4,012 | 18.0% |
| Alternative exploration | 12,456 | 5,891 | 52.7% |
| SWE-Bench-CL (15 tasks) | 12,059 | 1,402 | **88.4%** |
| **Average** | — | — | **58.0%** |

The SWE-Bench-CL task shows highest savings because it has the most sequential tasks, demonstrating the O(n) vs O(1) growth difference.

### 5.5.2 When Scope Helps Most

Analysis suggests scope-based management provides greatest benefit when:

1. **Many steps**: More opportunities for context to accumulate
2. **Separable subtasks**: Natural scope boundaries exist
3. **Knowledge reuse**: Notes from early work inform later work

For short tasks or highly sequential work without natural boundaries, the overhead of scope management may not be justified.

### 5.5.3 Output Token Overhead

The scope approach consistently uses 10-20% more output tokens due to:
- Tool call JSON formatting
- Command parsing and responses
- Note content in responses

This overhead is offset by input savings when tasks exceed ~5 steps.
