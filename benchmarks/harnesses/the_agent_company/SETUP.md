# TheAgentCompany Harness Setup

## Overview

TheAgentCompany is a benchmark for evaluating AI agents on realistic workplace tasks.
It provides a persistent company environment with:

- **GitLab**: Code repositories and merge requests
- **Plane**: Project management and sprint planning
- **ownCloud**: File storage and document sharing
- **RocketChat**: Team communication

## Requirements

- Docker and Docker Compose
- 30+ GB disk space
- Linux or macOS (Windows via WSL2)

## Quick Setup

### 1. Install Docker

If Docker is not installed:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER

# macOS
brew install docker docker-compose
```

### 2. Setup TheAgentCompany Services

```bash
# Allow Docker socket access
sudo chmod 666 /var/run/docker.sock

# Run the official setup script
curl -fsSL https://github.com/TheAgentCompany/the-agent-company-backup-data/releases/download/setup-script-20241208/setup.sh | sh
```

This script will:
- Pull required Docker images
- Set up GitLab, Plane, ownCloud, and RocketChat
- Configure networking between services
- Initialize sample data

### 3. Verify Installation

```bash
# Check services are running
docker compose ps

# Test GitLab access
curl http://localhost:8929

# Test Plane access
curl http://localhost:3000

# Test ownCloud access
curl http://localhost:8080

# Test RocketChat access
curl http://localhost:3100
```

## Manual Setup (Alternative)

If the script doesn't work, you can set up manually:

### Clone Repository

```bash
git clone https://github.com/TheAgentCompany/TheAgentCompany.git
cd TheAgentCompany
```

### Start Services

```bash
cd servers
docker compose up -d
```

### Wait for Initialization

Services take 5-10 minutes to fully initialize:

```bash
# Monitor logs
docker compose logs -f

# Check health
docker compose ps
```

## Configuration

### Environment Variables

Set these before running evaluations:

```bash
export TAC_SERVER_HOSTNAME=localhost
export TAC_GITLAB_URL=http://localhost:8929
export TAC_PLANE_URL=http://localhost:3000
export TAC_OWNCLOUD_URL=http://localhost:8080
export TAC_ROCKETCHAT_URL=http://localhost:3100
```

### Service Credentials

Default credentials (set during setup):

| Service | Username | Password |
|---------|----------|----------|
| GitLab | root | password123 |
| Plane | admin@theagentcompany.com | admin123 |
| ownCloud | admin | admin123 |
| RocketChat | admin | admin123 |

## Running Evaluations

### With ECM Agent

```bash
# Run all roles
uv run benchmarks/runners/run_benchmark.py \
    --benchmark the-agent-company \
    --size mini \
    --model gpt-4.1-mini

# Run specific role
uv run benchmarks/runners/run_benchmark.py \
    --benchmark the-agent-company \
    --size mini \
    --model gpt-4.1-mini \
    --config '{"role": "swe"}'
```

### Simulation Mode

If services are not running, the harness operates in simulation mode:
- Tasks are presented to the agent
- Checkpoint detection uses keyword matching
- Results are approximate (not suitable for paper claims)

## Task Catalog

### Available Roles

| Role | Task Count | Description |
|------|------------|-------------|
| SWE | 3 | Software engineering (code review, debugging, docs) |
| PM | 2 | Product management (sprint planning, status reports) |
| DataScientist | 2 | Data analysis and ML model training |
| HR | 1 | Employee onboarding and management |
| Finance | 1 | Expense review and budget management |
| Admin | 1 | Meeting organization and scheduling |

### Checkpoint Evaluation

Each task has multiple checkpoints:
- Partial credit is given for completed checkpoints
- Success threshold: 50% of checkpoints
- Full task list in `adapter.py:TASK_CATALOG`

## Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
sudo systemctl status docker

# Check available resources
docker system df

# Clean up old containers
docker system prune -a
```

### Port Conflicts

Default ports:
- GitLab: 8929
- Plane: 3000
- ownCloud: 8080
- RocketChat: 3100

If these conflict with existing services:

```bash
# Edit docker-compose.yml to change ports
# Then restart services
docker compose down
docker compose up -d
```

### Memory Issues

TheAgentCompany services require ~8GB RAM minimum.

```bash
# Check memory usage
docker stats

# Increase Docker memory limit (Docker Desktop settings)
```

## References

- Repository: https://github.com/TheAgentCompany/TheAgentCompany
- Paper: (link when published)
- Benchmark details: https://github.com/TheAgentCompany/TheAgentCompany#benchmark

## ECM Integration Notes

The adapter uses ECM scopes to organize company knowledge:

```
company/
├── codebase    # Code patterns, repo structure
├── team        # Team structure, responsibilities
├── tools       # Tool usage (GitLab, Plane, etc.)
└── processes   # Business workflows

task/
├── swe_gitlab_pr_001
├── pm_sprint_planning_001
└── ...
```

This allows knowledge to persist across tasks within a session,
demonstrating ECM's value for long-horizon agentic work.
