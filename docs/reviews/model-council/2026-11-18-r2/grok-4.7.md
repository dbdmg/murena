# EDBT 2027 demo review, round 2 — grok-4.7

- Model: grok-4.7
- Commit reviewed: `3030a130e9e5c6e21fb2ebd70906ff3dd3729357` (`demo`, already HEAD; not a detached checkout)
- Date: 2026-11-18
- Time spent: about 2 hours
- Read-only except this file. Metrics were recomputed into a temporary directory. The working tree had line-ending changes on two result JSON files; those copies were not used as evidence.

## Score

**Score: 3 / 5** (weak accept on the scale 1 reject … 5 strong accept).
**Confidence: 4 / 5.**

The cooperative and imperfect-user numbers recompute from the versioned runs. The manuscript now states the scope, the two series, and the attendee actions clearly. I would not accept the demo package while the mandatory video is absent and the offline booth replays a different series from the one in Section 5.

## Summary

Round 1's stale PDF is gone: the committed 4-page PDF matches the current abstract, including Claude Haiku 5.5, `gpt-6-luna`, and the closing attendee sentence. Table 1, Figure 3, and the imperfect-user paragraph match `compare_conditions.py` and `analyze_imperfect_user.py` at the paper's two-decimal rounding. Two submission blockers remain: there is still no MP4, only `paper/video/murena_demo_nursery.gif`, and both `.env.demo` and the checked-in offline export point away from `missingness_v3_haiku_r2`. A broken `\ref` is visible in the PDF as "Sec. efsec:demo". The contribution boundaries are respected: the pipeline is inherited, the conversational stage is the contribution, EVPI is attributed to SAGE-Agent, and the catalogue is supporting coverage.

## Round-1 follow-up

| # | Status | Where it shows in `3030a13` |
|---|---|---|
| 1 | Fixed | PDF text contains the new abstract (Haiku, `gpt-6-luna`, 0.16/0.88/0.87, attendee actions). Four pages including references. |
| 2 | Still open | `paper/video/` contains only `murena_demo_nursery.gif`. `paper/edbt-paper-template.tex:218` still says a video accompanies the submission. `paper/README.md:9` says the video link is still to be added. |
| 3 | Still open | `frontend/.env.demo:3` points at `imperfect_user_v4_comparison_seed13`. `frontend/vite.config.ts:11` defaults to `imperfect_user_v4_multiseed_seed13`. `frontend/public/data/benchmark_runs.json` has 22 imperfect-user runs (11 opt-out, 11 vague), ids such as `MS01_k2_optout`. |
| 4 | Fixed | `tex:205-211` describes use case + \(k\), one refined replay, and a results page that shows one selected run. That matches `DemoPanel.tsx:84-96` and `BenchmarkPage.tsx:125`. The series identity remains #3. `DemoPanel.tsx:70-71` still picks the first `case_id` when several profiles share a use case and \(k\). |
| 5 | Partly fixed | Caption `tex:229-232` no longer states 144 and says the shots are an earlier build. `figures/screen-results.jpg` still shows a Results badge of 144. Logged `MS02_k2` refined `bench_24b7eb94f445` has `results_count` 16. |
| 6 | Fixed | Activity (b) is limited to \(C_b, C_e, C_p\) (`tex:193-196`). The imperfect-user paragraph states the fixed phrase and those three dimensions (`tex:387-391`). The 75 scenarios opt out only on \(C_b\) (17), \(C_e\) (9), and \(C_p\) (9). |
| 7 | Fixed | `tex:275-276` says the three conditions ran in different time windows. `tex:397-399` says the ceilings differ (Haiku Jaccard ceiling 0.870, Codex 0.703) and that values are compared only within a series. |
| 8 | Partly fixed | `tex:168-169` limits the contradiction check to disambiguation answers. Omission answers do not take that path (`service.py:992`). Location disambiguation does not either (`service.py:1078`); the relation check is the remaining branch (`service.py:1142`). |
| 9 | Fixed | `tex:155-157` states \(1-1/n\) and zero EVPI for open omissions. Equal option weights are in `service.py:646-648`; an empty option list returns a single unknown and EVPI 0 (`service.py:636-640`, `uncertainty.py:39-41`). |
| 10 | Fixed | `tex:201-203`. Refined clarification medians: 11.1 s at \(k=0\) and 17.2, 23.3, 26.4, 30.8, 38.4 s for \(k=1..5\). |
| 11 | Fixed | `tex:80` says the simulated user supplies exactly the omitted requirement, places 0.87 on the Jaccard sentence, and gives \(F_1\) 0.61 to 0.98 in the next sentence. |
| 12 | Fixed | `tex:326-328`. Relaxation in 52 completed runs: refined 36 (spring 18, residential care 18), one-shot 6 (residential care only), oracle 10 (5 and 5). |
| 13 | Fixed | The active paragraph (`tex:328-329`) says earlier executions are documented and not pooled. The two-defect sentence survives only inside `\iffalse` (`tex:375-378`). |
| 14 | Fixed | Active text reports detection 360/360 and sign-flip \(p=0.008\) (`tex:333-339`) and drops tie-aware and invented-atom definitions. Those definitions remain in the disabled v4 block. |
| 15 | Fixed | Figure 3 is cited at `tex:337`. The template lists all six dimensions at `tex:110`. `tex:277` says "result relaxation" without "MURENA's". |
| 16 | Fixed | `tex:160-162`. A second unknown or rejected omission answer blocks (`service.py:1001-1010`); the turn limit blocks at `service.py:797`. Unclear answers take the follow-up path (`service.py:1024-1030`). |
| 17 | Still open | Availability (`tex:653-658`) does not name `a5c1b09` or say the table is rebuilt. `backend/data/` is gitignored (`.gitignore:191`), so `estates.parquet` is not in the repository. |
| 18 | Still open | No added slot-filling or IR clarification citations. Related work does discuss AmbiSQL, Sphinteract, FISQL, and COOL (`tex:104-106`). |
| 19 | Partly fixed | `showcomments` is false (`tex:25`). No `%% test` comment. `paper/README.md:28` still says the PDF was not recompiled; line 33 says it was. No `\email`. `figures/architecture.tex:36` still labels the arrow "interpret \(a_t\)". |

