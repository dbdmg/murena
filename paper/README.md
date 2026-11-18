# Conversational MURENA — editable EDBT LaTeX source

Demo-paper draft for EDBT 2027 (acmart `sigconf`). The paper keeps MURENA's six-dimension query template, agents, SQL construction and ranking as inherited components; the contribution is the pre-analysis conversational elicitation and confirmation stage, with an EVPI-inspired question order attributed to SAGE-Agent. The eight-use regulatory catalogue is supporting coverage.

## Evaluation status

- Section 5 describes the **three-condition benchmark protocol**: 8 base intents, k=0..5 omitted dimensions; conditions `refined` (×3), `one_shot` (k≥1, ×3), `oracle` (×5 per intent), 304 runs; Claude Haiku 5.5 via the Claude Code CLI provider `claude_cli` (medium effort); 89,200-property dataset. The paper now presents scenario generation through the **v4 deterministic catalogue**: all 32 omission masks per intent (256) and all three behaviours per omitted dimension (specified, vague, opt-out), for 8,192 scenarios (`backend/experiments/data/scenarios_v4/derive_imperfect_user_v4.py`). The reported 304 runs are the completed **cooperative series** of that catalogue; no sampling parameters, seeds, or v4 run results are reported. The paper names the model (Claude Haiku 5.5 via the Claude Code CLI, medium effort, CLI default sampling: the CLI has no temperature option). The oracle is a reference query, not relevance ground truth.
- The paper reports **all 304 planned runs, completed on 2026-11-18** (144 refined, 120 one-shot, 40 oracle; no failures; code `a5c1b09`) from `backend/experiments/results/missingness_v3_haiku_r2/`. The 2026-11-17 series `missingness_v3_haiku` ran before the typology-column fix `0e29b52` and is superseded, never pooled. Aggregates use the `intent_mean_paired` rows of `comparison_per_k.csv` (8 intents); `data/per_k.csv` is exported from its `per_k` rows. The earlier partial gpt-6-luna execution (115 completed of 123 executed runs, Git `4a7c882`) is superseded in the paper, kept in OKF, and never pooled. Provenance and limitations are recorded in `docs/okf/research/edbt-conversational-benchmark.md`.
- The **Imperfect users** paragraph reports `backend/experiments/results/imperfect_user_haiku/` (265/265 runs, code `62630c0`; `imperfect_user_summary.json` from `analyze_imperfect_user.py`): opt-out and vague-then-exact variants of the 40 k≥1 scenarios, compared only with the series' own oracle runs.
- The **Availability** paragraph cites the public repository `dbdmg/murena` and the reduced-format APE data published by the Piedmont Region as open data under CC BY 4.0 (portal `https://www.dati.piemonte.it/#/catalogo`, verified 2026-11-18); the demo-video link is still to be added (prepared by Marco De Luca).
- `video/murena_demo_nursery.gif` is a silent screen recording of the live nursery walkthrough (vague answer → follow-up, opt-out → not requested, review, map). It is source material for the demo video, not a reported result.
- Section 4 is audience-driven: attendees type their own requests in the live system (activities a–d: omit and observe, decline or hedge, review, inspect), use the offline scenario panel to browse completed v4 runs by use case and per-dimension state (specified, omitted, ambiguous), and the benchmark results page; an opening walkthrough uses the nursery case (`MS02_k2`). One-shot comparison is shown through recorded runs, not by toggling clarification live. The screenshots of the recorded backend session are included as `figures/screen-dialogue.png`, `figures/screen-review.png`, and `figures/screen-results.jpg`; these property results are not produced by the offline frontend simulator.

The v4 generator derives every ternary balance of specified, vague, and
opt-out answers over the full omission catalogue (8,192 scenarios) and is
validated statically. Its profiles are the framework of the benchmark;
the reported evidence remains the completed cooperative series. Partial
v4 runs and their descriptive metrics are documented in OKF but not
reported in the paper.

## Build

The architecture figure is `figures/architecture.tex` (TikZ). Build in a copy of this directory, not in place:

```bash
tectonic -X compile edbt-paper-template.tex
```

With Tectonic/XeTeX, copy the Libertinus OTF fonts into the build directory with lowercase file names (e.g. `libertinusmath-regular.otf`). A pdfLaTeX + BibTeX build (`pdflatex`, `bibtex`, `pdflatex` ×2) should also work. Current length: 4 pages including references, screenshots, and preliminary benchmark results (EDBT demo limit: 4 pages plus references; confirm in the 2027 call).

The per-level figure reads `data/per_k.csv`, exported from the benchmark comparison outputs; see the OKF research record for exact input paths and execution metadata.
