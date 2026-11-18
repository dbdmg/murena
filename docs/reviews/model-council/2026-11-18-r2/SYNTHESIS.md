# Model council round 2: synthesis (chair: claude-opus-5-5, 2026-11-18)

Reviews compared: `gpt-6-codex.md`, `grok-4.7.md` and `gemini-4-argon.md`, all written on commit `3030a13` (merge of PR #6).

**Important:** after the reviews, merge `6f4d7e5` (22:40) replaced the paper source with a different draft (mixed-response benchmark only). The findings below are therefore mapped to both `3030a13` (reviewed) and the current `demo` source. The choice of which version to submit is left to Marco De Luca.

## Scores

| Model | Score | Confidence |
|---|---|---|
| gpt-6-codex | 3 | 4/5 |
| grok-4.7 | 3 | 4/5 |
| gemini-4-argon | 4 (5 after fixes) | 5/5 |
| **Mean** | **3.33** | |

**Numbers.** All three reviewers recompute every active number of `3030a13` from `runs.jsonl`: Table 1, Fig. 3, the imperfect-user paragraph and the latencies. No quantitative contradiction was found. Of the 19 round-1 findings, about 15 are fixed in `3030a13`.

## What changed after the reviewed commit

The paper text in merge `6f4d7e5` matches neither parent (338 lines differ from `9471de6`, 384 from `3030a13`). The OKF log records: "mantenuta la bozza locale sul benchmark mixed-response". In the current source:

1. The cooperative Haiku series is no longer reported: 304 runs, one-shot 0.16 → refined 0.88, p = 0.008, Table 1, Fig. 3.
2. The paper now reports only the 75-scenario mixed-response benchmark with two models:
   - `imperfect_user_haiku_c7b9f7a`: 264/265 completed, code `c7b9f7a`. This series was marked superseded in `659f97f`, because `c7b9f7a` predates the EVPI fix in `a5c1b09`.
   - `imperfect_user_codex_vlast`: 265/265 completed, code `37e0732`.

   The two series differ in model, code revision and dataset snapshot; the text does not state the code difference.
3. Several council fixes are reverted:
   - contradiction check described as general;
   - activity (b) no longer restricted to $C_b, C_e, C_p$;
   - latencies removed;
   - second-unresolved-answer blocking removed.
4. The PR #6 changes are reverted (two contributions, `\SIMONE{}` note back), and `showcomments` is `true`.
5. The committed PDF is from `6a3747d`, so it does not match the source. A scratch build of the current source gives 4 pages.

## Consolidated findings

The "Raised by" column abbreviates the reviewers as C (gpt-6-codex), K (grok-4.7) and G (gemini-4-argon).

| # | Severity | Finding | Raised by | Status on current `demo` | When |
|---|---|---|---|---|---|
| 1 | blocker | The mandatory MP4 is missing (only a GIF), yet the paper says a video accompanies the submission. | C, K, G | open | before deadline |
| 2 | major | Offline replay and `/benchmark` do not use the reported series: `.env.demo` points at v4 seed-13, and the export has 22 runs over 3 intents. | C, K, G | `.env.demo` now points at `imperfect_user_codex_vlast` (Vercel build, 75 scenarios). This is consistent only with the Codex half of the current paper, and with neither series of `3030a13`. | before deadline / video |
| 3 | major | Broken reference "Sec. efsec:demo" (`tex:284`). | C, K, G | sentence no longer present | — |
| 4 | major | "Fully offline" fallback overstated: satellite tiles (Esri) need the network. | C | open | before deadline |
| 5 | minor | Abstract: "handled every explicit decline … as intended" overstates the result, since declined-dimension atoms are absent in only 0.90 of runs. | C, K | The new abstract says "Filter $F_1$ 0.99–1.00", but the declined preference is omitted from the filters in only 0.88/0.90 of runs: rephrase. | before deadline |
| 6 | minor | "304 simulated interactions" includes 160 runs without dialogue (use "304 pipeline runs"). | C | moot in the current text | — |
| 7 | minor | The blocking policy is wider than the code: the counter applies only to unknown/rejected omission answers. The contradiction check excludes location disambiguation. | C, K, G | regressed (now general) | before deadline |
| 8 | minor | "An analysis takes 72–83 s" should say *median*. | C, K | latencies removed | — |
| 9 | minor | Oracle self-agreement of 0.70 is the Jaccard value only. | K | The table row "Reference ranking self-agreement" does not say which metric: specify it. | before deadline |
| 10 | minor | Declined $C_p$: the inherited proximity agent still infers a filter from the intended use (10 runs). | G (Q4) | open; state as a limitation | before deadline |
| 11 | minor | Novelty sentence versus AmbiSQL and Sphinteract could be sharper; no form baseline or EVPI ablation. | C, G | open | camera-ready |
| 12 | nit | Fig. 2 badge shows 144 (logged run: 16); UI text too small. | C, K | open | video / camera-ready |
| 13 | nit | `paper/README.md` stale (4 pages *plus* references, not recompiled); `README-EDITORIAL.md` contradicts Sec. 4. | C, K, G | open | before deadline |
| 14 | nit | Italian labels on `/benchmark`. | G | open | before video |
| 15 | nit | MURENA bib entry lacks volume and pages (Springer: vol. 16949, pp. 446–462, to verify); three arXiv-only entries. | C | open | camera-ready |
| 16 | nit | Reproducibility: dirty trees, `a5c1b09` equivalence not in the paper, `estates.parquet` not distributed. | C, K | open | camera-ready |

## Chair recommendation

**Restore the `3030a13` paper (option A), adding the mixed-response table from the current draft if space allows.** Option B, keeping the current draft and re-applying the council fixes, is the alternative.

Reasons:
- The cooperative one-shot/refined comparison on 304 runs is the strongest evidence, and the only part all three reviewers verified number by number.
- Option B rests on a Haiku series from superseded code `c7b9f7a`, with a code revision different from the Codex series.

Before the deadline, whichever version is chosen:
- upload the MP4;
- align offline replay with the reported series;
- qualify the offline map claim;
- set `showcomments` to false and remove the leftover notes;
- rebuild and commit the PDF.

Decision owner: Marco De Luca.
