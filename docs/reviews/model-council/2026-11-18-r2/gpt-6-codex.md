# EDBT 2027 Demonstrations — independent round-2 review

Model: **GPT-6 / Codex** (the interface does not expose a more specific checkpoint identifier).  
Commit reviewed: **`3030a130e9e5c6e21fb2ebd70906ff3dd3729357`**, already checked out when the review began; no branch switch was necessary.  
Date: **2026-11-18**, Europe/Rome. Time spent: approximately **20 minutes**.  
Scope: original MURENA versus its conversational extension; static implementation review, local artifact recomputation, and inspection of all four rendered PDF pages. No new LLM experiments or live attendee session were executed.

## 1. Score and confidence

**Score: 3/5 — borderline accept. Confidence: 4/5.**

The scientific content and numerical traceability merit consideration as a demo; I would lean accept after the deadline fixes below. The package is **not submission-ready** until the mandatory MP4 is supplied. Its absence is a submission-completeness issue independently of this scientific score; a video uploaded outside the repository remains unverified here.

## 2. Summary

The paper presents a useful pre-analysis elicitation and confirmation stage for an existing real-estate screening system, and correctly attributes the inherited pipeline and SAGE-inspired ordering. Every active numerical result I recomputed agrees with the artifacts at the paper's displayed precision, without combining the two reported series. The new abstract and contribution bullets improve the framing, although “304 simulated interactions” mislabels pipeline runs and the abstract's universal imperfect-user success wording is too broad. The committed PDF now reflects the revised source and fits four pages including references. The remaining substantive demo weaknesses are a missing verifiable MP4, disagreement among the paper/configuration/exported replay data, and an overstated offline fallback.

## 3. Round-1 follow-up

Numbering follows `docs/reviews/model-council/2026-11-18/SYNTHESIS.md:26` onward. “Fixed” concerns the active manuscript, not every historical statement in disabled source.

| R1 # | Status | Evidence and round-2 judgment |
|---|---|---|
| 1 — stale PDF | **Fixed** | `paper/edbt-paper-template.tex:81`, `:95`, `:382`; PDF pp. 1 and 4 contain the revised abstract, three contributions, and Codex imperfect-user paragraph. `PdfReader` reports four pages. The broken reference at `:284` is also present in the PDF, supporting correspondence rather than a stale build. |
| 2 — mandatory MP4 | **Still open** | `git ls-files '*mp4' '*gif'` returns only `paper/video/murena_demo_nursery.gif`; `paper/README.md:9` says the video link remains to be added; `paper/edbt-paper-template.tex:218` nevertheless asserts that a video accompanies submission. External CMT upload: unverified. |
| 3 — wrong offline series | **Still open; additionally inconsistent export** | `frontend/.env.demo:3` still selects `imperfect_user_v4_comparison_seed13`. `frontend/vite.config.ts:11` embeds that source into `/benchmark`; `frontend/src/components/demo/DemoPanel.tsx:47` instead fetches the committed JSON. `frontend/public/data/benchmark_runs.json:1` contains 22 runs linked to `imperfect_user_codex_vlast`, covering only UC01–UC03. Neither is the complete cooperative Haiku replay promised by the revision plan. |
| 4 — scenario/results UI description | **Partly fixed** | `paper/edbt-paper-template.tex:205` now correctly says use case + k and one selected run, matching `DemoPanel.tsx:65` and `:70`, and removes the v4 three-behaviour claim. The eight-use-case/reported-series promise remains false for the committed configuration/assets: see R1 #3. |
| 5 — 144 screenshot results | **Fixed by the permitted caption remedy** | `paper/edbt-paper-template.tex:229` identifies an earlier live build and no longer states 144. The logged `bench_24b7eb94f445` still has 16 results; screenshots remain illustrative, not a faithful image of that benchmark artifact. |
| 6 — unrestricted opt-out generalization | **Fixed in body; partly fixed overall** | Demo activity restricts declines to Cb/Ce/Cp (`paper/edbt-paper-template.tex:193`); evaluation states the fixed phrase and scope (`:387`). Abstract `:81` still says every explicit decline was handled “as intended,” hiding the narrower state-tracking endpoint and residual declined-dimension atoms. |
| 7 — cross-series vague comparison | **Fixed** | Active paragraph `paper/edbt-paper-template.tex:396` reports Codex J5 0.74 against its own oracle and self-agreement 0.70, explicitly separating it from Haiku 0.87 (`:398`). Conditions are acknowledged to occupy different time windows (`:275`). Old Haiku 0.93 is inside `\iffalse` (`:361`). |
| 8 — contradiction scope | **Partly fixed** | `paper/edbt-paper-template.tex:168` narrows the claim to disambiguation. However, location disambiguation is a separate branch without the relation check (`backend/app/services/sage_clarification/service.py:1078`); the check is only in the generic ambiguity branch (`:1142`). Say “non-location ambiguity answers.” |
| 9 — EVPI oversell | **Fixed** | `paper/edbt-paper-template.tex:151` explains uniform alternatives, zero EVPI for open omissions, generation order, and heuristic status; contribution `:95` credits SAGE. Implementation: `service.py:702`, `uncertainty.py:41`. No efficiency gain from EVPI is claimed as measured. |
| 10 — k=0 latency | **Fixed** | `paper/edbt-paper-template.tex:202`: 11 s at k=0, 17–38 s for k≥1; recomputation gives 11.1 and 17.2–38.4 s. Analysis times are also medians, not bounds. |
| 11 — abstract ceiling/F1 and simulated answers | **Fixed** | `paper/edbt-paper-template.tex:81` explicitly states exact omitted-fragment answers and associates 0.87 with Jaccard; F1 is a separate sentence. Oracle F1 0.99 appears correctly in Table 1 (`:356`). |
| 12 — relaxation intents | **Fixed** | `paper/edbt-paper-template.tex:326` gives 36/6/10 and explicitly restricts one-shot relaxation to residential care. JSONL confirms these counts. |
| 13 — preliminary executions/defects | **Fixed for typeset paper; historical wording remains** | The inaccurate “A preliminary execution ... two blocking cases” is now only in the archived Haiku paragraph (`paper/edbt-paper-template.tex:375` within `:361`–`:380`). The active Codex paragraph makes no such claim. Historical reconstruction remains in the research record; do not count the archived sentence as a current measured result. |
| 14 — unreported metrics | **Fixed** | Active metrics `paper/edbt-paper-template.tex:291` remove tie-aware/invented-atom promises; `:333` reports detection 360/360 and `:338` gives p=0.008. Detailed v4 tables remain disabled (`:403`–`:607`). |
| 15 — figure reference/template count/relaxation attribution | **Fixed** | `paper/edbt-paper-template.tex:337` cites Fig. 3; `:117` explicitly lists all six dimensions; `:277` calls relaxation a pipeline option, not a contribution established by the original paper. |
| 16 — other blocking conditions | **Partly fixed** | Added at `paper/edbt-paper-template.tex:160`, but “a second unresolved answer on the same dimension” is too general: the counter applies to UNKNOWN/REJECTED omission answers (`service.py:995`–`:1010`), not UNCLEAR omissions (`:1024`) or unresolved location answers (`:1102`). |
| 17 — reproducibility | **Still open in manuscript; partly documented elsewhere** | `paper/edbt-paper-template.tex:400` discloses Codex dirty revision and `:653` gives general availability. Haiku equivalence to a5c1b09 is documented at `docs/okf/research/edbt-conversational-benchmark.md:417`, but not in the manuscript; exact property snapshots are not tracked (`git ls-files backend/data/metadata/estates.parquet` is empty). The local available file matches the Haiku hash, not Codex. |
| 18 — slot filling/clarifying IR | **Still open, reasonable camera-ready item** | `paper/edbt-paper-template.tex:100`–`:107` covers relevant SQL/LLM systems but not the slot-filling lineage or clarifying-question IR. More importantly, the conceptual overlap with the already cited interactive systems needs sharper explanation. |
| 19 — source cleanup/README/authors/figure typo | **Partly fixed** | `showcomments=false` at `paper/edbt-paper-template.tex:25`; `%% test` removed; `paper/figures/architecture.tex:36` now says “interpret.” Author names/affiliations are present (`:60`–`:69`); absent email addresses are not a demonstrated demo-track violation. README `:28` still incorrectly says four pages *plus* references and stale PDF; README-EDITORIAL `:36` contradicts the audience-driven plan. |