## Findings

| # | Severity | Finding | Evidence | Proposed fix | When |
|---|---|---|---|---|---|
| 1 | blocker | The mandatory MP4 is not in the repository. The paper tells the reader that a video accompanies the submission. | `paper/video/murena_demo_nursery.gif` is the only file under `paper/video/`. `tex:218`. `paper/README.md:9`. CMT upload status: unverified. | Keep the sentence only if the MP4 (≤5 min) is uploaded. Otherwise delete "A video of the demonstration accompanies this submission." Space: 0 lines, or −1 line. | before deadline |
| 2 | major | Offline mode and the benchmark page do not replay the cooperative Haiku series that Section 5 reports. | `frontend/.env.demo:3`; `frontend/vite.config.ts:11`; `frontend/scripts/export_benchmark_runs.py:13-23` reads that variable. Checked-in `frontend/public/data/benchmark_runs.json`: 22 runs, profiles opt-out 11 and vague 11. `tex:205-211` calls this "the benchmark series of Sec. 5". | Point `VITE_BENCHMARK_RESULTS_DIR` at `missingness_v3_haiku_r2`, re-export, and rehearse. Paper space: 0 if the code changes. | before deadline (needed for the video) |
| 3 | major | The nursery example's cross-reference is broken in the committed PDF, which prints "Sec. efsec:demo". | `tex:284-285` is a newline plus `ef{sec:demo}` (the `\r` of `\ref` was lost). PDF page 3 text: "one-shot input as in Sec. efsec:demo". | Replace with `omitted) supplied these inputs to the pipeline:`. The refined and oracle quotations that follow are exact (`bench_24b7eb94f445`; all 5 UC02 oracle runs). Space: 0. | before deadline |
| 4 | minor | The abstract says the Codex series "handled every explicit decline and every vague answer as intended." Dialogue outcomes are complete. A filter atom on the declined dimension is absent in an intent-mean of 0.90, not 1. | `tex:80`. `analyze_imperfect_user.py`: opt-out `no_declined_atoms` 0.8979 [0.7104, 1.0000], 105 runs; `NOT_REQUESTED`, one question, and \(k\) turns in 105/105; vague follow-up, \(k+1\) turns, and `SPECIFIED` in 120/120. | Replace the clause with "recorded every explicit decline and followed up every vague answer." Space: 0. | before deadline |
| 5 | minor | "An analysis takes 72–83 s" matches the band of per-slice medians (72.3–82.6 s). Individual runs are wider: one-shot analysis 56.3–196.6 s. | `tex:201-203`. `compare_conditions.py` operational medians: oracle 72.3 s; one-shot \(k=4\) 82.6 s. Direct min/max on completed Haiku rows. | Replace "an analysis takes" with "the median analysis time is". Space: 0. | before deadline |
| 6 | minor | "Oracle self-agreement was 0.70" follows both Jaccard and RBO. The recomputed figure is the Jaccard ceiling only. The imperfect-user script does not emit an oracle RBO ceiling. | `tex:397-398`. `oracle_vs_oracle_jaccard5` 0.7028 [0.5128, 0.8929]. | "Oracle top-5 self-agreement was 0.70 [0.51, 0.89]". Space: 0. | before deadline |
| 7 | nit | Figure 2's map badge still reads 144 results, while the logged nursery run the walkthrough points at returns 16. The caption already assigns the shots to an earlier build. | `figures/screen-results.jpg`; `tex:229-232` and `tex:241-249`. `MS02_k2` refined `results_count` 16, three repeats. | Recapture from `bench_24b7eb94f445` while recording the video, or crop the badge. Space: 0. | before deadline if the video is recorded; otherwise camera-ready |
| 8 | nit | "(seed 13)" sits next to "a different snapshot of the property table". In the Codex manifest `sample_seed` is 13 and `sample_fraction` is 1.0. The same words name the archived v4 1% sample. The dataset hashes differ: Haiku `bc6732c8…`, Codex `d3956041…`. | `tex:382-385`. `imperfect_user_codex_vlast/manifest.json` fields `dataset_sha256`, `sample_seed`, `sample_fraction`. | Delete "seed 13; ". Space: 0. | before deadline |
| 9 | nit | Location disambiguation never reaches the contradiction check. The sentence says "disambiguation answers". | `tex:168-169`. `service.py:1078` versus `service.py:1142`. | "ambiguity answers other than location". Space: 0. | camera-ready |
| 10 | nit | README still contains the pre-rebuild sentence. Author emails are absent. The architecture arrow still says "interpret". | `paper/README.md:28` and `:33`. `tex:61-69` has no `\email`. `figures/architecture.tex:36`. | Delete the stale README sentence. Add institutional emails at camera-ready without changing the scientific text. The "interpret" label matches answer classification; I would leave it. | README before deadline; emails camera-ready |

