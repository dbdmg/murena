# Conversational MURENA — editable EDBT LaTeX source

Demo-paper draft for EDBT 2027 (acmart `sigconf`). The paper keeps MURENA's six-dimension query template, agents, SQL construction and ranking as inherited components; the contribution is the pre-analysis conversational elicitation and confirmation stage, with an EVPI-inspired question order attributed to SAGE-Agent. The eight-use regulatory catalogue is supporting coverage.

## Evaluation status

- Section 5 reports the cooperative comparison using Claude Haiku 5.5 (`missingness_v3_haiku_r2`, 304/304 completed; code `a5c1b09`) and two imperfect-user benchmark replications: Claude Haiku 5.5 (`imperfect_user_haiku_c7b9f7a`, 264/265 completed; code `c7b9f7a`) and Codex/gpt-6-luna (`imperfect_user_codex_vlast`, 265/265 completed; code `37e0732`). The imperfect-user results are shown side by side, not pooled. The cooperative table summarizes completion, Jaccard@5, RBO@10, and filter-atom $F_1$ with 95% confidence intervals and oracle self-agreement. `data/per_k.csv` supplies the cooperative Haiku figure.
- The v4 seed-13 results are retained as a disabled LaTeX source block and are not compared with either reported series: the v4 dataset hash differs, and its generated $D$ opt-out wording blocked 37 refined attempts. Their detailed metrics remain in the source block and in `backend/experiments/results/imperfect_user_v4_comparison_seed13/`; the previous v4 curve is preserved in `data/per_k_v4_seed13_archived.csv`. The expanded v4 catalogue (8,192 generated scenarios) is described as a generator; neither reported series uses it. Provenance and limitations are recorded in `docs/okf/research/edbt-conversational-benchmark.md`.
- The **Availability** paragraph cites the public repository `dbdmg/murena` and the reduced-format APE data published by the Piedmont Region as open data under CC BY 4.0 (portal `https://www.dati.piemonte.it/#/catalogo`, verified 2026-11-18); the demo-video link is still to be added (prepared by Marco De Luca).
- `video/murena_demo_nursery.gif` is a silent screen recording of the live nursery walkthrough (vague answer → follow-up, opt-out → not requested, review, map). It is source material for the demo video, not a reported result.
- Section 4 is audience-driven: attendees type their own requests in the live system (activities a–d: omit and observe, decline or hedge, review, inspect), use the offline scenario panel to choose a use case and omission level $k$, preview the initial request and omitted dimensions, then replay one completed refined run. If multiple runs match, the panel previews the first case ID in lexicographic order. The benchmark results page displays one selected run at a time. One-shot comparison is shown through recorded runs, not by toggling clarification live. An opening walkthrough uses the nursery case (`MS02_k2`). The screenshots of the recorded backend session are included as `figures/screen-dialogue.png`, `figures/screen-review.png`, and `figures/screen-results.jpg`; these property results are not produced by the offline frontend simulator.

The v4 generator derives every ternary balance of specified, vague, and
opt-out answers over the full omission catalogue (8,192 scenarios) and is
validated statically. Its seed-13 sample results remain in a disabled LaTeX
block. The active imperfect-user metrics are descriptive for the recorded
Codex run; neither series establishes independent property-relevance ground
truth or supports generalization beyond its benchmark setup.

## Build

The architecture figure is `figures/architecture.tex` (TikZ). Build in a copy of this directory, not in place:

```bash
tectonic -X compile edbt-paper-template.tex
```

With Tectonic/XeTeX, copy the Libertinus OTF fonts into the build directory with lowercase file names (e.g. `libertinusmath-regular.otf`). A pdfLaTeX + BibTeX build (`pdflatex`, `bibtex`, `pdflatex` ×2) should also work. The previously generated PDF was 4 pages; the sources have since changed and, at the user's request, have not been recompiled, so the current page count and layout are unverified (EDBT demo limit: 4 pages plus references; confirm in the 2027 call).

The per-level figure reads `data/per_k.csv`, exported from the benchmark comparison outputs; see the OKF research record for exact input paths and execution metadata.
