# Conversational MURENA — editable EDBT LaTeX source

Demo-paper draft for EDBT 2027 (acmart `sigconf`). The paper keeps MURENA's six-dimension query template, agents, SQL construction and ranking as inherited components; the contribution is the pre-analysis conversational elicitation and confirmation stage, with an EVPI-inspired question order attributed to SAGE-Agent. The eight-use regulatory catalogue is supporting coverage.

## Evaluation status

- Section 5 describes the **three-condition benchmark protocol**: 8 base intents, k=0..5 omitted dimensions, 48 scenarios; conditions `refined` (×3), `one_shot` (k≥1, ×3), `oracle` (×5 per intent), 304 runs; Claude Haiku 5.5 via the Claude Code CLI provider `claude_cli` (medium effort), nested 48-variant runner file `backend/experiments/data/scenarios_v3/nested48_from_4a7c882.yaml`; 89,200-property dataset. The paper names the model (Claude Haiku 5.5 via the Claude Code CLI, medium effort, CLI default sampling: the CLI has no temperature option). The oracle is a reference query, not relevance ground truth.
- The paper reports **all 304 planned runs, completed on 2026-11-18** (144 refined, 120 one-shot, 40 oracle; no failures; code `a5c1b09`) from `backend/experiments/results/missingness_v3_haiku_r2/`. The 2026-11-17 series `missingness_v3_haiku` ran before the typology-column fix `0e29b52` and is superseded, never pooled. Aggregates use the `intent_mean_paired` rows of `comparison_per_k.csv` (8 intents); `data/per_k.csv` is exported from its `per_k` rows. The earlier partial gpt-6-luna execution (115 completed of 123 executed runs, Git `4a7c882`) is superseded in the paper, kept in OKF, and never pooled. Provenance and limitations are recorded in `docs/okf/research/edbt-conversational-benchmark.md`.
- Section 4 is audience-driven: attendees type their own requests in the live system (activities a–d: omit and observe, decline or hedge, review, inspect), use the offline scenario panel (256 variants, recorded top-10 where available), and the benchmark results page; an opening walkthrough uses the nursery case (`MS02_k2`). One-shot comparison is shown through recorded runs, not by toggling clarification live. The screenshots of the recorded backend session are included as `figures/screen-dialogue.png`, `figures/screen-review.png`, and `figures/screen-results.jpg`; these property results are not produced by the offline frontend simulator.

The current generator also prepares all 32 omission subsets per intent (256
variants), grouped as S01–S08 with one `enabled` flag per base scenario.
All eight bases are initially enabled; selection applies to all 32 variants
and the oracle of each base. The expanded catalog has not been evaluated; it does not replace
the protocol or results reported above.

## Build

The architecture figure is `figures/architecture.tex` (TikZ). Build in a copy of this directory, not in place:

```bash
tectonic -X compile edbt-paper-template.tex
```

With Tectonic/XeTeX, copy the Libertinus OTF fonts into the build directory with lowercase file names (e.g. `libertinusmath-regular.otf`). A pdfLaTeX + BibTeX build (`pdflatex`, `bibtex`, `pdflatex` ×2) should also work. Current length: 4 pages including references, screenshots, and preliminary benchmark results (EDBT demo limit: 4 pages plus references; confirm in the 2027 call).

The per-level figure reads `data/per_k.csv`, exported from the benchmark comparison outputs; see the OKF research record for exact input paths and execution metadata.