## Number-check table

Rounding is the paper's two decimals. Exact values are the recomputed ones. Haiku command: `compare_conditions.py --results backend/experiments/results/missingness_v3_haiku_r2 --bootstrap 10000 --permutations 1000 --seed 13 --rbo-p 0.8` (output outside the repo). Codex command: `analyze_imperfect_user.analyse` on `imperfect_user_codex_vlast` with the same bootstrap, permutations, seed, and \(p\), also written outside the repo. Counts are direct reads of `runs.jsonl`. Both-empty ranking pairs excluded: 0.

| Claim | Location | Paper | Recomputed | Match | Method |
|---|---|---|---|---|---|
| 304 Haiku runs, eight intents | abstract `tex:80`; intro `tex:96`; `tex:274`, `tex:322` | 304 | 304 completed: refined 144, one-shot 120, oracle 40; 0 errors; model `claude-haiku-5-5`; 8 `base_case_id`s | yes | `runs.jsonl` |
| Simulated user supplies the omitted fragment | abstract `tex:80`; `tex:259-260` | stated | refined: `expected_initial_missing` equals `initial_missing` on 144/144; sum of omissions 360 | yes | row fields |
| Jaccard 0.16 → 0.88, ceiling 0.87 | abstract `tex:80`; intro `tex:96`; Table 1 | 0.16 [0.07, 0.25]; 0.88 [0.81, 0.96]; 0.87 [0.79, 0.95] | 0.1586 [0.0700, 0.2487]; 0.8794 [0.8053, 0.9562]; oracle 0.870 [0.787, 0.950] | yes | `jaccard5_served`, \(k\ge 1\) intent mean |
| Filter \(F_1\) 0.61 → 0.98; oracle 0.99 | abstract `tex:80`; Table 1 | 0.61 [0.57, 0.65]; 0.98 [0.96, 1.00]; 0.99 [0.98, 1.00] | 0.6073 [0.5652, 0.6508]; 0.9796 [0.9624, 0.9951]; 0.990 [0.983, 0.995] | yes | `filter_f1` |
| RBO 0.94 / 0.20 / 0.94 | Table 1 | 0.94 [0.90, 0.97]; 0.20 [0.10, 0.30]; 0.94 [0.89, 0.98] | 0.9369 [0.8963, 0.9666]; 0.1969 [0.0963, 0.2965]; 0.943 [0.889, 0.977] | yes | `rbo10_served`, \(p=0.8\) |
| Completion 144/144, 120/120, 40/40 | Table 1 | those fractions | same, all `status=completed` | yes | `runs.jsonl` |
| Figure 3 and `data/per_k.csv` | `tex:609-632`; `paper/data/per_k.csv` | plotted \(J_5\) and the dashed line at 0.870 | every \(J_5\) and RBO float in `per_k.csv` equals `jaccard5_served` / `rbo10_served` for that \(k\); dashed line equals the oracle mean 0.870 | yes | float comparison against the recomputed table |
| Sign-flip \(p=0.008\), all eight intents positive, minimum attainable | `tex:337-339` | 0.008 | exact 0.0078125 (2/256) for \(J_5\), RBO, and filter \(F_1\) | yes at two decimals | script print |
| Detection 360/360, no false positives; turns \(=k\); no question at \(k=0\) | `tex:331-334` | stated | 360 omissions, 0 set mismatches; turns \(=k\) on 144/144; \(k=0\) is 24 runs with 0 turns | yes | row fields |
| Relaxation 52 (36 / 6 / 10), spring and residential care; one-shot residential care only | `tex:326-328` | stated | 52; refined UC03 18 and UC07 18; one-shot UC07 6; oracle UC03 5 and UC07 5 | yes | `relaxation_applied` |
| Median clarification 11 s at \(k=0\), 17–38 s for \(k\ge 1\) | `tex:201-203` | stated | 11.148 s; 17.213–38.367 s | yes | medians of `clarification_seconds` |
| Analysis 72–83 s | `tex:202-203` | stated | per-slice medians 72.3–82.6 s | yes for medians | operational table; see finding 5 for the run range |
| Conditions in different time windows; one pause; concurrency 10; no failed run | `tex:275-276`, `tex:322-325` | stated | refined starts 06:05–07:48 UTC, one-shot 07:48–08:08, oracle 08:08–08:13; one `resume_pending`; `agent_errors` 0; fallback 0; empty results 0 | yes | `started_at`, manifest |
| 48 variants, 8 controls, 40 one-shot scenarios, 5 oracle reps | `tex:256-274` | stated | manifest `enabled_variant_ids` 48; refined \(k=0\) is 8 variants × 3; one-shot 40 × 3; oracle 8 × 5 | yes | manifest and rows |
| 8,192 generator scenarios, not evaluated | `tex:263-266` | 8,192 | generator asserts `len(derived) == 8192` | source assertion; validator not re-run | `derive_imperfect_user_v4.py:294` |
| Nursery refined and oracle quotations | `tex:286-287` | the two quoted strings | exact match on refined repeat 1 and on all 5 UC02 oracle runs | yes | `submitted_query` |
| 89,200-property dataset | `tex:277` | 89,200 | parquet footer `num_rows` 89200; SHA-256 equals the Haiku manifest `bc6732c8…` | yes for the Haiku file | footer plus hash |
| Codex 265 planned, 225 refined, 40 oracle; 201 failed attempts re-run | `tex:385-387` | stated | 466 rows: 225 refined completed, 40 oracle completed, 201 `error`. Every error is "Codex CLI LLM call failed" and its `(condition, unit, repeat)` has a completed run. Completed attempts: 64 on attempt 1 and 201 on attempt 2 | yes | `runs.jsonl` |
| Opt-out 105: `NOT_REQUESTED`, one question, \(k\) turns; no-atom rate 0.90 [0.71, 1.00]; other-dimension \(F_1\) 0.99 [0.98, 1.00] | `tex:389-393` | stated | 105/105; 0.8979 [0.7104, 1.0000]; 0.9923 [0.9816, 1.0000]. Dimensions: \(C_b\) 51, \(C_e\) 27, \(C_p\) 27 | yes | imperfect-user script |
| Vague 120: follow-up, \(k+1\), `SPECIFIED`; \(F_1\) 1.00; Jaccard 0.74 [0.59, 0.88]; RBO 0.82 [0.72, 0.91] | `tex:394-397` | stated | 120/120; \(F_1\) 0.9989 [0.9972, 1.0000]; Jaccard 0.7352 [0.5869, 0.8808]; RBO 0.8179 [0.7223, 0.9108] | yes at two decimals | imperfect-user script |
| Codex oracle ceiling 0.70 [0.51, 0.89], below Haiku 0.87 | `tex:397-399` | stated | Jaccard 0.7028 [0.5128, 0.8929] versus Haiku 0.870 | yes for Jaccard | see finding 6 |
| Code `37e0732`, dirty tree; low effort; `codex_exec`; `gpt-6-luna` | `tex:382-401` | stated | manifest `git.commit` `37e0732…`, `dirty: true`, provider and model and `reasoning_effort: low` | yes | manifest |
| Haiku code comment `a5c1b09` | `tex:2-4` (comment, not body) | `a5c1b09` | manifest records `659f97f` then `4071a3a`, both dirty. `git diff --stat a5c1b09 <those> -- backend/app backend/experiments/*.py` is empty | consistent | git diff |
| Fixed phrases | `tex:388-389` | "I have no requirement on …"; one non-committal reply | 3 opt-out strings, all with that prefix; all 40 vague scenarios use "It depends; something suitable for the project, I guess." | yes | `imperfect_user.yaml`, 75 scenarios |
| Six turns in the reported runs; default 20 | `tex:161-162` | stated | both manifests `sage.max_turns` 6; `config.py:140` `SAGE_MAX_TURNS = 20` | yes | manifest and config |
| Temperature "CLI's default sampling" / Codex low effort | `tex:320-322`, `tex:382` | stated | `claude_cli.py` accepts `temperature` and does not pass it; command uses `--tools ""` and `--effort` (`claude_cli.py:180-189`). Codex manifest `temperature_applied: false` | yes | source and manifest |

