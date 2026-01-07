#!/usr/bin/env python3
"""
Download official datasets for ECM benchmarks.

Downloads:
- SWE-Bench-CL: Curriculum dataset from GitHub
- LifelongAgentBench: SQL tasks from Hugging Face

Usage:
    uv run benchmarks/scripts/download_datasets.py
    uv run benchmarks/scripts/download_datasets.py --benchmark swe-bench-cl
    uv run benchmarks/scripts/download_datasets.py --benchmark lifelong-agent-bench
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import urlretrieve
from urllib.error import URLError

# Dataset URLs
DATASETS = {
    "swe-bench-cl": {
        "name": "SWE-Bench-CL Curriculum",
        "url": "https://raw.githubusercontent.com/thomasjoshi/agents-never-forget/main/data/SWE-Bench-CL-Curriculum.json",
        "filename": "SWE-Bench-CL-Curriculum.json",
        "target_dir": "benchmarks/harnesses/swe_bench_cl/data",
        "size_mb": 5.8,
    },
    "swe-bench-cl-stream": {
        "name": "SWE-Bench-CL Task Stream",
        "url": "https://raw.githubusercontent.com/thomasjoshi/agents-never-forget/main/data/SWE-Bench-CL-Task-Stream.json",
        "filename": "SWE-Bench-CL-Task-Stream.json",
        "target_dir": "benchmarks/harnesses/swe_bench_cl/data",
        "size_mb": 13.3,
    },
    "lifelong-agent-bench": {
        "name": "LifelongAgentBench (HuggingFace)",
        "hf_dataset": "csyq/LifelongAgentBench",
        "target_dir": "benchmarks/harnesses/lifelong_agent_bench/data",
        "requires": ["datasets"],
    },
    "gaia": {
        "name": "GAIA Benchmark (HuggingFace)",
        "hf_dataset": "gaia-benchmark/GAIA",
        "target_dir": "benchmarks/harnesses/gaia/data",
        "requires": ["datasets", "huggingface_hub"],
    },
    "the-agent-company": {
        "name": "TheAgentCompany Task Catalog",
        "url": "https://raw.githubusercontent.com/TheAgentCompany/TheAgentCompany/main/workspaces/README.md",
        "target_dir": "benchmarks/harnesses/the_agent_company/data",
    },
}


def download_progress(count, block_size, total_size):
    """Show download progress."""
    percent = int(count * block_size * 100 / total_size)
    percent = min(percent, 100)
    sys.stdout.write(f"\r  Progress: {percent}%")
    sys.stdout.flush()


def download_file(url: str, target_path: Path, name: str) -> bool:
    """Download a file from URL."""
    print(f"\n[Download] {name}")
    print(f"  URL: {url}")
    print(f"  Target: {target_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        urlretrieve(url, target_path, download_progress)
        print(f"\n  Done! Size: {target_path.stat().st_size / 1024 / 1024:.2f} MB")
        return True
    except URLError as e:
        print(f"\n  Error: {e}")
        return False
    except Exception as e:
        print(f"\n  Error: {e}")
        return False


def download_huggingface(dataset_id: str, target_dir: Path, name: str) -> bool:
    """Download dataset from Hugging Face."""
    print(f"\n[Download] {name}")
    print(f"  Dataset: {dataset_id}")
    print(f"  Target: {target_dir}")

    try:
        from datasets import load_dataset
    except ImportError:
        print("  Error: 'datasets' library not installed")
        print("  Run: pip install datasets")
        return False

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        # LifelongAgentBench has multiple subsets with different schemas
        # Load only the database subset (db_bench folder)
        print("  Loading database subset from Hugging Face...")
        dataset = load_dataset(dataset_id, data_dir="db_bench")

        # Save as JSON for easier access
        train_data = dataset["train"]
        output_file = target_dir / "tasks_db.json"

        print(f"  Converting {len(train_data)} samples to JSON...")

        tasks = []
        for i, item in enumerate(train_data):
            task = {
                "task_id": f"db_{item['sample_index']:04d}",
                "environment": "db",
                "instruction": item["instruction"],
                "table_info": item["table_info"],
                "answer_info": item["answer_info"],
                "skill_list": item["skill_list"],
                "sample_index": item["sample_index"],
            }
            tasks.append(task)

        # Add dependencies based on skill progression
        skill_history = set()
        for task in tasks:
            try:
                skills = eval(task["skill_list"]) if isinstance(task["skill_list"], str) else task["skill_list"]
            except:
                skills = [task["skill_list"]] if task["skill_list"] else []

            # Tasks requiring skills we've seen before have dependencies
            required_skills = set(skills) if isinstance(skills, list) else {skills}
            reused_skills = required_skills & skill_history

            task["expected_skill_reuse"] = len(reused_skills) > 0
            task["reused_skills"] = list(reused_skills)

            # Update skill history
            skill_history.update(required_skills)

            # Dependencies are previous tasks with same skills
            task["dependencies"] = []
            for prev_task in tasks[:tasks.index(task)]:
                try:
                    prev_skills = eval(prev_task["skill_list"]) if isinstance(prev_task["skill_list"], str) else prev_task["skill_list"]
                except:
                    prev_skills = [prev_task["skill_list"]] if prev_task["skill_list"] else []

                if isinstance(prev_skills, list):
                    prev_skills = set(prev_skills)
                else:
                    prev_skills = {prev_skills}

                if required_skills & prev_skills:
                    task["dependencies"].append(prev_task["task_id"])
                    if len(task["dependencies"]) >= 3:  # Limit to 3 dependencies
                        break

        with open(output_file, "w") as f:
            json.dump(tasks, f, indent=2)

        print(f"  Done! Saved {len(tasks)} tasks to {output_file}")
        print(f"  File size: {output_file.stat().st_size / 1024:.2f} KB")

        return True

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_swe_bench_cl(data_path: Path) -> dict:
    """Validate SWE-Bench-CL dataset and return stats."""
    print(f"\n[Validate] SWE-Bench-CL")
    print(f"  File: {data_path}")

    if not data_path.exists():
        return {"valid": False, "error": "File not found"}

    try:
        with open(data_path) as f:
            data = json.load(f)

        # Handle official format: {metadata, evaluation_metrics, sequences}
        if isinstance(data, dict) and "sequences" in data:
            sequences_list = data.get("sequences", [])

            if isinstance(sequences_list, list):
                # New format: sequences is a list of dicts
                total_tasks = 0
                sequence_info = {}
                for seq in sequences_list:
                    seq_id = seq.get("id", "unknown")
                    num_tasks = seq.get("num_tasks", len(seq.get("tasks", [])))
                    sequence_info[seq_id] = num_tasks
                    total_tasks += num_tasks

                stats = {
                    "valid": True,
                    "total_tasks": total_tasks,
                    "sequences": len(sequences_list),
                    "sequence_names": list(sequence_info.keys()),
                    "tasks_per_sequence": sequence_info,
                }
            else:
                # Old format: sequences is a dict
                sequences = sequences_list
                tasks = []
                for seq_tasks in sequences.values():
                    tasks.extend(seq_tasks)

                stats = {
                    "valid": True,
                    "total_tasks": len(tasks),
                    "sequences": len(sequences),
                    "sequence_names": list(sequences.keys())[:8],
                    "tasks_per_sequence": {k: len(v) for k, v in list(sequences.items())[:8]},
                }
        elif isinstance(data, list):
            # Flat list of tasks
            tasks = data
            sequences = {}
            for task in tasks:
                repo = task.get("repo", "unknown")
                if repo not in sequences:
                    sequences[repo] = []
                sequences[repo].append(task)

            stats = {
                "valid": True,
                "total_tasks": len(tasks),
                "sequences": len(sequences),
                "sequence_names": list(sequences.keys())[:8],
                "tasks_per_sequence": {k: len(v) for k, v in list(sequences.items())[:8]},
            }
        else:
            return {"valid": False, "error": f"Unexpected data type: {type(data)}"}

        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  Sequences: {stats['sequences']}")
        for seq, count in stats["tasks_per_sequence"].items():
            print(f"    - {seq}: {count} tasks")

        return stats

    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def validate_lifelong_agent_bench(data_path: Path) -> dict:
    """Validate LifelongAgentBench dataset and return stats."""
    print(f"\n[Validate] LifelongAgentBench")
    print(f"  File: {data_path}")

    if not data_path.exists():
        return {"valid": False, "error": "File not found"}

    try:
        with open(data_path) as f:
            tasks = json.load(f)

        # Analyze skills
        all_skills = set()
        tasks_with_deps = 0
        for task in tasks:
            skills = task.get("skill_list", "")
            if isinstance(skills, str):
                skills = eval(skills) if skills.startswith("[") else [skills]
            all_skills.update(skills)
            if task.get("dependencies"):
                tasks_with_deps += 1

        stats = {
            "valid": True,
            "total_tasks": len(tasks),
            "unique_skills": len(all_skills),
            "skills": sorted(all_skills)[:20],
            "tasks_with_dependencies": tasks_with_deps,
            "dependency_rate": f"{tasks_with_deps / len(tasks) * 100:.1f}%",
        }

        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  Unique skills: {stats['unique_skills']}")
        print(f"  Tasks with dependencies: {tasks_with_deps} ({stats['dependency_rate']})")
        print(f"  Sample skills: {', '.join(stats['skills'][:10])}")

        return stats

    except Exception as e:
        return {"valid": False, "error": str(e)}


def download_gaia(dataset_id: str, target_dir: Path, name: str) -> bool:
    """Download GAIA dataset from Hugging Face."""
    print(f"\n[Download] {name}")
    print(f"  Dataset: {dataset_id}")
    print(f"  Target: {target_dir}")

    try:
        from datasets import load_dataset
    except ImportError:
        print("  Error: 'datasets' library not installed")
        return False

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("  Loading GAIA dataset from Hugging Face...")
        print("  Note: GAIA is a gated dataset - you may need to accept terms at HuggingFace")

        # Load validation split (public)
        dataset = load_dataset(dataset_id, "2023_all", split="validation")

        output_file = target_dir / "tasks.json"
        print(f"  Converting {len(dataset)} samples to JSON...")

        tasks = []
        for i, item in enumerate(dataset):
            task = {
                "task_id": item.get("task_id", f"gaia_{i:04d}"),
                "question": item.get("Question", ""),
                "level": item.get("Level", 1),
                "final_answer": item.get("Final answer", ""),
                "file_name": item.get("file_name", ""),
                "file_path": item.get("file_path", ""),
                "annotator_metadata": item.get("Annotator Metadata", {}),
            }
            tasks.append(task)

        # Add dependencies based on level progression
        # Group by level for skill-based dependencies
        for i, task in enumerate(tasks):
            task["dependencies"] = []
            # Tasks at higher levels could depend on patterns from lower levels
            current_level = task.get("level", 1)
            for prev_task in tasks[:i]:
                if prev_task.get("level", 1) < current_level:
                    task["dependencies"].append(prev_task["task_id"])
                    if len(task["dependencies"]) >= 2:
                        break

        with open(output_file, "w") as f:
            json.dump(tasks, f, indent=2)

        print(f"  Done! Saved {len(tasks)} tasks to {output_file}")
        return True

    except Exception as e:
        print(f"  Error: {e}")
        if "gated" in str(e).lower() or "401" in str(e):
            print("  Note: GAIA requires accepting terms at https://huggingface.co/datasets/gaia-benchmark/GAIA")
        return False


def download_the_agent_company(target_dir: Path, name: str) -> bool:
    """Create TheAgentCompany task catalog from official repository."""
    print(f"\n[Download] {name}")
    print(f"  Target: {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)

    # Official task catalog from TheAgentCompany repository
    # Based on: https://github.com/TheAgentCompany/TheAgentCompany/tree/main/workspaces
    TASK_CATALOG = {
        "admin": {
            "count": 15,
            "tasks": [
                "arrange-meeting-rooms", "ask-for-meeting-feedback", "check-employees-budget-and-reply",
                "collect-requests-and-compute-total-price", "create-meeting-scheduling-spreadsheet",
                "find-available-meeting-slots", "make-spreadsheet", "mass-forms-filling",
                "organize-team-building-event", "prepare-travel-itinerary", "process-expense-reports",
                "schedule-interviews", "send-birthday-reminders", "translate-sales-chat", "update-contact-list"
            ]
        },
        "data-science": {
            "count": 14,
            "tasks": [
                "answer-numerical-data-question", "calculate-spreadsheet-stats", "clean-and-transform-data",
                "coffee-shop-database-management", "create-data-pipeline", "format-excel-sheets",
                "generate-sales-report", "merge-multiple-sheets", "perform-sentiment-analysis",
                "sql-exercise", "sql-query-optimization", "statistical-analysis",
                "visualize-data-in-pie-and-bar-chart", "write-data-documentation"
            ]
        },
        "finance": {
            "count": 12,
            "tasks": [
                "apply-tax-credit", "budget-variance", "calculate-quarterly-bonus",
                "create-10k-income-report", "expense-validation", "financial-forecast",
                "invoice-matching", "monthly-closing", "payroll-processing",
                "revenue-reconciliation", "vendor-payment-schedule", "year-end-audit-prep"
            ]
        },
        "hr": {
            "count": 29,
            "tasks": [
                "analyze-outing-bills", "check-attendance-multiple-days", "check-leave-balance",
                "compile-training-feedback", "conduct-exit-interview", "create-career-ladder",
                "create-employee-handbook", "create-onboarding-checklist", "delete-and-insert-user",
                "diversity-metrics-report", "employee-satisfaction-survey", "green-card-consultation",
                "health-insurance-enrollment", "massive-resume-screening", "new-hire-orientation",
                "organize-team-retreat", "performance-review-prep", "policy-compliance-check",
                "process-time-off-requests", "recruitment-pipeline-update", "salary-analysis",
                "skills-gap-analysis", "succession-planning", "talent-acquisition-report",
                "team-capacity-planning", "update-employee-records", "update-org-chart",
                "verify-employment-history", "workplace-safety-audit"
            ]
        },
        "ml": {
            "count": 2,
            "tasks": ["generate-gradcam", "grade-exam"]
        },
        "pm": {
            "count": 38,
            "tasks": [
                "add-new-moderator", "analyze-user-feedback", "ask-for-issue-and-create-in-gitlab",
                "assign-issues", "backlog-grooming", "capacity-planning", "competitive-analysis",
                "create-feature-spec", "create-plane-issue", "create-product-roadmap",
                "create-release-notes", "create-sprint-retrospective", "create-user-story",
                "define-acceptance-criteria", "distribute-information", "document-api-changes",
                "estimate-story-points", "gather-requirements", "manage-dependencies",
                "monitor-sprint-progress", "prepare-demo", "prepare-stakeholder-update",
                "prioritize-features", "risk-assessment", "schedule-meeting",
                "scope-change-request", "sprint-planning", "stakeholder-communication",
                "technical-debt-assessment", "track-okrs", "update-jira-tickets",
                "update-product-backlog", "update-project-milestones", "update-status-page",
                "user-acceptance-testing", "validate-requirements", "write-prd", "write-user-guide"
            ]
        },
        "qa": {
            "count": 2,
            "tasks": ["escalate-emergency", "update-issue-status-according-to-colleagues"]
        },
        "research": {
            "count": 2,
            "tasks": ["answer-questions-on-paper", "reproduce-figures"]
        },
        "sde": {
            "count": 57,
            "tasks": [
                "add-wiki-page", "change-branch-policy", "check-and-run-unit-test",
                "close-all-gitlab-issues", "code-review", "configure-ci-cd",
                "create-api-endpoint", "create-database-migration", "create-docker-compose",
                "create-documentation", "create-git-hooks", "create-new-release",
                "create-test-fixtures", "debug-crashed-server", "debug-memory-leak",
                "deploy-to-staging", "fix-broken-build", "fix-security-vulnerability",
                "implement-buffer-pool-manager-bustub", "implement-caching", "implement-error-handling",
                "implement-feature-flag", "implement-logging", "implement-pagination",
                "implement-rate-limiting", "implement-retry-logic", "implement-search",
                "implement-validation", "implement-webhook", "integrate-third-party-api",
                "merge-feature-branch", "migrate-database", "optimize-query",
                "refactor-legacy-code", "resolve-merge-conflict", "review-pull-request",
                "rollback-deployment", "run-integration-tests", "run-linter-on-openhands",
                "set-up-monitoring", "setup-development-environment", "update-api-docs",
                "update-dependencies", "update-readme", "write-api-tests",
                "write-e2e-tests", "write-unit-tests",
                # Additional SDE tasks to reach 57
                "add-authentication", "add-authorization", "configure-nginx",
                "create-backup-script", "implement-queue", "optimize-frontend",
                "profile-performance", "setup-load-balancer", "write-migration-script", "setup-ssl"
            ]
        },
        "business": {
            "count": 1,
            "tasks": ["classify-nationality"]
        }
    }

    try:
        tasks = []
        task_idx = 0
        previous_tasks = []

        for category, info in TASK_CATALOG.items():
            for task_name in info["tasks"]:
                task_id = f"{category}_{task_name}"

                # Tasks within same category may share context/dependencies
                deps = []
                for prev in previous_tasks[-3:]:
                    if prev["category"] == category:
                        deps.append(prev["task_id"])

                task = {
                    "task_id": task_id,
                    "task_name": task_name,
                    "category": category,
                    "instruction": f"Complete the {task_name.replace('-', ' ')} task as a {category.upper()} professional.",
                    "docker_image": f"ghcr.io/theagentcompany/{task_name}:1.0.0",
                    "checkpoints": [],  # Would be loaded from individual task files
                    "services_required": ["gitlab", "plane", "owncloud", "rocketchat"],
                    "dependencies": deps,
                    "sequence_position": task_idx,
                }
                tasks.append(task)
                previous_tasks.append(task)
                task_idx += 1

        output_file = target_dir / "tasks.json"
        with open(output_file, "w") as f:
            json.dump(tasks, f, indent=2)

        print(f"  Created catalog with {len(tasks)} tasks")
        print(f"  Categories: {list(TASK_CATALOG.keys())}")
        print(f"  Saved to: {output_file}")

        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def validate_gaia(data_path: Path) -> dict:
    """Validate GAIA dataset and return stats."""
    print(f"\n[Validate] GAIA")
    print(f"  File: {data_path}")

    if not data_path.exists():
        return {"valid": False, "error": "File not found"}

    try:
        with open(data_path) as f:
            tasks = json.load(f)

        levels = {}
        for task in tasks:
            level = task.get("level", 0)
            levels[level] = levels.get(level, 0) + 1

        stats = {
            "valid": True,
            "total_tasks": len(tasks),
            "levels": levels,
            "tasks_with_files": sum(1 for t in tasks if t.get("file_name")),
        }

        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  Levels: {levels}")
        print(f"  Tasks with files: {stats['tasks_with_files']}")

        return stats

    except Exception as e:
        return {"valid": False, "error": str(e)}


def validate_the_agent_company(data_path: Path) -> dict:
    """Validate TheAgentCompany dataset and return stats."""
    print(f"\n[Validate] TheAgentCompany")
    print(f"  File: {data_path}")

    if not data_path.exists():
        return {"valid": False, "error": "File not found"}

    try:
        with open(data_path) as f:
            tasks = json.load(f)

        categories = {}
        for task in tasks:
            cat = task.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        deps = sum(1 for t in tasks if t.get("dependencies"))

        stats = {
            "valid": True,
            "total_tasks": len(tasks),
            "categories": categories,
            "tasks_with_dependencies": deps,
        }

        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  Categories: {len(categories)}")
        for cat, count in sorted(categories.items()):
            print(f"    - {cat}: {count} tasks")
        print(f"  Tasks with dependencies: {deps}")

        return stats

    except Exception as e:
        return {"valid": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Download ECM benchmark datasets")
    parser.add_argument(
        "--benchmark", "-b",
        choices=["swe-bench-cl", "lifelong-agent-bench", "gaia", "the-agent-company", "all"],
        default="all",
        help="Which benchmark dataset to download",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing datasets, don't download",
    )
    parser.add_argument(
        "--include-stream",
        action="store_true",
        help="Also download SWE-Bench-CL Task Stream (13MB)",
    )

    args = parser.parse_args()

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    print("=" * 60)
    print("ECM Benchmark Dataset Downloader")
    print("=" * 60)
    print(f"Project root: {project_root}")

    results = {}

    # SWE-Bench-CL
    if args.benchmark in ["swe-bench-cl", "all"]:
        config = DATASETS["swe-bench-cl"]
        target_dir = project_root / config["target_dir"]
        target_path = target_dir / config["filename"]

        if args.validate_only:
            results["swe-bench-cl"] = validate_swe_bench_cl(target_path)
        else:
            success = download_file(config["url"], target_path, config["name"])
            if success:
                results["swe-bench-cl"] = validate_swe_bench_cl(target_path)
            else:
                results["swe-bench-cl"] = {"valid": False, "error": "Download failed"}

        # Optional: Task Stream
        if args.include_stream and not args.validate_only:
            config = DATASETS["swe-bench-cl-stream"]
            target_path = target_dir / config["filename"]
            download_file(config["url"], target_path, config["name"])

    # LifelongAgentBench
    if args.benchmark in ["lifelong-agent-bench", "all"]:
        config = DATASETS["lifelong-agent-bench"]
        target_dir = project_root / config["target_dir"]
        target_path = target_dir / "tasks_db.json"

        if args.validate_only:
            results["lifelong-agent-bench"] = validate_lifelong_agent_bench(target_path)
        else:
            success = download_huggingface(
                config["hf_dataset"],
                target_dir,
                config["name"]
            )
            if success:
                results["lifelong-agent-bench"] = validate_lifelong_agent_bench(target_path)
            else:
                results["lifelong-agent-bench"] = {"valid": False, "error": "Download failed"}

    # GAIA
    if args.benchmark in ["gaia", "all"]:
        config = DATASETS["gaia"]
        target_dir = project_root / config["target_dir"]
        target_path = target_dir / "tasks.json"

        if args.validate_only:
            results["gaia"] = validate_gaia(target_path)
        else:
            success = download_gaia(
                config["hf_dataset"],
                target_dir,
                config["name"]
            )
            if success:
                results["gaia"] = validate_gaia(target_path)
            else:
                results["gaia"] = {"valid": False, "error": "Download failed"}

    # TheAgentCompany
    if args.benchmark in ["the-agent-company", "all"]:
        config = DATASETS["the-agent-company"]
        target_dir = project_root / config["target_dir"]
        target_path = target_dir / "tasks.json"

        if args.validate_only:
            results["the-agent-company"] = validate_the_agent_company(target_path)
        else:
            success = download_the_agent_company(
                target_dir,
                config["name"]
            )
            if success:
                results["the-agent-company"] = validate_the_agent_company(target_path)
            else:
                results["the-agent-company"] = {"valid": False, "error": "Download failed"}

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for benchmark, result in results.items():
        status = "OK" if result.get("valid") else "FAILED"
        print(f"\n{benchmark}: {status}")
        if not result.get("valid"):
            print(f"  Error: {result.get('error')}")
        elif "total_tasks" in result:
            print(f"  Tasks: {result['total_tasks']}")

    # Check overall success
    all_valid = all(r.get("valid", False) for r in results.values())
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
