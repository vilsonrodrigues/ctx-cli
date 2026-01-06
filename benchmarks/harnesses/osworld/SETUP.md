# OSWorld Setup

## Overview

OSWorld provides real computer environments (Ubuntu, Windows, macOS) for
evaluating multimodal agents on desktop automation tasks.

**Repository**: https://github.com/xlang-ai/OSWorld
**Website**: https://os-world.github.io/

## Installation

### Option 1: Docker (Recommended for development)

```bash
# Clone official repo
git clone https://github.com/xlang-ai/OSWorld.git /tmp/osworld

# Install dependencies
cd /tmp/osworld
pip install -r requirements.txt

# Pull Docker images
docker pull osworld/ubuntu:latest
```

### Option 2: AWS (For full evaluation)

```bash
# Configure AWS credentials
aws configure

# Setup parallel evaluation infrastructure
# See: https://github.com/xlang-ai/OSWorld/blob/main/PUBLIC_EVALUATION_GUIDELINE.md
```

## Requirements

- Docker or VMware/VirtualBox
- GPU recommended for vision models
- 16GB+ RAM for VM execution
- AWS account for parallel evaluation

## Task Categories

369 real-world computer tasks across:

| Category | Examples | Tasks |
|----------|----------|-------|
| Web | Fill forms, navigate sites | ~120 |
| Desktop | Office apps, file management | ~100 |
| System | Settings, installations | ~80 |
| Multi-app | Cross-application workflows | ~69 |

## Running with ECM

```bash
# Mini evaluation (5 tasks, Docker mode)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark osworld \
    --size mini \
    --mode docker

# Full evaluation requires AWS setup
uv run benchmarks/runners/run_benchmark.py \
    --benchmark osworld \
    --size full \
    --mode aws
```

## Agent Interface

OSWorld agents receive:
- **Screenshot**: Current desktop state (PNG)
- **Accessibility tree**: DOM-like structure (optional)
- **Task instruction**: Natural language goal

And output:
- **Mouse actions**: click, drag, scroll
- **Keyboard actions**: type, hotkeys
- **Coordinates**: (x, y) for interactions

## Metrics

- **Task Completion**: Binary success based on final state
- **Action Efficiency**: Steps vs optimal solution
- **Error Recovery**: Ability to recover from mistakes
- **Cross-app Workflow**: Multi-application task success

## Correctness Verification

Each task has a custom evaluation script that checks:
- Final application state
- File contents (for file operations)
- Settings values (for configuration tasks)
- Visual assertions (screenshot comparison)

## Memory Requirements for ECM

For OSWorld, ECM should track:
- Successful action patterns
- Error recovery strategies
- Application-specific shortcuts
- Workflow sequences

## Key Files

- `adapter.py`: ECM adapter for visual interaction
- `runner.py`: Main evaluation script (Docker/AWS modes)
- `evaluation_examples/`: Sample task configurations
