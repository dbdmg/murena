# EDBT 2027 Demo Track Review — Conversational MURENA

- **Model ID:** Gemini 4 Hydrogen (Medium)
- **Date:** 2026-11-18
- **Commit reviewed:** `3dca8d4` (branch `demo`)
- **Files actually read:**
  - Paper: `paper/edbt-paper-template.tex`, `paper/sample-base.bib`, `paper/edbt-macros.tex`, `paper/data/per_k.csv`, `paper/figures/architecture.tex`, `paper/figures/screen-dialogue.png`, `paper/figures/screen-review.png`, `paper/figures/screen-results.jpg`, `paper/README.md`, `paper/edbt-paper-template.pdf` (stale build)
  - Project rules & OKF context: `AGENTS.md`, `docs/okf/index.md`, `docs/okf/project/overview.md`, `docs/okf/project/evidence-boundaries.md`, `docs/okf/frontend/ui-routes.md`
  - Research record: `docs/okf/research/edbt-conversational-benchmark.md`, `docs/okf/research/conversational-paper-audit.md`, `docs/okf/references/paper/paper.tex`
  - Experiment artifacts: `backend/experiments/results/missingness_v3_haiku_r2/{manifest.json, comparison.json, comparison_per_k.csv, comparison_operational.csv, runs.jsonl}`, `backend/experiments/results/imperfect_user_haiku/{manifest.json, imperfect_user_summary.json, runs.jsonl}`
  - Benchmark & analysis code: `backend/experiments/data/scenarios_v3/{README.md, derive_imperfect_user.py}`, `backend/experiments/data/scenarios_v4/README.md`, `backend/experiments/benchmark_cli.py`, `backend/experiments/compare_conditions.py`, `backend/experiments/analyze_imperfect_user.py`
  - System implementation: `backend/app/services/sage_clarification/{service.py, uncertainty.py, prompts.md}`, `backend/app/core/config.py`, `frontend/src/components/demo/DemoPanel.tsx`, `frontend/.env.demo`, `frontend/vite.config.ts`

---

## Verdict

- **Score:** **3 / 5** (Weak Accept / Borderline — would rise to **4 / 5** once the missing MP4 video, stale PDF verification, and demo-UI mismatches are resolved)
- **Confidence:** **4 / 5** (High — all reported benchmark numbers were recomputed from `runs.jsonl` and all system/UI claims were checked against source code)

**Summary:** Conversational MURENA presents a well-scoped, genuinely useful pre-analysis clarification layer over MURENA's inherited six-dimension real-estate screening pipeline, with clear attribution to MURENA and SAGE-Agent and fully reproducible benchmark numbers on `missingness_v3_haiku_r2` (304/304 runs) and `imperfect_user_haiku` (265/265 runs). However, the submission currently has two hard EDBT 2027 Demo Track blockers: `paper/edbt-paper-template.pdf` is stale relative to the latest `.tex` edits (leaving the strict 4-page limit unverified), and the mandatory MP4 demo video ($\le 5$ min) is missing (only a silent GIF exists). In addition, the paper's description of the offline scenario panel (per-dimension state filtering) and the benchmark results page (comparing one-shot, refined, and oracle on the reported series) does not match the current `DemoPanel.tsx` and `.env.demo` configuration.

---

## Findings Table

