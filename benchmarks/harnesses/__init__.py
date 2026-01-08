"""
Official Harness Integrations for ECM Benchmarks.

Each harness provides integration with an official benchmark:
- swe_bench_cl: SWE-Bench Continual Learning
- lifelong_agent_bench: LifelongAgentBench (DB/OS/KG)
- appworld: AppWorld multi-app environment
- osworld: OSWorld desktop automation
- the_agent_company: TheAgentCompany workplace simulation
- browsecomp_plus: BrowseComp-Plus deep research
- gaia: GAIA general AI assistants
"""

# Harness implementations are loaded on-demand to avoid import errors
# when optional dependencies are not installed.

AVAILABLE_HARNESSES = {
    "swe-bench-cl": {
        "module": "benchmarks.harnesses.swe_bench_cl",
        "class": "SWEBenchCLHarness",
        "description": "SWE-Bench Continual Learning - 273 sequential coding tasks",
        "type": "continual_learning",
        "requires": ["docker"],
    },
    "lifelong-agent-bench": {
        "module": "benchmarks.harnesses.lifelong_agent_bench",
        "class": "LifelongAgentBenchHarness",
        "description": "LifelongAgentBench - Skill reuse across DB/OS/KG",
        "type": "continual_learning",
        "requires": ["docker"],
    },
    "appworld": {
        "module": "benchmarks.harnesses.appworld",
        "class": "AppWorldHarness",
        "description": "AppWorld - Multi-app interactive environment",
        "type": "long_horizon",
        "requires": ["appworld"],
    },
    "osworld": {
        "module": "benchmarks.harnesses.osworld",
        "class": "OSWorldHarness",
        "description": "OSWorld - Desktop automation with real VMs",
        "type": "long_horizon",
        "requires": ["docker", "vmware"],
    },
    "the-agent-company": {
        "module": "benchmarks.harnesses.the_agent_company",
        "class": "TheAgentCompanyHarness",
        "description": "TheAgentCompany - Realistic workplace tasks with persistent company environment",
        "type": "long_horizon",
        "requires": ["docker"],
    },
    "gaia": {
        "module": "benchmarks.harnesses.gaia",
        "class": "GAIAHarness",
        "description": "GAIA - General AI assistants benchmark with multi-step reasoning",
        "type": "long_horizon",
        "requires": ["huggingface"],
    },
    "browsecomp-plus": {
        "module": "benchmarks.harnesses.browsecomp_plus",
        "class": "BrowseCompPlusHarness",
        "description": "BrowseComp-Plus - Deep research with 830 complex queries and 100K documents",
        "type": "long_horizon",
        "requires": ["huggingface", "datasets"],
    },
}


def get_harness(name: str):
    """
    Load and return a harness by name.

    Args:
        name: Harness name (e.g., 'swe-bench-cl')

    Returns:
        Harness class (not instance)

    Raises:
        ValueError: If harness not found
        ImportError: If harness dependencies not installed
    """
    if name not in AVAILABLE_HARNESSES:
        available = ", ".join(AVAILABLE_HARNESSES.keys())
        raise ValueError(f"Unknown harness: {name}. Available: {available}")

    info = AVAILABLE_HARNESSES[name]

    import importlib
    module = importlib.import_module(info["module"])
    return getattr(module, info["class"])


def list_harnesses() -> list[dict]:
    """List all available harnesses with metadata."""
    return [
        {
            "name": name,
            "description": info["description"],
            "type": info["type"],
            "requires": info["requires"],
        }
        for name, info in AVAILABLE_HARNESSES.items()
    ]
