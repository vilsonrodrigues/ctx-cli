# ECM Benchmarks

Comprehensive evaluation suite for Explicit Context Management (ECM) with official benchmark harness integrations.

## Directory Structure

```
benchmarks/
├── core/                      # Shared infrastructure
│   ├── harness_protocol.py    # Abstract harness interface
│   ├── base_agent.py          # Base agent class
│   └── metrics.py             # Token & correctness metrics
│
├── harnesses/                 # Official benchmark integrations
│   ├── swe_bench_cl/          # SWE-Bench-CL (thomasjoshi/agents-never-forget)
│   ├── lifelong_agent_bench/  # LifelongAgentBench (caixd-220529/LifelongAgentBench)
│   ├── appworld/              # AppWorld (StonyBrookNLP/appworld)
│   └── osworld/               # OSWorld (xlang-ai/OSWorld)
│
├── retrieval/                 # Retrieval benchmarks (NOT continual learning)
│   ├── run_locomo_semantic.py # LOCOMO semantic evaluation
│   └── run_locomo_style.py    # LOCOMO style evaluation
│
├── runners/                   # Unified CLI runners
│   └── run_benchmark.py       # Main benchmark runner
│
├── memory/                    # Memory agent implementations
│   └── agents/                # ECM, RAG, Mem0, Letta agents
│
├── results/                   # Benchmark results (JSON)
├── configs/                   # Configuration files
└── deprecated/                # Archived broken implementations
```

## Quick Start

```bash
# Install dependencies
uv sync --all-groups

# List available benchmarks
uv run benchmarks/runners/run_benchmark.py --list

# Run mini evaluation (quick validation)
uv run benchmarks/runners/run_benchmark.py --benchmark swe-bench-cl --size mini

# Run full evaluation (paper results)
uv run benchmarks/runners/run_benchmark.py --benchmark swe-bench-cl --size full
```

## Benchmark Categories

### Continual Learning (CL) Benchmarks

These are the primary evaluation targets for ECM. They test **knowledge retention across sequential tasks**.

| Benchmark | Tasks | Description |
|-----------|-------|-------------|
| **SWE-Bench-CL** | 273 | GitHub issues in 8 repository sequences |
| **LifelongAgentBench** | 1,400 | Skill reuse in DB/OS/KG environments |

#### SWE-Bench-CL

Tests agent ability to learn and reuse patterns within a codebase:

```bash
# Run Django sequence
uv run benchmarks/runners/run_benchmark.py \
  --benchmark swe-bench-cl \
  --sequence django \
  --size mini

# Run with baseline comparison
uv run benchmarks/runners/run_benchmark.py \
  --benchmark swe-bench-cl \
  --compare-baseline
```

**Setup:** See `harnesses/swe_bench_cl/SETUP.md`

#### LifelongAgentBench

Tests skill transfer across database, OS, and knowledge graph tasks:

```bash
# Run DB environment
uv run benchmarks/runners/run_benchmark.py \
  --benchmark lifelong-agent-bench \
  --environment db \
  --size mini

# Run all environments
uv run benchmarks/runners/run_benchmark.py \
  --benchmark lifelong-agent-bench \
  --environment all
```

**Setup:** See `harnesses/lifelong_agent_bench/SETUP.md`

### Long-Horizon Benchmarks

These test multi-step task completion with accumulated context:

| Benchmark | Tasks | Description |
|-----------|-------|-------------|
| **AppWorld** | 750 | Multi-app interaction (9 apps) |
| **OSWorld** | 369 | Desktop automation (Ubuntu VM) |

#### AppWorld

Tests agent ability to complete multi-step tasks across applications:

```bash
uv run benchmarks/runners/run_benchmark.py \
  --benchmark appworld \
  --size mini
```

**Setup:** `pip install appworld && appworld install`

#### OSWorld

Tests desktop automation with real VM environments:

```bash
uv run benchmarks/runners/run_benchmark.py \
  --benchmark osworld \
  --size mini
```

**Setup:** See `harnesses/osworld/SETUP.md` (requires Docker or VMware)

### Retrieval Benchmarks (NOT CL)

These are **NOT continual learning** benchmarks but useful baselines:

```bash
# LOCOMO - Long context memory
uv run benchmarks/retrieval/run_locomo_semantic.py

# MemoryAgentBench - Accurate Retrieval
uv run benchmarks/run_memoryagentbench.py --sub-dataset AR
```

### Planned Benchmarks (Future Work)

The following benchmarks are under consideration for integration, following their usage in the **Confucius Code Agent (CCA)** paper [arXiv:2512.10398]:

*   **SWE-Bench-Pro**: A larger dataset (731 tasks) for evaluating scalable coding agents.
*   **PyTorch-Bench**: A custom benchmark for large-scale debugging workflows.
*   **SWE-Bench-Verified**: Already partially covered by SWE-Bench-CL, but direct integration is planned.

## Evaluation Sizes

| Size | Tasks | Use Case |
|------|-------|----------|
| `mini` | 5-10 | Quick validation during development |
| `small` | 15-30 | Intermediate testing |
| `full` | 50-273 | Paper evaluation |

## Metrics

### Token Metrics

- **Peak Context**: Maximum context window size reached
- **Final Context**: Context size at end of sequence
- **Growth Rate**: Tokens added per task
- **Total I/O**: Total input/output tokens used

### Correctness Metrics

- **Success Rate**: Percentage of tasks completed correctly
- **Forward Transfer (FWT)**: Performance gain from prior knowledge
- **Backward Transfer (BWT)**: Impact on earlier task performance
- **Knowledge Retention (KRT)**: Accuracy on callback questions

## Results

Results are saved to `benchmarks/results/`:

```
results/
├── swe-bench-cl_mini_20250106_123456.json
├── appworld_full_20250106_234567.json
└── ...
```

Each result includes:
- Token trajectory (per-task context sizes)
- Correctness metrics
- Execution logs
- Configuration used

## Critical Rules

1. **NEVER reset agent between CL tasks** - Memory must persist
2. **ALWAYS use official harness verification** - No heuristics
3. **ALWAYS track tokens** - Use `CumulativeTokenReport`
4. **DO reset between sequences** - New episode = fresh state

## Adding New Benchmarks

1. Create harness directory: `harnesses/{name}/`
2. Implement `OfficialHarness` protocol in `adapter.py`
3. Create `SETUP.md` with installation instructions
4. Register in `harnesses/__init__.py`
5. Add config to `runners/run_benchmark.py`

## Requirements

- Python 3.9+
- `uv` package manager
- `OPENAI_API_KEY` environment variable
- Docker (for SWE-Bench-CL test execution)
- Optional: VM setup for OSWorld
