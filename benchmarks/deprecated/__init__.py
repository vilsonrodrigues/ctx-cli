"""
Long-Horizon Task Benchmarks for ECM.

These benchmarks test agents on extended, multi-step tasks that require
maintaining state and context across many interactions:

- SWE-Bench-CL: Sequences of 50+ related code tasks (continual learning)
- AppWorld: Multi-step tasks across 9 apps with state dependencies
- TheAgentCompany: Realistic work simulation with complex workflows

These benchmarks are ideal for evaluating ECM because they test:
1. Knowledge retention across tasks
2. Forward transfer (learning from earlier tasks helps later ones)
3. State management over long horizons
4. Context efficiency under sustained load

Runners:
- run_swe_bench_cl.py: SWE-Bench Continual Learning evaluation
- run_appworld.py: AppWorld multi-app task evaluation
- run_agentcompany.py: TheAgentCompany work simulation
"""

__all__ = []
