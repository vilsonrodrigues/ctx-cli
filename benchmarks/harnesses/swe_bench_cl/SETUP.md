# SWE-Bench-CL Setup

## Overview

SWE-Bench-CL (Continual Learning) evaluates agents on sequential GitHub issue resolution
with knowledge retention. It's the primary CL benchmark for code agents.

**Repository**: https://github.com/thomasjoshi/agents-never-forget
**Paper**: https://arxiv.org/abs/2507.00014

## Installation

```bash
# Clone official harness
git clone https://github.com/thomasjoshi/agents-never-forget.git /tmp/swe-bench-cl

# Install dependencies
pip install -r /tmp/swe-bench-cl/requirements.txt

# Copy data files
cp /tmp/swe-bench-cl/data/SWE-Bench-CL-Curriculum.json benchmarks/harnesses/swe_bench_cl/data/
```

## Dataset Structure

The dataset contains 273 tasks organized into 8 repository sequences:

| Repository | Tasks | Focus |
|------------|-------|-------|
| django | ~50 | Web framework |
| flask | ~30 | Microframework |
| requests | ~25 | HTTP library |
| scikit-learn | ~40 | ML library |
| sympy | ~35 | Symbolic math |
| matplotlib | ~30 | Plotting |
| pandas | ~35 | Data analysis |
| numpy | ~28 | Numerical computing |

## Running with ECM

```bash
# Mini evaluation (5 tasks)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark swe-bench-cl \
    --size mini \
    --sequence django

# Full evaluation (all tasks in sequence)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark swe-bench-cl \
    --size full \
    --sequence django
```

## Metrics

- **Success Rate**: Percentage of tasks with passing tests
- **Forward Transfer (FWT)**: Performance improvement from prior tasks
- **Backward Transfer (BWT)**: Impact on earlier task recall
- **Context Growth**: Token usage trajectory

## Docker Requirements

For test execution, Docker is required:

```bash
# Verify Docker is available
docker --version

# Pull SWE-bench evaluation image
docker pull swebench/evaluation:latest
```

## Correctness Verification

SWE-Bench-CL runs actual test suites to verify patches:

1. Agent generates patch
2. Patch is applied to repository
3. Test suite is executed
4. Success = all targeted tests pass

**Important**: Never use heuristic matching (keywords, file mentions) as success metric.
Only actual test results count.

## Key Files

- `data/SWE-Bench-CL-Curriculum.json`: Task sequences with chronological ordering
- `adapter.py`: ECM adapter for the harness
- `runner.py`: Main evaluation script
