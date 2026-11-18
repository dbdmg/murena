# Model council: synthesis (chair: claude-opus-5-5, 2026-11-18)

Reviews compared: `claude-opus-5-5.md`, `gemini-4-hydrogen.md` and `grok-4.7.md`, all written on commit `3dca8d4`. Since then, `0cdd528` has changed the author order, the Fig. 1 caption and the demo start screen; none of these changes affects the findings below.

## Scores

| Model | Score | Confidence |
|---|---|---|
| claude-opus-5-5 | 3 (would be 4 after the fixes) | 4/5 |
| gemini-4-hydrogen | 3 (would be 4 after the fixes) | 4/5 |
| grok-4.7 | 2 (3–4 after the fixes) | medium |
| **Mean** | **2.67** | |

**Numbers.** All three reviewers recompute every number in the paper from `runs.jsonl`: Table 1, Fig. 3 and the imperfect-user counts. The one exception is "144 matching properties" in the caption of Fig. 2.

## Consolidated findings

The "Raised by" column abbreviates the reviewers as O (claude-opus-5-5), G (gemini-4-hydrogen) and K (grok-4.7).

| # | Severity | Finding | Raised by | Fix | When |
|---|---|---|---|---|---|
| 1 | blocker | The committed PDF is stale (`5e47a32`). It still contains "or Italian", the 8,192 scenarios in the abstract and the old title. | O, G, K | Rebuild the PDF, check that it fits in 4 pages and commit it together with the source. | before deadline |
| 2 | blocker | The mandatory MP4 is missing; only a GIF exists. | O, G, K | Narrated MP4 of at most 5 minutes, uploaded to CMT. Keep the sentence "A video … accompanies" only if the MP4 is actually uploaded. | before deadline |
| 3 | major | The offline mode and `/benchmark` read the v4 seed-13 series, not the reported Haiku series (`.env.demo:3`). | O, G, K | Point `VITE_BENCHMARK_RESULTS_DIR` at `missingness_v3_haiku_r2`, re-export and rehearse. This is a code change, not a paper change. | before deadline (needed for the video) |
| 4 | major | The scenario panel offers only "use case + k", not a per-dimension state filter. "Three-behaviour design" refers to v4. The results page shows one run at a time. | O, G, K | Rewrite the "Controlled scenarios" paragraph. | before deadline |
| 5 | major | Fig. 2 reports 144 results, but the logged `MS02_k2` case returns 16. The screenshots come from an older build or a different session. | O, G, K | Option 1: recapture the screenshots. Option 2: caption saying "live session on an earlier build", without the number 144. | before deadline (caption) |
| 6 | major | Opt-out was measured only on $C_b, C_e, C_p$, each with a single fixed phrase, yet demo activity (b) says "any dimension". | O, G | Restrict (b) to preferences and add "fixed phrase" plus the scope to the imperfect-user paragraph. | before deadline |
| 7 | major/minor | The vague-answer 0.93 should not be compared with 0.88; the ceilings differ between executions (0.87 vs 0.93). The conditions also ran in separate time windows. | O, G | One sentence after "(0.93)", plus ", in different time windows". | before deadline |
| 8 | minor | The contradiction check runs only on ambiguity questions, not on omission or location answers. | O, G, K | Rephrase the sentence (System, Answers). | before deadline |
| 9 | minor | EVPI with uniform weights gives $1-1/n$; open omissions have EVPI 0 and follow generation order. Contribution (ii) promises more than this. | O, G (K as a PC question) | One sentence in System plus a softer contribution (ii). | before deadline |
| 10 | minor | Latencies: 17–38 s holds only for $k\ge1$; at $k=0$ it is 11 s. | O, G, K | "11 s at $k=0$, 17–38 s for $k\ge1$". | before deadline |
| 11 | minor | In the abstract, "(0.87)" sits next to $F_1$ too; the oracle ceiling for $F_1$ is 0.99. The abstract also does not say that the simulated user supplies the exact fragment. | O (m5), K (F5) | Reword the abstract sentence. | before deadline |
| 12 | minor | Relaxation: "always the same two intents" is false for one-shot (UC07 only). | K | Reword. | before deadline |
| 13 | minor | Two preliminary executions and three defects, not one execution with two. | O | Reword. | before deadline |
| 14 | minor | Metrics are defined but not reported (tie-aware, invented atoms, sign-flip, detection P/R). | O | Report detection 360/360 and sign-flip $p=0.008$; cut tie-aware and invented atoms. This also frees space. | before deadline |
| 15 | minor | Fig. 3 is never referenced; "six-dimension template" lists five; "MURENA's result relaxation" is not in the original paper. | O | Small text fixes. | before deadline |
| 16 | minor | Other blocking conditions (a second unresolved answer) are not described. | O | Extend the turn-limit sentence. | before deadline |
| 17 | minor | Reproducibility: the dirty-tree commits and `estates.parquet` are not distributed. | O | Availability: "code equivalent to `a5c1b09`" and the table is rebuilt from open data. | camera-ready (or before, if space allows) |
| 18 | minor | Novelty against slot filling and clarifying questions in IR is not discussed. | O | 1–2 verified citations. | camera-ready (bibliography must be verified) |
| 19 | nit | `showcomments` is true and a `%% test` comment remains in the source; the README is stale; there are no emails; "interpret" in Fig. 1. | O, G, K | Source cleanup and README. | before deadline (cleanup) |

## Disagreements

- **Score: Grok gives 2, the others 3.** Grok penalises the stale PDF and the mismatched figure, judging the package rather than the source. The finding is shared by all three; the difference lies only in its weight. Once #1–#5 are fixed, all three expect 3–4.
- **Fig. 2: recapture or caption?** Grok asks for new screenshots of `bench_24b7eb94f445`; Gemini and Claude accept a caption fix. Decision: fix the caption now; recapture only if there is time while recording the video, from the same session.
- **New citations (#18).** Claude alone asks for them and has not verified the DOIs. Decision: postpone, because adding unverified entries goes against the project rules.

## Note on page space

The current build already fills page 4. Fixes #4–#16 add about 10–12 lines. Space to recover:
- the tie-aware and invented-atom definitions (#14);
- a shorter nursery example in Evaluation, which Grok proposes as the first cut;
- the Regulatory catalogue paragraph.
