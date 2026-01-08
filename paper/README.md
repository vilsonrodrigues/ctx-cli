# SPACE: Manuscript Preparation

**Title**: SPACE: Self-Partitioned Agent Context Environment for Long-Horizon Agents
**Target Venue**: ACL / NeurIPS / ICLR
**Status**: Draft (Preliminary Results Phase)

## Abstract (250 words)
See `00-abstract.md` for the current abstract focusing on the "Context Growth Problem" and the $O(1)$ scaling proposition.

## Manuscript Structure

The paper follows a standard 8-page conference format (excluding references):

| Section | File | Description |
| :--- | :--- | :--- |
| **0. Abstract** | `00-abstract.md` | Problem, Method (SPACE), Preliminary Results ($O(1)$ scaling). |
| **1. Introduction** | `01-introduction.md` | The Context Growth Problem, Memory Imperative, Reasoning Model Paradox. |
| **2. Related Work** | `02-related-work.md` | Comparison with CoALA, MemGPT, RLM, Context-Folding, and AgentFold. |
| **3. Method** | `03-method.md` | Formal definition of Scopes ($\mathcal{S}$), Notes ($\mathcal{N}$), and Insights ($\mathcal{I}$). Token economics analysis. |
| **4. Experiments** | `04-experiments.md` | Protocols for SWE-Bench-CL, Knowledge Transfer, and Alternative Exploration. |
| **5. Results** | `05-results.md` | **Preliminary data** from pilot runs demonstrating efficiency gains and context bounding. |
| **6. Discussion** | `06-discussion.md` | Mechanisms of efficiency (Anti-Rumination), limitations, and theoretical implications. |
| **7. Conclusion** | `07-conclusion.md` | Summary of contributions and future research directions. |

## Appendices (Supplementary Material)

| Appendix | File | Description |
| :--- | :--- | :--- |
| **A. Formalization** | `appendix-a-formalization.md` | Mathematical definitions of context growth and operations. |
| **B. Metrics** | `appendix-b-metrics.md` | Definitions of Forward Transfer (FWT), Note Utility, and Context Reduction Ratio. |
| **C. Algorithm** | `appendix-c-algorithm.md` | Pseudocode for the core `ctx_cli` loop and state machine. |
| **D. Theory** | `appendix-d-theory.md` | Connection to Tulving's memory models and Test-Time Compute (TTC). |

## Compilation

To compile the full manuscript into LaTeX/PDF (requires `pandoc` and `texlive`):

```bash
# Compile individual sections
for file in paper/*.md; do
  pandoc "$file" -o "${file%.md}.tex"
done

# Compile full document with citations
cat paper/0*.md paper/references.md | \
  pandoc -s --bibliography=references.bib --citeproc -o paper/full-paper.pdf
```

## Reproducibility

Benchmark scripts are located in `benchmarks/`. All results presented in Section 5 are reproducible using:

```bash
# Run SWE-Bench-CL Pilot
uv run benchmarks/run_swe_cl.py --approach space --tasks 15
```

## Experimental Status

**Current Phase**: Pilot Validation.
Results presented in `05-results.md` are derived from initial pilot runs to validate the architectural thesis. Full-scale evaluation on the complete SWE-Bench Verified dataset is currently in progress.