| ID | Severity | Area | Location | Problem | Evidence | Concrete fix | Fixable before the deadline |
|---|---|---|---|---|---|---|---|
| F1 | **blocker** | E | `paper/edbt-paper-template.pdf`, `paper/README.md:17-18` | The compiled PDF (`2026-11-18 16:50:57`) is stale relative to `paper/edbt-paper-template.tex` (`2026-11-18 18:25:45`). The stale PDF still contains `"Authors to be confirmed"`, `"or Italian"`, `"8,192 scenarios"` in the abstract, and an older Table 1, and it already fills page 4 to the bottom. The 4-page limit (references included) of the current `.tex` is **unverified**. | `Get-Item paper/edbt-paper-template.*` timestamps; visual inspection of `paper/edbt-paper-template.pdf` pages 1–4. | Recompile `paper/edbt-paper-template.tex` in a clean copy per `paper/README.md:22-28`, verify it fits within 4 pages (references included) with no overfull/layout regressions, and trim if needed. | yes |
| F2 | **blocker** | D | `paper/video/`, `paper/edbt-paper-template.tex:267,682-684`, `paper/README.md:9-10` | EDBT 2027 Demo Call requires a mandatory MP4 video ($\le 5$ min). Only a silent GIF (`paper/video/murena_demo_nursery.gif`, 7.87 MB) exists in the repo, and no video link is in the paper. | `ls paper/video/` shows only `murena_demo_nursery.gif`; `paper/README.md:9` states `"the demo-video link is still to be added"`. | Export/narrate an MP4 ($\le 5$ min, H.264/AAC) covering the nursery walkthrough, an opt-out, a vague follow-up, the review form, and the map/offline fallback, upload it for CMT submission, and add the link in `Availability` if desired. | yes |
| F3 | **major** | B / D | `paper/edbt-paper-template.tex:250-256`, `frontend/src/components/demo/DemoPanel.tsx:65-71,84-97` | Paper claims attendees *"narrow the available completed runs by the state of each dimension (specified, omitted, or ambiguous)"*. In reality, `DemoPanel.tsx` only exposes two dropdowns: **Use case** and **$k$** (number of omitted dimensions), and auto-selects `matches[0]` when multiple profiles share `(useCase, k)`. | `DemoPanel.tsx:85-96` renders `<select aria-label="Use case">` and `<select aria-label="k">`; line 71 `const selected = matches[0];`. | Replace lines 251–254 of `paper/edbt-paper-template.tex` with: `attendees pick one of the eight benchmark use cases and the omission count $k$, and the interface loads a completed run with its initial request, prepared answers, rewritten query, and top-10 on the map, without network or model access.` | yes |
| F4 | **major** | B / D | `paper/edbt-paper-template.tex:257-259`, `frontend/.env.demo:3`, `frontend/vite.config.ts:11` | Paper states the results page *"lists the recorded runs of a benchmark series, so the one-shot, refined, and oracle outputs of the same case can be compared side by side"*. However, `frontend/.env.demo:3` points `VITE_BENCHMARK_RESULTS_DIR` to `../backend/experiments/results/imperfect_user_v4_comparison_seed13` (and `vite.config.ts:11` defaults to `imperfect_user_v4_multiseed_seed13`), not `missingness_v3_haiku_r2`. | `frontend/.env.demo:3`, `frontend/vite.config.ts:11`, `docs/okf/frontend/ui-routes.md:56`. | Either point `VITE_BENCHMARK_RESULTS_DIR` in `.env.demo` / `vite.config.ts` to `../backend/experiments/results/missingness_v3_haiku_r2` before building the demo, or explicitly state in `Sec. 4` which series is preloaded in the offline results view. | yes |
| F5 | **major** | A / C | `paper/edbt-paper-template.tex:239-240,414-421`, `backend/experiments/data/scenarios_v3/derive_imperfect_user.py:32` | Paper invites attendees to decline dimensions and reports 105/105 opt-out runs without stating that `imperfect_user_haiku` tested opt-out **only on preference dimensions** ($C_b, C_e, C_p$), never on $D$ or $L$. | `derive_imperfect_user.py:32`: `PREFERENCE_DIMENSIONS = ("Cb", "Ce", "Cp")`; `imperfect_user_summary.json:35-43` shows only `optout:Cb` (51), `optout:Ce` (27), `optout:Cp` (27). | In `paper/edbt-paper-template.tex:416`, replace `the declined dimension` with `the declined preference dimension ($C_b$, $C_e$, or $C_p$)`, and in line 239 illustrate decline with a preference (e.g., `"no requirement on energy class"`). | yes |
| F6 | **minor** | B | `paper/edbt-paper-template.tex:210-212`, `backend/app/services/sage_clarification/service.py:992-1169` | Paper claims *"a separate check blocks answers that contradict earlier requirements"*, implying it runs on all answers. In code, `_classify_answer` (which checks `relation == "contradictory"`) only runs in the `else:` branch (`service.py:1114-1159`), not on `omission_confirmation` (`service.py:992-1077`) or `location_disambiguation` (`service.py:1078-1112`). | `service.py:992-1169`. | Replace `and a separate check blocks answers that contradict earlier requirements` (line 211–212) with `and a separate consistency check blocks disambiguation answers that contradict earlier requirements`. | yes |
| F7 | **minor** | B | `paper/edbt-paper-template.tex:197-200`, `backend/app/services/sage_clarification/service.py:635-640,714-738` | Paper states candidates with enumerable alternatives use EVPI ordering, which is true, but does not note that plain omissions without alternatives ($C_b, C_e, C_p$) evaluate to $\text{EVPI}=0$ and therefore fall back to parser/index order (`-index`). | `service.py:637-640` returns `{"<UNK>": EPSILON}`, giving `evpi = 0.0`; `service.py:735` breaks ties by `-index`. | Append to line 200: `(omissions without enumerable alternatives tie at zero EVPI and follow parser order)`. | yes |
| F8 | **minor** | A / D | `paper/edbt-paper-template.tex:281,297-298`, `backend/experiments/results/missingness_v3_haiku_r2/runs.jsonl` | Fig. 2 caption states the pipeline returns `144` matching properties, and line 297–298 says `"This is benchmark scenario k=2 of Sec. 5"`. In `missingness_v3_haiku_r2`, `MS02_k2` (`bench_24b7eb94f445`) returned `16` results (`edbt-conversational-benchmark.md:487`), whereas `screen-results.jpg` was captured from a separate live session (`144` results). | `paper/figures/screen-results.jpg` shows `Results 144`; `edbt-conversational-benchmark.md:487` records `16` results for `bench_24b7eb94f445`. | In line 297–298, clarify: `Fig.~\ref{fig:screens} shows a live capture of this request (benchmark scenario $k=2$ of Sec.~\ref{sec:eval}).` | yes |
| F9 | **minor** | C | `paper/edbt-paper-template.tex:425-426`, `backend/experiments/results/imperfect_user_haiku/imperfect_user_summary.json:149-155` | Vague-answer $J_5=0.93$ is compared with its own oracle ceiling (`0.93`), while cooperative Table 1 has $J_5=0.88$ and ceiling `0.87`. Without an explicit caution, a reader may compare `0.93` vs `0.88` across series and infer that vague answers improve ranking agreement. | `imperfect_user_summary.json:128,150`; `comparison.json:312,327`; `conversational-paper-audit.md:146-148`. | After `(0.93)` on line 426, add `; cross-series comparison with Table~\ref{tab:results} is avoided because oracle self-agreement differs across executions`. | yes |
| F10 | **minor** | A / D | `paper/edbt-paper-template.tex:246-247`, `backend/experiments/results/missingness_v3_haiku_r2/comparison_operational.csv` | Paper states `"a dialogue takes 17--38 s and an analysis 72--83 s (medians)"`. `17–38 s` holds for $k=1\dots5$ (`17.2–38.4 s`), whereas $k=0$ takes `11.1 s` (median). | `comparison_operational.csv:2-7` (`11.148`, `17.2135`, ..., `38.3665`). | Change `17--38\,s` (line 247) to `11--38\,s` (or `17--38\,s` for $k\ge 1$). | yes |
| F11 | **nit** | E | `paper/edbt-paper-template.tex:60-68` | Author block lists names and affiliations but no `\email{...}` addresses. | `paper/edbt-paper-template.tex:60-68`. | Add `\email{...}` entries if required by EDBT 2027 submission guidelines. | yes |
| F12 | **nit** | C | `paper/edbt-paper-template.tex:373-376`, `backend/experiments/results/imperfect_user_haiku/manifest.json:124-125` | `temperature_applied: false` (CLI default sampling is used even though `temperature: 0.0` is logged in `manifest.json`). Paper already notes `"CLI's default sampling"`, which is accurate, and single-model scope (`claude-haiku-5-5`) is clear. | `imperfect_user_haiku/manifest.json:124-125`; `edbt-conversational-benchmark.md:413`. | No edit strictly needed; optionally mention single-model evaluation in `Sec. 6` limitations. | yes |