## 4. Findings

Line impacts estimate typeset column lines, not source lines. They require a final four-page rebuild; no margin/font reduction is proposed. Exact replacements below are recommendations only: this review does not edit the paper or runtime.

| # | Severity | Finding | Evidence (file:line or command) | Proposed fix, including paper wording and space impact | Timing |
|---|---|---|---|---|---|
| F1 | **blocker** | Mandatory MP4 is not available in the reviewed package; the accompanying-video assertion is unverified. A GIF is not an MP4 submission. | `paper/edbt-paper-template.tex:218`; `paper/README.md:9`; `git ls-files '*mp4' '*gif'`. [Official demo call](https://raw.githubusercontent.com/edbticdt2027/edbticdt2027.github.io/main/contents/call_for_demos.html), lines 21–22. | Supply and verify an MP4 ≤5 min with attendee interaction, setup and fallback, and verify its CMT upload. H.264/AAC are recommended by the call, not separately mandatory. Retain the paper sentence only after actual upload. **0 lines** if supplied; deleting the sentence saves about **1 line** but does not cure the submission blocker. | **Before deadline** |
| F2 | **major** | The paper, compiled benchmark page, and committed scenario replay disagree about source and coverage. This is more than a cosmetic stale path: replay exports cover only three of eight intents. | Paper `:206`–`:211`; `frontend/.env.demo:3`; `frontend/vite.config.ts:11`–`:18`; `frontend/src/components/demo/DemoPanel.tsx:47`–`:55`; JSON `frontend/public/data/benchmark_runs.json:1`. Join each exported `run_id` against the three candidate JSONLs: 22/22 match Codex vlast, 0 match Haiku or v4. | Point configuration at `missingness_v3_haiku_r2`, regenerate both run and estate exports, and verify all eight use cases and k=0…5 work and match `/benchmark`. Merely editing `.env.demo` does not replace the committed replay JSON. The existing paper paragraph can then remain. **0 paper lines.** | **Before deadline/video** |
| F3 | **major** | “Without network ... fully offline, so only typing new requests is lost” overstates fallback. Satellite basemap tiles remain remote and do not have an implemented offline alternative. Stored rankings/markers can survive while imagery disappears on a cold cache. | `paper/edbt-paper-template.tex:208`, `:215`–`:217`; `frontend/src/components/map/Map.tsx:576`–`:584`; `frontend/src/pages/MapPage.tsx:598`–`:612` passes no local tile URL; `frontend/src/demo/backend.ts:190` only mocks map config. | Replace the last setup sentence with: **“Without network, recorded conversations and rankings remain available; satellite imagery requires network access.”** About **−1 line**. Alternatively implement local basemap assets, rehearse with cache disabled and network disconnected, then retain a stronger statement only if verified. | **Before deadline** |
| F4 | **minor** | The abstract's “handled every explicit decline and every vague answer as intended” sounds like end-to-end faithful constraint handling or broad robustness. Verified universality is restricted to scripted clarification states/turns; no declined-dimension atoms is only 0.898 intent-mean, not 1. | `paper/edbt-paper-template.tex:81`, `:387`–`:397`; `backend/experiments/analyze_imperfect_user.py:94`–`:114`. | Replace that sentence with: **“A separate series with \mbox{\texttt{gpt-6-luna}} recorded all 105 scripted declines as non-preferences and followed up all 120 scripted vague replies.”** Approximately **+1–2 lines**; preserves model attribution and accurate endpoints. | **Before deadline** |
| F5 | **minor** | The controlled-evaluation contribution calls 304 runs “simulated interactions,” although 120 one-shot and 40 oracle runs have no dialogue. | `paper/edbt-paper-template.tex:96`; design at `:271`–`:274`; JSONL conditions. | Replace **“across 304 simulated interactions”** with **“across 304 pipeline runs”**. **0 to −1 line**. Abstract “304 benchmark runs” is already correct. | **Before deadline** |
| F6 | **minor** | Added blocking description does not match the actual branching policy. Repeated UNCLEAR/location answers are not counted by the two-answer counter; generic ambiguity UNKNOWN/REJECTED can become unanswerable immediately. | `paper/edbt-paper-template.tex:160`–`:162`; `service.py:995`–`:1029`, `:1102`–`:1112`, `:1135`–`:1136`; global limit `:797`. | Replace the two sentences with: **“A turn limit blocks unresolved sessions; repeated unknown or rejected omission answers can also block analysis. Experiments used six turns; the current default is twenty.”** About **−1 line**. This describes implemented behavior without promising one universal retry policy. | **Before deadline** |
| F7 | **minor** | “Disambiguation answers” still includes location disambiguation in ordinary reading, but the consistency check excludes that branch. | `paper/edbt-paper-template.tex:168`; `service.py:1078`, `:1114`, `:1142`. | Replace **“a separate check blocks disambiguation answers that contradict earlier requirements”** with **“a consistency check blocks conflicting non-location ambiguity answers”**. Approximately **−1 line**. | **Before deadline** |
| F8 | **minor** | A malformed cross-reference is visibly typeset as “Sec. efsec:demo”. This is source damage, not an unresolved LaTeX label. | `paper/edbt-paper-template.tex:284`–`:285`; committed PDF p. 3 left column. | Replace the split `Sec.~` / `ef{sec:demo}` with **`Sec.~\ref{sec:demo}`**. **0 lines**. Rebuild after this final edit. | **Before deadline** |
| F9 | **minor** | Project-facing instructions conflict with the corrected paper and could cause the wrong rehearsal/build decisions. | `paper/README.md:28` versus `:32`; `paper/README-EDITORIAL.md:36`–`:42` versus `paper/edbt-paper-template.tex:184`–`:217`; `docs/okf/research/conversational-paper-audit.md:127`–`:128` still labels Haiku imperfect users “in paper.” | Correct the README to four pages **including** references and current PDF status; align editorial instructions with audience-driven live mode and stored property replay; label the historical Haiku evidence as superseded in the research record. **0 paper lines.** Preserve history explicitly rather than deleting it. | **Before deadline** for rehearsal/build docs; historical labels may wait |
| F10 | **minor** | Metrics are recomputable, but exact experimental execution is not fully reproducible from release artifacts: both manifests identify dirty trees; the property snapshots are not versioned and the generic data portal does not reconstruct either exact byte sequence. | `paper/edbt-paper-template.tex:400`, `:653`–`:658`; Haiku manifest `:99`–`:109`; Codex manifest `:208`–`:218`; `docs/okf/research/edbt-conversational-benchmark.md:417`; `git ls-files backend/data/metadata/estates.parquet`. | Add after the availability repository sentence: **“Haiku used backend code equivalent to \texttt{a5c1b09}; exact property snapshots are identified by manifest hashes but are not distributed.”** About **+2–3 lines**; record clean source snapshots and deterministic dataset reconstruction outside the four-page paper. Equivalence excludes result files and cannot certify unrecorded dirty changes. | **Camera-ready**; useful before deadline if space permits |
| F11 | **minor** | Novelty is defensible as a domain-specific interaction mechanism/integration, but the final related-work contrast can imply that “requirements” do not overlap prior intent/context clarification. No evaluation isolates dialogue or EVPI from a static form/fixed order. | `paper/edbt-paper-template.tex:107`, `:151`–`:158`, `:309`–`:317`, `:648`–`:651`; [AmbiSQL author manuscript](https://arxiv.org/abs/2508.15276), [Sphinteract](https://www.vldb.org/pvldb/vol18/p1145-zhao.pdf). | Replace the last two Related Work sentences with: **“Our focus is the distinction between unresolved optional requirements and confirmed non-preferences in MURENA's fixed domain, with explicit review before portfolio screening; we do not propose a new general-purpose NL2SQL disambiguation algorithm.”** About **0 to +1 line**. Keep the stated lack of a form baseline. Add broader slot-filling/IR citations only after verification. | **Camera-ready**; sharpen contrast before deadline if feasible |
| F12 | **minor** | Fig. 2 is illustrative but its chat/card/filter text is very small at actual page size, and the opening walkthrough still directly associates it with the recorded k=2 example despite the earlier-build caveat. | `paper/edbt-paper-template.tex:220`–`:237`, `:248`; PDF p. 3, visually inspected at print scale. | Recapture a single coherent current session and crop to the question, opt-out/follow-up, editable review, and one readable result explanation. If keeping images, replace **“filters, map, and ranking of Fig.~\ref{fig:screens}”** with **“filters, map, and ranking, illustrated in Fig.~\ref{fig:screens}”**. **0 to +1 line**. Do not relabel the screenshots as measured benchmark evidence. | Caption clarification **before deadline**; recapture **camera-ready/video** |
| F13 | **minor** | “an analysis takes 72–83 s” describes a range of condition/level medians, not a bound on individual live requests. The claimed live viability has not been rehearsed in this review. | `paper/edbt-paper-template.tex:201`–`:203`; `compare_conditions.py:573`–`:590` operational aggregation; recomputed medians below. | Replace **“and an analysis takes 72--83\,s, which is compatible with live use”** with **“and median analysis time is 72--83\,s”**. About **−1 line**. Use the video/rehearsal to establish actual live responsiveness; no new large experiment is needed for submission. | **Before deadline** |
| F14 | **nit** | Bibliography is identifiable and all citations resolve, but the inherited MURENA entry lacks available volume/pages; three entries use arXiv notes rather than full archival links. No invented DOI should be added to fill these fields. | `paper/sample-base.bib:1`–`:9`, `:37`–`:42`, `:68`–`:73`, `:91`–`:96`; PDF p. 4; [Springer record](https://link.springer.com/chapter/10.1007/978-3-032-37682-4_26) lists volume 16949 and pp. 446–462. | Add verified **`volume = {16949}, pages = {446--462}`** to MURENA. Check publisher export for the year (online 2026 and book copyright year need not coincide). Add stable URLs to preprint-only identifiers if no archival DOI is verified. **0–2 bibliography lines**; avoid adding duplicate DOI URLs. | **Camera-ready** |

The text is already at four pages. F3/F5/F6/F7/F13 together recover roughly enough space for F4; F10/F11/F14 can wait. Reflow must be checked after changes; none of these line estimates guarantees the final page count.

## 5. Number check

### Method and provenance

Abbreviations below: **H** = `backend/experiments/results/missingness_v3_haiku_r2`; **C** = `backend/experiments/results/imperfect_user_codex_vlast`; **P** = `paper/edbt-paper-template.tex`. All JSONL paths are versioned at the reviewed commit. “Yes” means matching at displayed precision; it does not establish practical relevance or a causal advantage for dialogue.

I independently executed the analysis functions against JSONL/per-run artifacts, not merely read cached summary values. Final recomputation used **10,000 cluster-bootstrap samples, seed 13, RBO p=0.8, 1,000 tie permutations**, strict-majority oracle atoms, and the scripts' latest-attempt/input-hash policy. The active paper reports served rankings, so tie permutations do not affect its numbers. Earlier diagnostic calls with one permutation gave the same served metrics; a zero-permutation diagnostic was invalid and was discarded.

Reproduction from the repository root, without writing summaries:

```python
# Run with PYTHONDONTWRITEBYTECODE=1. No CLI main() calls are needed.
import argparse, sys
from pathlib import Path
sys.path.insert(0, 'backend/experiments')
from compare_conditions import load_rows, analyse
from analyze_imperfect_user import analyse as analyse_imperfect
H = Path('backend/experiments/results/missingness_v3_haiku_r2')
C = Path('backend/experiments/results/imperfect_user_codex_vlast')
args = argparse.Namespace(permutations=1000, seed=13, rbo_p=.8,
                          bootstrap=10000, reference_min_votes=None)
h = analyse(load_rows(H)[0], args)
c = analyse_imperfect(C, 10000, 13, 1000, .8)
```

**Audit-side-effect disclosure:** the first successful calls to the scripts' CLI entry points regenerated their cached summaries by default. Those files were restored from the reviewed Git blobs, with original CRLF working-tree form restored; `git diff --name-only` was empty afterward. Subsequent recomputation used the in-memory functions above. The only retained repository addition is this review.

Methods used in tables:

- **M1:** `load_rows` + cooperative `analyse`; intent-level paired means over k=1…5. See `compare_conditions.py:308`, `:416`, `:499`–`:567`. J5 uses all condition×oracle repetition pairs; oracle uses distinct repetition pairs; no both-empty pairs were excluded in H.
- **M2:** `analyse_imperfect` plus per-run conversations/scenario definitions. See `analyze_imperfect_user.py:58`–`:136`.
- **M3:** direct JSONL counts, group by `(condition, model, unit_id, repeat)`, and verify latest completion/artifact existence. For C, inspect all attempts before deduplication.
- **M4:** compare every CSV mean and endpoint to `h['ranking'][metric]['by_condition'][condition][k]` (all six J5/RBO columns match to <1e−14); plot source `P:617`–`:627`.
- **M5:** local `duckdb.sql("select count(*) from read_parquet('backend/data/metadata/estates.parquet')")`, SHA-256 of that file, and `git ls-files` to distinguish available local from distributed data.
- **M6:** inspect YAML and run `.venv/Scripts/python.exe backend/experiments/data/scenarios_v4/validate_scenarios_v4.py` with bytecode writing disabled. It validates 8,192 cases and 256 distinct source masks without LLM calls.

| Series | Model/provider | Dataset SHA-256 | Code provenance and separation |
|---|---|---|---|
| H | Claude Haiku 5.5 / `claude_cli`, medium effort | `bc6732c8ff55725619e0a0e163297792de049de35a210ab4ebe30f14a1f5dbc7` | Manifest records dirty `659f97f` and `4071a3a`; OKF identifies loaded backend a5c1b09. Independently, `git diff --name-only a5c1b09 659f97f -- backend ':!backend/experiments/results'` and the analogous 4071a3a diff are empty. This verifies committed backend equivalence, not unknowable uncommitted process state. |
| C | `gpt-6-luna` / `codex_exec`, low effort | `d3956041f120b33de94d1b7b6bd1da1a07c11ded37b077056ef58efd47d4f6da` | Manifest records dirty b530178 then 37e0732; do not apply H's ceiling or data to C. Seed 13 is recorded in C; it does not imply shared data or a randomized/interleaved H execution. |

Manifest evidence: `H/manifest.json:16`, `:91`–`:109`; `C/manifest.json:15`, `:19`, `:197`–`:218`. Earlier Haiku imperfect users and v4 seed-13 are archived in `P:361`–`:380` and `P:403`–`:607`; their numbers are **not** active paper claims. In particular the archived v4 “text tables” are not a second current Table 1. The active imperfect-user prose is audited as the requested text table below.

### Abstract, introduction, protocol and operational claims

| Claim | Location | Paper value | Recomputed value | Match? | Method |
|---|---|---|---|---|---|
| Cooperative total | P:81, :96, :274, :322 | 304 | 144 refined +120 one-shot +40 oracle =304, all latest and raw rows completed | **Yes** for runs; **no** for “304 simulated interactions” at :96 | M3 |
| Cooperative intents | P:81, :253, :325 | 8 | Eight base intents, all present per applicable cell | Yes | M3 |
| Clarification dialogues | Implicit in P:96, explicit :322 | 144 refined | 144; 120 have questions, 24 k=0 controls do not | Yes; scope correction F5 | M3 |
| Abstract/intro J5 improvement | P:81, :96 | 0.16 → 0.88 | 0.158571429 → 0.879365079 | Yes | M1 |
| Abstract/intro J5 self-agreement | P:81, :96 | 0.87 | 0.870238095 | Yes | M1, 8×C(5,2)=80 oracle pairs |
| Abstract filter F1 | P:81 | 0.61 → 0.98 | 0.607257719 → 0.979579248 | Yes | M1 |
| Abstract imperfect-user total | P:81 | 225 refined | 105 opt-out +120 vague =225 successful latest units | Yes | M2/M3 |
| Six dimensions/five optional omissions | P:117, :255 | 6; omit 5, keep I | I,D,L,Cb,Ce,Cp; omissions only D,L,Cb,Ce,Cp | Yes | YAML, H rows; not a new template |
| Nested variants/controls | P:256–:257 | 48; 8 k=0 variants | 8×6=48; 8 controls×3 repeats=24 k=0 runs | Yes | M3/YAML |
| Cooperative repetitions | P:271–:274 | 3 refined; 40 one-shot variants×3; 5 oracle/intent | 48×3=144, 40×3=120, 8×5=40 | Yes | M3 |
| Imperfect variants/repetitions | P:260, :384 | 75; 3 refined; 5 oracle/intent | 35 opt-out +40 vague =75; ×3=225; +40 oracle | Yes | M2/M3/YAML |
| Generator masks and size | P:263–:266 | 32/intent; 8,192 total | 2^5=32; 8×sum C(5,k)3^k=8×4^5=8192; validator passes | Yes; generator validation, not measured effectiveness | M6 |
| Property rows | P:277 | 89,200 | Local matching-H-hash Parquet has exactly 89,200 rows | Yes locally; exact C row count not independently checked | M5 |
| Nursery example | P:283–:289 | k=2; ≥600 sqm; capacity 45; class D or better; two turns | Submitted queries for `bench_24b7eb94f445` and `bench_d3c744f2613b` match the quoted text; refined turns=2 | Yes | Direct JSONL/per-run lookup; result count=16, not a current 144 claim |
| Metric depth/decay | P:294–:298 | J5, top-10 RBO, p=.8 | First five IDs; extrapolated RBO over stored ten at p=.8 | Yes | `compare_conditions.py:85`–`:108`, :344, M1 |
| Bootstrap | P:304–:306 | 95%; 8 clusters; B=10,000 | Percentiles .025/.975; eight intent means; B=10000 | Yes | `compare_conditions.py:271`, M1/M2 |
| Detection | P:333–:334 | 360/360; no FP | Sum expected omissions=360; 144/144 refined rows have P=R=F1=1; actual omissions equal expected | Yes | M3, compare `initial_missing`/`expected_initial_missing` |
| Turns/controls | P:332–:333 | exactly k; no k=0 questions | Every refined turns=k; 0/24 controls asked a question | Yes | M3 |
| Global paired significance | P:337–:339 | All 8 positive; p=.008 on J5/RBO/F1 | Every intent delta >0 for all three metrics; exact two-sided p=2/256=.0078125 | Yes | M1, `sign_flip_test` at :289 |
| Clarification latency | P:202 | 11 s k=0; 17–38 s k≥1 | Medians by k=0…5: 11.1,17.2,23.3,26.4,30.8,38.4 s | Yes rounded | M1 operational cells |
| Analysis latency | P:203 | 72–83 s | Condition/level median range 72.3–82.6 s; refined medians 73.8–75.7 s | Yes as medians; not a per-run bound | M1 |
| Cooperative completion/date/concurrency | P:322–:325 | 304; Nov 18; concurrency 10; no failed run/agent | 304 completed; UTC timestamps Nov 18; manifest concurrency 10; zero logged agent-error runs | Yes as recorded; scheduler concurrency not instrumented independently | M3, H manifest:112, :132–:135 |
| Relaxation | P:326–:328 | 52 =36 refined +6 one-shot +10 oracle | Refined UC03=18, UC07=18; one-shot UC07=6; oracle UC03=5, UC07=5 | Yes | M3 on `relaxation_applied` |
| Turn configuration | P:161–:162 | Experiments 6; current default 20 | Both manifests sage.max_turns=6; `backend/app/core/config.py:140` default=20 | Yes; this does not validate the generalized second-answer policy | Manifests/source |

### Table 1 — all displayed cells

Each recomputed entry is mean [95% CI]; columns retain their respective denominators. The first two condition means exclude k=0; completion includes k=0. CI rounding to 1.00 must not be read as exactly perfect agreement.

| Claim | Location | Paper value | Recomputed value | Match? | Method |
|---|---|---|---|---|---|
| Refined completion | P:353 | 144/144 (100%) | 144/144 =100% | Yes | M3 |
| One-shot completion | P:353 | 120/120 (100%) | 120/120 =100% | Yes | M3 |
| Oracle completion | P:353 | 40/40 (100%) | 40/40 =100% | Yes | M3 |
| Refined J5 | P:354 | .88 [.81,.96] | .879365 [.805278,.956151] | Yes | M1 |
| One-shot J5 | P:354 | .16 [.07,.25] | .158571 [.069980,.248710] | Yes | M1 |
| Oracle J5 self | P:354 | .87 [.79,.95] | .870238 [.786905,.950000] | Yes | M1 |
| Refined RBO@10 | P:355 | .94 [.90,.97] | .936881 [.896258,.966649] | Yes | M1 |
| One-shot RBO@10 | P:355 | .20 [.10,.30] | .196887 [.096250,.296545] | Yes | M1 |
| Oracle RBO@10 self | P:355 | .94 [.89,.98] | .942892 [.889170,.977241] | Yes | M1 |
| Refined filter F1 | P:356 | .98 [.96,1.00] | .979579 [.962353,.995065] | Yes | M1 |
| One-shot filter F1 | P:356 | .61 [.57,.65] | .607258 [.565189,.650758] | Yes | M1 |
| Oracle filter F1 self | P:356 | .99 [.98,1.00] | .990000 [.983333,.995000] | Yes | M1 |

### Fig. 3 — every plotted mean and interval

Values below reproduce `paper/data/per_k.csv:2`–`:12` and the coordinates read by `P:617`–`:627`. Paper and recomputed values are shown separately to make the full curve auditable rather than checking only its endpoints.

| Claim | Location | Paper/data value: mean [CI] | Recomputed: mean [CI] | Match? | Method |
|---|---|---|---|---|---|
| Refined k=0 | CSV:2; P:617 | .867857 [.771429,.952381] | .867857 [.771429,.952381] | Yes | M4 |
| Refined k=1 | CSV:3 | .875694 [.788988,.952381] | .875694 [.788988,.952381] | Yes | M4 |
| Refined k=2 | CSV:4 | .846032 [.752579,.939980] | .846032 [.752579,.939980] | Yes | M4 |
| Refined k=3 | CSV:5 | .873115 [.800000,.950000] | .873115 [.800000,.950000] | Yes | M4 |
| Refined k=4 | CSV:6 | .900000 [.836905,.963889] | .900000 [.836905,.963889] | Yes | M4 |
| Refined k=5 | CSV:7 | .901984 [.822569,.966667] | .901984 [.822569,.966667] | Yes | M4 |
| One-shot k=1 | CSV:8; P:622 | .497222 [.224206,.770238] | .497222 [.224206,.770238] | Yes | M4 |
| One-shot k=2 | CSV:9 | .152282 [.031250,.276910] | .152282 [.031250,.276910] | Yes | M4 |
| One-shot k=3 | CSV:10 | .080357 [.000000,.191964] | .080357 [.000000,.191964] | Yes | M4 |
| One-shot k=4 | CSV:11 | .049107 [.000000,.147321] | .049107 [.000000,.147321] | Yes | M4 |
| One-shot k=5 | CSV:12 | .013889 [.000000,.041667] | .013889 [.000000,.041667] | Yes | M4 |
| Dashed oracle line | P:627 | .870 | .870238095 | Yes rounded | M1 |
| Figure aggregation | P:631–:632 | 8 intents; 95% CI | Eight intent clusters; percentile 95% intervals | Yes | M1/M4 |

The dashed line is a point estimate of self-agreement, not a maximum attainable value or a proof that .88 is statistically equivalent to .87. A refined result can exceed it numerically. The manuscript correctly distinguishes oracle-reference agreement from independently assessed relevance (`P:278`, `:340`, `:649`); “matching” in the abstract should be read descriptively, not as a tested equivalence claim.

### Imperfect-user text results — denominators and all statistics

| Claim | Location | Paper value | Recomputed value | Match? | Method |
|---|---|---|---|---|---|
| Completed planned units | P:385–:386 | 265 =225 refined +40 oracle | 265 latest units; 225+40; all completed | Yes | M3 |
| Failed attempts/retries | P:386–:387 | 201 provider-error attempts rerun | 466 raw records =265 completed +201 error; 161 refined errors +40 oracle errors; all 201 failed unit keys later complete; all carry Codex CLI failure text | Yes; not 265/265 first-attempt success | M3 |
| Opt-out support | P:387–:391 | First omitted preference, Cb/Ce/Cp; 105 | Cb=51, Ce=27, Cp=27; total105; 35 variants×3 | Yes | M2 |
| Opt-out state/asking/turns | P:390–:391 | All105 NOT_REQUESTED; once on declined dimension; k turns | 105/105 on each endpoint | Yes; “one question” means on altered dimension, not whole dialogue | M2 |
| No declined-dimension atom | P:391–:392 | .90 [.71,1.00] | .897916667 [.710416667,1.000000000], intent-weighted | Yes | M2; not a raw-run fraction |
| F1 on other dimensions | P:392–:393 | .99 [.98,1.00] | .992254274 [.981570513,1.000000000] | Yes | M2 |
| Vague cases | P:394–:395 | 120 | 40 variants×3; Cb30, Ce15, Cp15, D30, L30 | Yes | M2 |
| Vague follow-up/turns/state | P:394–:395 | All120; k+1; SPECIFIED | 120/120 on all three endpoints | Yes | M2 |
| Vague filter F1 | P:396 | 1.00 [1.00,1.00] | .998888889 [.997222222,1.000000000] | Yes rounded; not exactly perfect | M2 |
| Vague J5 | P:396 | .74 [.59,.88] | .735158730 [.586884921,.880760582] | Yes | M2, only C oracle |
| Vague RBO@10 | P:397 | .82 [.72,.91] | .817920653 [.722280534,.910796994] | Yes | M2, only C oracle |
| C oracle J5 self | P:397–:398 | .70 [.51,.89] | .702827381 [.512797619,.892857143] | Yes | M2, 40 oracle runs, 80 distinct pairs, eight intent means |
| H comparison ceiling | P:398 | .87 | .870238095 from H alone | Yes; not C's ceiling | M1 |

**No quantitative contradiction was found in the active table, plotted data, or imperfect-user paragraph.** The two substantive numerical-language issues are the 304-dialogue implication (F5) and the abstract's conflation of state success with overall faithful handling (F4). The exact C snapshot's row count and dirty working-tree contents are unverified; no new results are inferred from them.

## 6. Demo-track assessment and formal check

**Attendee experience.** The four activities at `P:190`–`:200` are concrete and more convincing than a presenter-only canned scenario: omit, decline/hedge, edit/confirm, inspect. Live confirmation is implemented: `frontend/src/pages/SearchPage.tsx:254`–`:266` submits the edited review text with `clarification_confirmed=true`; backend readiness and rewrite occur at `service.py:740`–`:778`. The review explicitly acknowledges imperfect interpretation (`P:173`). The mechanism is believable from code and records, but an unrehearsed arbitrary audience request is not covered by exact-fragment simulations. The paper should retain that distinction and demonstrate both an unexpected input and successful fallback in the video.

**Latency and fallback.** Haiku stage medians imply roughly a minute and a half to two minutes of machine time for an incomplete request, before human answering; they do not justify an instant interaction claim. This can work at a demo desk if the presenter explains the state transitions and offers instant replay while analysis runs. C's vague clarification mean is 74.438 s, so the Haiku timing should not be transferred to the Codex path. Static replay correctly uses stored results after confirmation (`frontend/src/demo/backend.ts:98`–`:108`); changes to recorded answers/review in that path should not be presented as fresh model computation. The cold-cache imagery issue and split replay sources in F2/F3 are more likely to embarrass a live demonstration than a small metric difference.

**Novelty.** The inherited six-dimensional representation, specialized agents, SQL and ranking are clearly separated at `P:117`–`:124`; the regulatory expansion is appropriately supporting coverage (`:176`–`:180`). SAGE receives proper credit in the contribution, related work and method (`:95`, `:102`, `:148`). AmbiSQL already performs pre-SQL ambiguity clarification and rewriting, and Sphinteract already uses targeted interactive disambiguation; these are not new generic capabilities. The defensible delta is explicit optional-dimension state, the unresolved-omission versus non-preference distinction, a confirmation gate, and downstream screening visibility in this domain. The evaluation demonstrates information recovery under scripts, not superiority to these systems or to a form; the existing limitations at `P:309`–`:317` and `:648`–`:651` correctly admit this. [AmbiSQL](https://arxiv.org/abs/2508.15276), [Sphinteract](https://www.vldb.org/pvldb/vol18/p1145-zhao.pdf), and [SAGE](https://aclanthology.org/2026.findings-acl.2028/) substantiate this comparison.

**Figures.** Fig. 1 is a useful and legible new-versus-inherited diagram, although the five possible statuses are richer than its U/A loop label; use it as a conceptual sketch, not a complete state machine (`paper/figures/architecture.tex:18`, `:34`). Fig. 2 shows a real interface but the map/filter/cards occupy too many pixels relative to the readable interaction; most fine UI text is difficult at print size (`P:220`–`:237`). Fig. 3 is clear, has distinguishable marks and intervals, is referenced, and plots the correct cooperative series (`P:337`, `:617`–`:632`). The oracle uncertainty band is omitted, but Table 1 supplies its interval; this is not a numerical error.

**Most likely chair criticism:** “The manuscript describes an attractive participatory demo, but show me the required video of that experience; make the offline story true, and make the replay correspond to the evaluation you just reported.” The next concern is whether the audience sees a distinctive requirement-state/confirmation interaction or mostly a slow familiar clarification chatbot attached to the earlier MURENA map (`P:184`–`:218`, `:117`–`:124`). These are demo-track concerns, not a demand for another research-paper-sized benchmark.

Formal checks:

| Check | Outcome and evidence |
|---|---|
| Page limit including references | **Pass:** `pypdf.PdfReader('paper/edbt-paper-template.pdf')` has exactly **4 pages**; all 12 bibliography entries end on page 4. This agrees with the [official demo call](https://raw.githubusercontent.com/edbticdt2027/edbticdt2027.github.io/main/contents/call_for_demos.html), lines 34–39; do not use README's “plus references.” |
| Source/PDF correspondence | **Pass at content/layout level:** revised abstract, contribution bullets, Codex paragraph, corrected old-build caption, showcomments-off behavior, and even the damaged reference agree. PDF SHA-256: `26926c05b5b11a9db5b8b82854acfed118dbe576c049ad024f6cd669ba281375`; metadata CreationDate `20261118212346Z`. No byte-identical rebuild was attempted, so binary reproducibility/build-log warnings are unverified. |
| Template/non-anonymity | `paper/edbt-paper-template.tex:10` uses `acmart` sigconf,review; `:11`–`:13` specifies A4 geometry, consistent with the conference's updated A4-template direction. Names and affiliations are present (`:60`–`:69`); review line numbers are visible on pp. 2–4. The exact distributed conference template archive was not compared byte-for-byte; I found no visible formatting violation. [Official research-format instructions](https://raw.githubusercontent.com/edbticdt2027/edbticdt2027.github.io/main/contents/EDBT_CFP.html), lines 143–150, explicitly require the updated A4 template. |
| Comments/author notes | `showcomments=false` (`P:25`), no active DANIELE/MARCO/SIMONE notes or TODOs, no `%% test`. The old abstract remains in `%` comments (`:77`–`:79`); the Haiku and v4 history is genuinely disabled, including nested `\iffalse` (`:361`, `:403`, `:448`, `:606`–`:607`). Do not count those archived tables/results against the active narrative. |
| Bibliography/DOIs | All 12 cited keys resolve in the PDF. Nine entries contain DOIs, three contain arXiv identifiers. Primary-source checks support MURENA, COOL, FISQL, Sphinteract, SAGE, CLAMBER, PRACTIQ, AmbiQT and the three preprint identities; the ACM RBO landing page returned 403, so its current publisher metadata is **unverified**, although the DOI is present. No evidence supports claiming the bibliography is fabricated. Minor completeness issue F14 remains. |
| Overfull lines/layout | All four pages rendered with `pypdfium2` and were visually inspected. No clipped body lines or overlapping figures/tables were visible; Table 1 is small but legible, Fig. 2's detailed UI text is too small. No `.log` is committed and I did not compile sources, so **absence of TeX overfull/underfull warnings is unverified**. F8 is a visible reference defect. |
| Template placeholders | `paper/edbt-macros.tex:6`–`:12` retains ISBN/ISSN/publication-date placeholders, visible in the first-page footer. These are publication metadata to replace when supplied for camera-ready, not measured claims or author TODOs; do not invent values. |
| Setup/fallback description | Present (`P:213`–`:218`) and adequate in intended structure, but F2/F3 make its current factual implementation incomplete. |
| Mandatory media | **Not verified/supplied in repository.** Only GIF is tracked; MP4 duration, playback, and CMT attachment are unverified. |

Primary bibliography checks: [MURENA publisher record](https://link.springer.com/chapter/10.1007/978-3-032-37682-4_26), [COOL proceedings](https://openproceedings.org/2021/conf/edbt/p145.pdf), [FISQL proceedings](https://openproceedings.org/2025/conf/edbt/paper-300.pdf), [Sphinteract proceedings](https://www.vldb.org/pvldb/vol18/p1145-zhao.pdf), [SAGE](https://aclanthology.org/2026.findings-acl.2028/), [CLAMBER](https://aclanthology.org/2024.acl-long.578/), [PRACTIQ](https://aclanthology.org/2025.naacl-long.13/), [AmbiQT](https://aclanthology.org/2023.emnlp-main.436/), [AmbiSQL](https://arxiv.org/abs/2508.15276), [AMBROSIA](https://arxiv.org/abs/2406.19073), [QuestBench](https://arxiv.org/abs/2503.22674). These checks verify identification/attribution, not every experimental claim in those external papers.

**Submission readiness.** Before the deadline: supply and verify the mandatory MP4; align and rehearse replay sources/coverage; qualify or repair offline imagery; correct the damaged reference and the short overstatements F4–F7/F13; rebuild and verify the final four-page PDF. Updating the rehearsal/build READMEs is important because they currently contradict the submitted interaction plan. Exact dataset reconstruction, a clean execution-source snapshot, broader related work, bibliography polish and better screenshots can wait until camera-ready; a user study, form baseline and EVPI ablation are future research rather than prerequisites for an honest demo submission. Conference metadata can be filled when provided. No OKF or paper files were updated in this task because the requested deliverable is a read-only review, not implementation or manuscript revision.

## 7. Questions to the authors

1. Where is the submitted MP4, and does it show an attendee-entered request, a vague follow-up, a decline, edited confirmation, results, and a genuinely disconnected fallback? (`P:184`–`:218`.)
2. Which artifact set will attendees actually replay? Why are `.env.demo`, embedded `/benchmark` data, and the committed 22-run/three-intent export different? (`frontend/.env.demo:3`; `frontend/vite.config.ts:11`; `frontend/public/data/benchmark_runs.json:1`.)
3. What happens to the map on a cold laptop with Wi-Fi disabled, given the remote Esri TileLayer? (`frontend/src/components/map/Map.tsx:576`–`:584`.)
4. What makes the dialogue preferable to a six-field optional form for the target domain expert, and what benefit is expected specifically from EVPI ordering when open omissions have zero EVPI? I do not require an unexecuted study to be reported as a result. (`P:151`–`:158`, `:309`–`:317`, `:648`–`:651`.)
5. How do you explain an explicit non-preference that is correctly recorded but still produces an atom on that dimension downstream? Will attendees see that distinction and be able to inspect it? (`P:390`–`:393`; `analyze_imperfect_user.py:94`–`:104`.)
6. Which model/provider and property snapshot will the live demo use, what are its observed upper-tail latencies, and what does the presenter show during the analysis wait? The Haiku medians do not characterize every supported model. (`P:201`–`:203`, `:319`–`:323`, `:382`–`:401`.)
7. Can you release clean source snapshots or patches for both dirty execution histories and deterministic reconstruction instructions for each dataset hash? (`H/manifest.json:99`; `C/manifest.json:208`; `P:653`–`:658`.)
8. Is the intended stopping policy “one follow-up for all unresolved answers,” or deliberately different policies for omission UNKNOWN/REJECTED, UNCLEAR and location ambiguity? (`P:160`; `service.py:995`, `:1024`, `:1102`, `:1135`.)
