# Conversational MURENA — editable EDBT LaTeX source

Demo-paper draft for EDBT 2027 (acmart `sigconf`). The paper keeps MURENA's six-dimension query template, agents, SQL construction and ranking as inherited components; the contribution is the pre-analysis conversational elicitation and confirmation stage, with an EVPI-inspired question order attributed to SAGE-Agent. The eight-use regulatory catalogue is supporting coverage.

## Evaluation status

- Section 5 reports a **sampled three-condition benchmark** from the v4 deterministic catalogue: 8 base intents, 32 omission masks per intent and all three behaviours per omitted dimension (specified, vague, opt-out), for 8,192 scenarios (`backend/experiments/data/scenarios_v4/derive_imperfect_user_v4.py`). The reported run sample is 1% (82 scenarios), seed 13, model `gpt-6-luna` via `codex_exec` (low reasoning effort), with 246 one-shot, 246 refined (209 completed), and 24 oracle runs. Ranking and filter metrics use completed runs; operational completion rates include failures. The generated $D$ opt-out wording is defective: 33/51 such refined sessions and 4/195 other opt-out sessions were blocked. The v4 dataset hash differs from the earlier Haiku series, so the paper makes no cross-series performance comparison. The oracle is a reference query, not relevance ground truth, and opt-out scenarios can make oracle agreement an unsuitable target.
- The paper presents one compact table with the primary outcomes: completion, Jaccard@5, RBO@10, and filter-atom $F_1$ for refined and one-shot, plus oracle self-agreement as a noise ceiling. The confidence intervals and detection $F_1$ are stated in the results text. The previous full set of aggregate and per-$k$ diagnostics (dimension recall, invented atoms, SQL consistency, mapping accuracy, latency, and operational counts) remains in a disabled LaTeX block for provenance; source data remain in `backend/experiments/results/imperfect_user_v4_comparison_seed13/comparison.json` and its CSV exports. `data/per_k.csv` is retained for the per-$k$ figure. Previous cooperative Claude Haiku results and the separate Haiku imperfect-user findings are retained as disabled LaTeX source (`\iffalse ... \fi`) for provenance, but are not current reported findings. The previous curve data are preserved in `data/per_k_cooperative_haiku_archived.csv`. The earlier full v3 series is not pooled with the v4 seed-13 sample. Provenance and limitations are recorded in `docs/okf/research/edbt-conversational-benchmark.md`.
- The **Availability** paragraph cites the public repository `dbdmg/murena` and the reduced-format APE data published by the Piedmont Region as open data under CC BY 4.0 (portal `https://www.dati.piemonte.it/#/catalogo`, verified 2026-11-18); the demo-video link is still to be added (prepared by Marco De Luca).
- `video/murena_demo_nursery.gif` is a silent screen recording of the live nursery walkthrough (vague answer → follow-up, opt-out → not requested, review, map). It is source material for the demo video, not a reported result.
- Section 4 is audience-driven: attendees type their own requests in the live system (activities a–d: omit and observe, decline or hedge, review, inspect), use the offline scenario panel to browse completed v4 runs by use case and per-dimension state (specified, omitted, ambiguous), and the benchmark results page; an opening walkthrough uses the nursery case (`MS02_k2`). One-shot comparison is shown through recorded runs, not by toggling clarification live. The screenshots of the recorded backend session are included as `figures/screen-dialogue.png`, `figures/screen-review.png`, and `figures/screen-results.jpg`; these property results are not produced by the offline frontend simulator.

The v4 generator derives every ternary balance of specified, vague, and
opt-out answers over the full omission catalogue (8,192 scenarios) and is
validated statically. The paper reports detailed seed-13 sample metrics as
preliminary descriptive evidence; it does not claim independent relevance
ground truth or generalize beyond this sample. The user requested no PDF
build after the latest source edits; page count and layout are unverified.

## Build

The architecture figure is `figures/architecture.tex` (TikZ). Build in a copy of this directory, not in place:

```bash
tectonic -X compile edbt-paper-template.tex
```

With Tectonic/XeTeX, copy the Libertinus OTF fonts into the build directory with lowercase file names (e.g. `libertinusmath-regular.otf`). A pdfLaTeX + BibTeX build (`pdflatex`, `bibtex`, `pdflatex` ×2) should also work. The previously generated PDF was 4 pages; the sources have since changed and, at the user's request, have not been recompiled, so the current page count and layout are unverified (EDBT demo limit: 4 pages plus references; confirm in the 2027 call).

The per-level figure reads `data/per_k.csv`, exported from the benchmark comparison outputs; see the OKF research record for exact input paths and execution metadata.