---

## Reproduced Numbers

All numbers below were recomputed directly from `runs.jsonl` and per-run artifacts using `compare_conditions.py` and `analyze_imperfect_user.py` (read-only Python invocations, no files modified):

### 1. Cooperative Haiku series (`backend/experiments/results/missingness_v3_haiku_r2`)

**Command used:**
```bash
uv run --project backend python -c "
import argparse, sys, statistics
from pathlib import Path
from collections import Counter
sys.path.insert(0, 'backend/experiments')
import compare_conditions as cc

r2 = Path('backend/experiments/results/missingness_v3_haiku_r2')
rows, skipped = cc.load_rows(r2)
print('cond/status:', Counter((r['condition'], r['status']) for r in rows))
print('relax:', Counter((r['condition'], r.get('base_case_id')) for r in rows if r.get('relaxation_applied')))
args = argparse.Namespace(permutations=1000, bootstrap=10000, seed=13, rbo_p=0.8, reference_min_votes=None)
res_cc = cc.analyse(rows, args)
for m in ('jaccard5_served', 'rbo10_served'):
    il = res_cc['ranking'][m]['delta_refined_minus_one_shot']['intent_level']
    oc = res_cc['ranking'][m]['oracle_noise_ceiling']
    print(m, 'refined:', il['paired_by_condition']['refined'], 'one_shot:', il['paired_by_condition']['one_shot'], 'oracle:', oc)
f_il = res_cc['filters']['f1']['delta_refined_minus_one_shot']['intent_level']
f_oc = res_cc['filters']['oracle_self_agreement_f1']
print('filter_f1 refined:', f_il['paired_by_condition']['refined'], 'one_shot:', f_il['paired_by_condition']['one_shot'], 'oracle:', f_oc)
"
```

