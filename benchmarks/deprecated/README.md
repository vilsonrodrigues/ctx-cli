# Deprecated Benchmark Implementations

This directory contains archived benchmark implementations that have been superseded by the official harness integrations in `benchmarks/harnesses/`.

## Why Deprecated

These implementations had critical issues:

| File | Issue |
|------|-------|
| `run_agentcompany.py` | No official harness exists; synthetic data only |
| `run_appworld.py` | Used synthetic tasks; reset agent per task (breaks CL) |
| `run_osworld.py` | Trivial simulation (5 commands); no real VM execution |
| `run_swe_bench_cl.py` | Synthetic fallback; heuristic matching instead of tests |
| `run_*_internal.py` | Development/debug versions of above |

## Migration

Use the new implementations in `benchmarks/harnesses/`:

```bash
# Old (deprecated)
uv run benchmarks/longhorizon/run_appworld.py

# New (correct)
uv run benchmarks/runners/run_benchmark.py --benchmark appworld --size mini
```

## Key Differences

### Old (Incorrect)
- Synthetic data generation
- Agent reset between tasks
- Heuristic success matching (keywords)
- No official harness integration

### New (Correct)
- Official datasets from harness repos
- Memory persists across task sequences (CL)
- Official test execution for verification
- Full harness protocol compliance
