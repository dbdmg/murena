# Conversational MURENA — editable EDBT LaTeX source

Demo-paper draft for EDBT 2027 (acmart `sigconf`). The paper keeps MURENA's six-dimension query template, agents, SQL construction and ranking as inherited components; the contribution is the pre-analysis conversational elicitation and confirmation stage, with an EVPI-inspired question order attributed to SAGE-Agent. The eight-use regulatory catalogue is supporting coverage.

## Evaluation status

- Section 5 describes the **v3 three-condition protocol** (`backend/experiments/data/scenarios_v3/`): 8 base intents, k=0..5 omitted dimensions, 48 scenarios; conditions `refined` (×3), `one_shot` (k≥1, ×3), `oracle` (×5 per intent), 304 runs; gpt-6-luna via Codex CLI (low reasoning effort); 89,200-property dataset. The oracle is a reference query, not relevance ground truth.
- **No v3 results are in the compiled text.** The results table (`tab:results`) and per-k figure (`fig:perk`) are inside a `%% RESULTS-PENDING (v3)` block wrapped in `\iffalse ... \fi`. To enable it: fill the `\RP` placeholders, create `data/per_k.csv` (columns `k,cond,j5,j5_lo,j5_hi,rbo,rbo_lo,rbo_hi`; `cond` in `one_shot`, `refined`, `oracle`, where oracle rows hold the noise ceiling), and remove `\iffalse`/`\fi`.
- The "Earlier robustness suite" paragraph reports the verified v1 run of 2026-11-16 (24 scenarios, conversational condition only), as documented in `docs/okf/research/edbt-conversational-benchmark.md`.
- Screenshot figures are commented out (`%% SCREENSHOT-PENDING`); expected files `figures/screen-dialogue.png` and `figures/screen-results.png`.

## Build

The architecture figure is `figures/architecture.tex` (TikZ). Build in a copy of this directory, not in place:

```bash
tectonic -X compile edbt-paper-template.tex
```

With Tectonic/XeTeX, copy the Libertinus OTF fonts into the build directory with lowercase file names (e.g. `libertinusmath-regular.otf`). A pdfLaTeX + BibTeX build (`pdflatex`, `bibtex`, `pdflatex` ×2) should also work. Current length: 4 pages including references, with demo screenshots and the preliminary v3 results (EDBT demo limit: 4 pages plus references; confirm in the 2027 call). The per-k figure reads `data/per_k.csv`, exported from `backend/experiments/results/missingness_v3/comparison_per_k.csv`.