| Paper Claim / Table 1 Entry | Paper Value | Recomputed Value | Match |
|---|---|---|---|
| Completion (Refined / One-shot / Oracle) | `144/144`, `120/120`, `40/40` (100%) | `144/144`, `120/120`, `40/40` (100%) | Exact |
| Jaccard@5 Refined ($k \ge 1$) | `0.88 [0.81, 0.96]` | `0.8794 [0.8053, 0.9562]` | Exact |
| Jaccard@5 One-shot ($k \ge 1$) | `0.16 [0.07, 0.25]` | `0.1586 [0.0700, 0.2487]` | Exact |
| Jaccard@5 Oracle self-agreement | `0.87 [0.79, 0.95]` | `0.8702 [0.7869, 0.9500]` | Exact |
| RBO@10 Refined ($k \ge 1$) | `0.94 [0.90, 0.97]` | `0.9369 [0.8963, 0.9666]` | Exact |
| RBO@10 One-shot ($k \ge 1$) | `0.20 [0.10, 0.30]` | `0.1969 [0.0963, 0.2965]` | Exact |
| RBO@10 Oracle self-agreement | `0.94 [0.89, 0.98]` | `0.9396 [0.8919, 0.9759]` (from `comparison.json`) | Exact |
| Filter-atom $F_1$ Refined ($k \ge 1$) | `0.98 [0.96, 1.00]` | `0.9796 [0.9624, 0.9951]` | Exact |
| Filter-atom $F_1$ One-shot ($k \ge 1$) | `0.61 [0.57, 0.65]` | `0.6073 [0.5652, 0.6508]` | Exact |
| Filter-atom $F_1$ Oracle self-agreement | `0.99 [0.98, 1.00]` | `0.9896 [0.9815, 0.9969]` | Exact |
| Relaxation runs | `52` (`36` refined, `6` one-shot, `10` oracle; 2 intents) | `52` (`UC03` 18 ref + 5 ora; `UC07` 18 ref + 6 one + 5 ora) | Exact |
| Fig. 3 `paper/data/per_k.csv` | 11 rows ($k=0..5$ refined, $k=1..5$ one-shot) | Verified against `comparison_per_k.csv` ($|\Delta| < 10^{-12}$) | Exact |
| Latency medians (Demo `Sec. 4`) | `17–38 s` dialogue; `72–83 s` analysis | Dialogue `11.1 s` ($k=0$), `17.2–38.4 s` ($k=1..5$); Analysis `72.3–82.6 s` | Exact for $k\ge 1$ (see F10) |

### 2. Imperfect-user Haiku series (`backend/experiments/results/imperfect_user_haiku`)

**Command used:**
```bash
uv run --project backend python -c "
import sys
from pathlib import Path
sys.path.insert(0, 'backend/experiments')
import analyze_imperfect_user as aiu
res_iu = aiu.analyse(Path('backend/experiments/results/imperfect_user_haiku'), b=10000, seed=13, permutations=1000, p=0.8)
print(res_iu['status_counts'], res_iu['final_state_of_altered_dimension'])
print(res_iu['optout']['filter_f1_other_dims'], res_iu['vague']['filter_f1'], res_iu['vague']['jaccard5_served'], res_iu['oracle_vs_oracle_jaccard5'])
"
```

| Paper Claim | Paper Value | Recomputed Value | Match |
|---|---|---|---|
| Total runs completed | `225` refined + `40` oracle | `105` opt-out + `120` vague = `225` refined, `40` oracle | Exact |
| Opt-out recorded as `NOT_REQUESTED` & $k$ turns | `105/105` | `105/105` (`not_requested=1.0`, `asked_once=1.0`, `turns_eq_k=1.0`) | Exact |
| Declined-dimension filter on student residence | `10` runs (`UC08`) | `10` runs (`UC08_student_grant_missing_use`, `Cp:education`) | Exact |
| Opt-out filter $F_1$ on other dimensions | `0.98` | `0.9770 [0.9508, 1.0000]` | Exact |
| Vague follow-up & $k+1$ turns & `SPECIFIED` | `120/120` | `120/120` (`followup=1.0`, `turns_eq_k_plus_1=1.0`, `specified=1.0`) | Exact |
| Vague filter $F_1$ | `0.99` | `0.9873 [0.9708, 0.9989]` | Exact |
| Vague top-5 agreement ($J_5$) vs. own oracle | `0.93` | `0.9306 [0.8861, 0.9733]` | Exact |
| Series oracle-vs-oracle $J_5$ | `0.93` | `0.9333 [0.8833, 0.9833]` | Exact |