Series were not pooled. Haiku scenario hash in the manifest is `be783d82…`. Codex scenario hash is `696a6a6d…`. The current `estates.parquet` matches the Haiku hash and does not match the Codex hash, so the Codex snapshot was not re-counted from the file on disk.

## Demo-track assessment

Attendee actions (a)–(d) are concrete: omit a requirement, decline a preference with "no requirement", give a vague answer, edit the rewritten request, then read filters, the map, and the ranking (`tex:188-200`). Setup and fallback are stated: laptop, network for live requests, offline scenario panel and results page when the network is down (`tex:213-217`). That is the right shape for a booth.

A demo chair's likely objections, in order:

1. The track requires an MP4 of at most 5 minutes. The repository has a silent GIF and the README still says the video link is pending. The sentence that a video accompanies the submission is ahead of the artifact.
2. The offline path the chair would rehearse does not play Section 5. The checked-in export is 22 imperfect-user dialogues, and the demo environment variable points at a v4 seed-13 directory. Attendees who pick "nursery, \(k=2\)" can land on an opt-out or vague profile because `DemoPanel.tsx:70-71` keeps the first `case_id`.
3. Live latency is believable only with the offline fallback in hand. Median clarification of 11–38 s plus a median analysis near 75 s is a long booth turn. One logged one-shot analysis ran 197 s. The paper should call the analysis figure a median.
4. Figure 2 is legible as a walkthrough, and the caption now says the shots are an earlier build. The visible "144" badge still disagrees with the 16-result logged nursery run. Figure 1 is dense but readable in the PDF text. Figure 3 is cited and its points match `per_k.csv`.
5. Novelty against AmbiSQL and Sphinteract is drawn in one sentence: those systems clarify SQL ambiguity, while this demo elicits MURENA's predefined search dimensions and shows the effect on a portfolio ranking (`tex:104-106`). That is enough for a demo if the booth actually shows the loop. It is not a new dialogue algorithm, and the paper does not claim one. The missing comparison is slot filling and clarifying questions in IR (round-1 #18), which can wait.

The `review` class option is on, so the PDF has line numbers. That is appropriate for review and should come off for camera-ready. I did not recompile, so overfull boxes are unverified. The extracted PDF text is four pages, references included, authors visible, and `showcomments` produces no notes.

## Questions for the authors

1. Will the MP4 be uploaded to CMT before the deadline, and will the video sentence stay only if it is?
2. Which directory will the booth load for the scenario panel and the results page, and can you replay `MS02_k2` from `missingness_v3_haiku_r2` rather than an opt-out variant?
3. Will the recorded video use the logged nursery run (`results_count` 16) or the earlier session whose badge reads 144?
4. What should a chair expect to wait during a live question plus analysis, given a logged analysis of 197 s?
5. Can the Codex property snapshot (`d3956041…`) be rebuilt from the open APE data? The parquet currently on disk matches the Haiku hash only.
