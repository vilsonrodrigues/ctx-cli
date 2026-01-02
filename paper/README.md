# Explicit Context Management for Long-Running Language Agents

**Paper Draft** - Academic submission for conference publication

## Abstract

This paper presents explicit context management, a lightweight approach to handling context window limits in long-running language model agents. Through scope isolation and episodic notes, we achieve 88% reduction in peak context and 34% faster execution on sequential tasks.

## Paper Structure

The paper is organized into modular sections (10 pages total):

```
paper/
├── 00-abstract.md           250 words - Problem, solution, results
├── 01-introduction.md       1.5 pages - Motivation and contributions
├── 02-related-work.md       1.5 pages - Comparison with 4 key papers
├── 03-method.md             2.5 pages - Architecture and implementation
├── 04-experiments.md        1.0 pages - Experimental setup
├── 05-results.md            1.5 pages - Quantitative results
├── 06-discussion.md         1.0 pages - Analysis and limitations
├── 07-conclusion.md         0.5 pages - Contributions and future work
├── references.md            Bibliography (24 papers)
└── figures/                 Visualizations and diagrams
```

## Key Results

### Sequential Tasks (SWE-Bench-CL)
- **88% peak context reduction**: 12,059 → 1,402 tokens
- **34% faster execution**: 121.5s → 80.5s
- **Bounded growth**: O(1) vs O(n) for linear approach

### Isolated Tasks (SWE-Bench Lite)
- **LINEAR more efficient**: 2.7x faster (18.6s vs 50.3s)
- Both approaches generated correct patches
- Reveals trade-off: SCOPE for sequential, LINEAR for isolated

### Critical Insight
**Explicit context management provides value when context accumulates across multiple related steps.**

## Compilation

### Markdown to LaTeX

For conference submission, convert to LaTeX:

```bash
# Install pandoc
sudo apt install pandoc texlive-full

# Compile individual sections
for file in paper/*.md; do
  pandoc "$file" -o "${file%.md}.tex"
done

# Or compile full paper
cat paper/0*.md paper/references.md | \
  pandoc -s --bibliography=references.bib \
         --citeproc \
         -o paper/full-paper.tex
```

### LaTeX Template

For submission to ACL/NeurIPS/ICML, use their official templates:

```bash
# ACL 2024 template
wget https://github.com/acl-org/acl-style-files/archive/master.zip
unzip master.zip
cp paper/*.tex acl-style-files-master/

# Compile
cd acl-style-files-master/
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

### Figures

Generate figures from code:

```bash
# Context growth visualization
python demos/demo_comparison.py --visualize

# Token savings chart
python demos/demo_token_savings.py --export-figure

# Scope isolation diagram
python demos/visualize_scopes.py
```

## References

The paper cites 24 key works organized by topic:

- **Context Compression**: AgentFold [1], Context-Folding [2], HiAgent [3]
- **Memory Systems**: Memory surveys [4-7], MemGPT [13], Mem0 [16]
- **Cognitive Architectures**: CoALA [12], Generative Agents [14], Reflexion [15]
- **Benchmarks**: SWE-Bench [21], SWE-Bench-CL [20], LOCOMO [22]
- **Infrastructure**: GPT-4 [23], tiktoken [24]

See `references.md` for complete bibliography with ArXiv links.

## Experimental Data

All benchmark results are reproducible:

```bash
# SWE-Bench-CL (sequential tasks)
OPENAI_API_KEY="..." uv run python benchmarks/run_swe_cl.py \
  --repo django \
  --tasks 15 \
  --approach both

# SWE-Bench Lite (isolated tasks)
OPENAI_API_KEY="..." uv run python benchmarks/run_swe_bench_lite.py \
  --tasks 10 \
  --approach both

# Results saved to benchmarks/results/
```

## Code Availability

The implementation is available as an open-source library:

```bash
pip install ctx-cli

# Or from source
git clone https://github.com/[organization]/ctx-cli.git
cd ctx-cli
uv pip install -e .
```

## Contributions

This paper makes five key contributions:

1. **Minimal four-command interface** for explicit context management
2. **Scope isolation with attention masking** for bounded context
3. **Asymmetric note placement semantics** preventing reasoning gaps
4. **Empirical validation** on SWE-Bench-CL and SWE-Bench Lite
5. **Open-source implementation** for practical deployment

## Target Venues

Suitable for submission to:

- **ACL 2024/2025** (System Demonstrations or Main Conference)
- **NeurIPS 2024/2025** (Datasets and Benchmarks or Main Conference)
- **ICML 2024/2025** (Applications Track)
- **EMNLP 2024/2025** (Main Conference)
- **ICLR 2025** (Main Conference)

Focus: Practical systems with empirical evaluation, minimal complexity, real-world applicability.

## Revision History

- **2024-12-30**: Initial draft complete with SWE-Bench-CL results
- **2024-12-30**: Added comparative analysis (when SCOPE helps vs LINEAR)
- **2024-12-30**: Updated abstract, intro, conclusion with benchmark data

## Authors

[To be filled based on contribution]

## License

Paper content: CC BY 4.0
Code implementation: MIT License

## Contact

For questions about the paper or experiments:
- Email: [to be added]
- GitHub: https://github.com/[organization]/ctx-cli