---

## Top 5 Changes to Maximize Acceptance Chance

1. **Recompile `paper/edbt-paper-template.tex` and verify the 4-page limit (F1):** The current PDF is stale and the previous build already reached the bottom of page 4. Compiling the latest `.tex` and confirming 4 pages (references included) with clean layout is mandatory before submission.
2. **Produce and submit the mandatory $\le 5$-minute MP4 video (F2):** Convert/narrate the nursery walkthrough (`murena_demo_nursery.gif` + audio/UI tour showing opt-out, vague follow-up, review, map, and offline fallback) into an H.264/AAC MP4.
3. **Align `Sec. 4` ("Controlled scenarios") with `DemoPanel.tsx` (F3):** Update the paper text to accurately describe the `(Use case, k)` selector (rather than per-dimension state filtering), so live/video reviewers see exact alignment between paper and UI.
4. **Align `VITE_BENCHMARK_RESULTS_DIR` in `.env.demo` / `vite.config.ts` with the reported series (F4):** Point the demo configuration to `missingness_v3_haiku_r2` so the `/benchmark` results page shows the exact cooperative one-shot / refined / oracle series reported in Table 1.
5. **Clarify opt-out scope ($C_b, C_e, C_p$ only) and contradiction-check scope (F5, F6):** Explicitly state that `imperfect_user_haiku` tested opt-out on preference dimensions only, and qualify the contradiction check as applying to disambiguation answers.

---

## Likely PC Member Questions & Suggested Answers

1. **Q: How does your EVPI-style ordering actually behave when most omissions ($C_b, C_e, C_p$) have no enumerable candidate alternatives?**
   - *Suggested answer:* When a question has no enumerable alternatives (`alternatives == []`), its EVPI score is `0.0`, so EVPI ordering actively differentiates questions with candidate options (such as up to two regulatory uses for $D$ or up to three candidate cities for $L$) and otherwise falls back to parser order minus the redundancy penalty (`redundancy_lambda = 0.5`). Importantly, EVPI is strictly an ordering heuristic—readiness still requires every `UNCONFIRMED_ABSENT` dimension to be answered or explicitly declined.
2. **Q: Why did you not evaluate opt-out on intended use ($D$) or location ($L$) in the reported imperfect-user series?**
   - *Suggested answer:* In the reported `imperfect_user_haiku` series, opt-out was restricted to the three preference dimensions ($C_b, C_e, C_p$) because $D$ and $L$ are the primary domain/geographic anchors. While the system's state machine supports `NOT_REQUESTED` for any dimension (dropping $L$ searches the full regional dataset), evaluating realistic opt-out phrasing on $D$ and $L$ without leaking the hidden use case is left for future work.
3. **Q: Your evaluation uses a single model (`claude-haiku-5-5`) with simulated users and no static-form baseline. What does the benchmark actually establish?**
   - *Suggested answer:* It establishes two things under controlled conditions: (1) omitting requirements silently degrades one-shot top-5 overlap from `0.50` ($k=1$) to `0.01` ($k=5$), and (2) when the user supplies or declines requirements, the conversational stage recovers filter atoms (`F1 = 0.98`) and top-5 agreement (`0.88`) up to the pipeline's own oracle-vs-oracle noise ceiling (`0.87`). We explicitly frame this as an upper bound on recovery rather than a user study or a comparison against a static web form.
4. **Q: In the opt-out runs, why did a filter on the declined dimension still appear in 10 student-residence runs?**
   - *Suggested answer:* In those 10 runs (`UC08_student_grant_missing_use`), the user declined `Cp` (nearby services), which SAGE correctly recorded as `NOT_REQUESTED` without adding any proximity constraint to the rewritten query $\hat q$. However, the inherited `ProximityAgent` independently infers `Cp:education` from the stated student-residence use case—demonstrating a boundary between the conversational layer and the unchanged downstream agents.
5. **Q: What happens at the conference booth if the Wi-Fi drops or the LLM provider times out?**
   - *Suggested answer:* The frontend can be launched in controlled-scenario mode (`VITE_DEMO_MODE=true`), which runs completely offline using pre-exported property data (`estates.json`, `benchmark_estates.json`, `pois_by_category.json`) and completed benchmark runs (`benchmark_runs.json`), allowing attendees to step through recorded dialogues, editable review prompts, SQL queries, and top-10 map results without network or LLM access.
