# Conversational MURENA -- EDBT demonstration draft

## Revised scientific framing

This draft deliberately **starts from the limitation explicitly acknowledged
in the original MURENA paper**: the initial query is assumed to be sufficiently
specified, and ambiguous/underspecified input can produce suboptimal agent
configurations. The new demo resolves this through **pre-analysis,
conversational requirement elicitation**.

This is not a claim that the original MURENA requires *every* query dimension.
The original query has optional dimensions. The issue is distinguishing
ambiguity, unconfirmed omissions, and genuinely irrelevant criteria.

The EDBT demonstration's specific delta is:

1. Stateful clarification across `I, D, L, Cb, Ce, Cp`.
2. Context-dependent questions, user answers, and explicit opt-outs.
3. Final editable natural-language query and user approval.
4. Handoff to the original SQL-based filtering, agent scoring, explanation,
   and visual analytics without changing those methods.

The diagram and demonstration steps follow precisely this sequence. Related
Work (Section 2) covers clarification in LLMs (CLAMBER, QuestBench,
SAGE-Agent) and ambiguity/interaction for data access (AmbiQT, AMBROSIA,
PRACTIQ, AmbiSQL, FISQL, COOL). Broader spatial/OLAP demos are omitted
because the novelty here is clarification rather than spatial querying or
ranking.

The demonstration uses the nursery request of scenario MS02_k2
(C_b and C_e omitted, two questions). The UI does not display
per-dimension states; the backend maintains them and Fig. 1 explains them.
The regulatory catalogue in
`backend/docs/knowledge/normativa/normativa.json` has eight use cases.

The demonstration is a single prepared nursery-conversion scenario with a
predefined request and answers. The presenter explains the interaction;
arbitrary audience input and a separate open-ended path are outside the
presentation plan. This editorial scope does not restrict the live system's
conversational capabilities or alter the benchmark protocol. The captured
backend session and its property results remain distinct from the frontend's
offline scripted mode, which contains no property results.

## Implementation-aligned caveats

- Clarification happens **before** the MURENA analysis run, not as a
  post-processing conversation to modify a computed ranking.
- In the provided code, every unconfirmed omitted dimension must be resolved
  or explicitly declined; EVPI is a **heuristic ordering** signal, not evidence
  of fewer turns or calibrated intent probabilities.
- The example question wording and choices illustrate an interaction; the
  precise text is generated at runtime by the configured LLM.
- `ENABLE_SAGE_CLARIFICATION=true` by default in the repository; it can be disabled by configuration.
- The published evaluation uses about 90,000 EPC records; the reproducible
  local demo has 1,500 **synthetic** Turin records. They must not be conflated.

## Before submitting

1. Confirm the author list, affiliations and ORCIDs (placeholders remain).
2. Replace or supplement the conceptual diagram with genuine screenshots of
   the multi-turn dialogue and the final map/ranking interface.
3. Confirm the actual audience deployment and the dataset it will use.
4. Check the final EDBT demo-track formatting and page limits.
5. Keep the reported 115 completed runs (and 8 failed) distinct from the 304-run plan.
   Before updating the table or figure, verify the benchmark outputs and
   document their provenance in OKF; preserve the incomplete-coverage caveat.

## Build

See `README.md` (Tectonic build in a copy of this directory). Bundled
class, bibliography and EDBT macros are retained from the user's source
template.
