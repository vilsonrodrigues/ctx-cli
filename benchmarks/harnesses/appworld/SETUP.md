# AppWorld Setup

## Overview

AppWorld provides a realistic multi-app environment with 9 simulated applications
for evaluating interactive code generation agents.

**Repository**: https://github.com/StonyBrookNLP/appworld
**Website**: https://appworld.dev/

## Installation

```bash
# Install AppWorld package
pip install appworld

# Initialize environment
appworld install

# Download data
appworld download data

# Verify installation
appworld verify tests     # ~2-3 minutes
appworld verify tasks     # ~2-3 minutes for train/dev
```

## Applications

AppWorld simulates 9 day-to-day applications:

| App | Description | API Endpoints |
|-----|-------------|---------------|
| Email | Gmail-like email client | ~40 |
| Calendar | Google Calendar-like scheduling | ~25 |
| Notes | Simple note-taking app | ~15 |
| Todo | Task management | ~20 |
| Contacts | Address book | ~15 |
| Files | File system operations | ~30 |
| Browser | Web browsing simulation | ~35 |
| Shopping | E-commerce platform | ~50 |
| Social | Social media platform | ~45 |

## Running with ECM

```bash
# Mini evaluation (5 tasks)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark appworld \
    --size mini

# Full evaluation (50 tasks)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark appworld \
    --size full
```

## Task Structure

Tasks require multi-step interactions:

```python
from appworld import AppWorld

with AppWorld(task_id="email_001") as world:
    while not world.is_complete():
        # Get current state
        obs = world.get_observation()

        # Agent generates action (Python code)
        code = agent.generate(obs)

        # Execute in AppWorld
        result = world.execute(code)

    # Get final evaluation
    success = world.evaluate()
```

## Metrics

- **Task Completion Rate**: Percentage of fully completed tasks
- **Partial Progress**: Steps completed before failure
- **Action Efficiency**: Optimal vs actual action count
- **State Consistency**: No invalid state transitions

## State Persistence

AppWorld maintains persistent state within a task:
- Files created remain available
- Email sent appears in recipient's inbox
- Calendar events are scheduled
- Shopping cart persists

**Important**: State does NOT persist across different tasks by default.
For CL evaluation, run tasks sequentially with shared state.

## Key Files

- `adapter.py`: ECM adapter for multi-turn interaction
- `runner.py`: Main evaluation script
