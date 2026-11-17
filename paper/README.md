# Conversational MURENA — editable EDBT LaTeX source

Demo-paper draft for EDBT 2027 (acmart `sigconf`). The paper keeps MURENA's six-dimension query template, agents, SQL construction and ranking as inherited components; the contribution is the pre-analysis conversational elicitation and confirmation stage, with an EVPI-inspired question order attributed to SAGE-Agent. The eight-use regulatory catalogue is supporting coverage.

## Evaluation status

- Section 5 describes the **three-condition benchmark protocol**: 8 base intents, k=0..5 omitted dimensions, 48 scenarios; conditions `refined` (×3), `one_shot` (k≥1, ×3), `oracle` (×5 per intent), 304 runs; gpt-6-luna via Codex CLI (low reasoning effort); 89,200-property dataset. The oracle is a reference query, not relevance ground truth.
- The paper reports **preliminary results from 115 completed of 123 executed runs (304 planned)** (54 refined, 44 one-shot, 17 oracle; 8 refined runs failed with model-call timeouts in a resumed attempt), stopped because of model-service latency. Aggregates use the paired intent means of `comparison_per_k.csv`. Coverage is uneven; the table and per-level figure are compiled from the imported benchmark outputs. Provenance and limitations are recorded in `docs/okf/research/edbt-conversational-benchmark.md`.
- Section 4 presents one prepared nursery-conversion demonstration (`MS02_k2`) with a predefined request and answers, demonstrated by the presenter. It does not promise a separate open-ended audience session. The screenshots of the recorded backend session are included as `figures/screen-dialogue.png`, `figures/screen-review.png`, and `figures/screen-results.jpg`; these property results are not produced by the offline frontend simulator.

## Build

The architecture figure is `figures/architecture.tex` (TikZ). Build in a copy of this directory, not in place:

```bash
tectonic -X compile edbt-paper-template.tex
```

With Tectonic/XeTeX, copy the Libertinus OTF fonts into the build directory with lowercase file names (e.g. `libertinusmath-regular.otf`). A pdfLaTeX + BibTeX build (`pdflatex`, `bibtex`, `pdflatex` ×2) should also work. Current length: 4 pages including references, screenshots, and preliminary benchmark results (EDBT demo limit: 4 pages plus references; confirm in the 2027 call).

The per-level figure reads `data/per_k.csv`, exported from the benchmark comparison outputs; see the OKF research record for exact input paths and execution metadata.
