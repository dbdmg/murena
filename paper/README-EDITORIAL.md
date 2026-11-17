# Conversational MURENA -- EDBT demonstration draft

## Revised scientific framing

This version deliberately **starts from the limitation explicitly acknowledged
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
Work is placed after the walkthrough and focuses on COOL, FISQL, AmbiSQL,
and SAGE-Agent. Broader spatial/OLAP demos are omitted because the novelty
here is clarification rather than spatial querying or ranking.

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
5. If claiming measurable improvement, run a controlled comparison against
   MURENA's single-shot interface with incomplete/ambiguous inputs.

## Build

Run `pdflatex edbt-paper-template.tex`, `bibtex edbt-paper-template` (or
`bibtex.original` on systems with a broken BibTeX alternative), then
`pdflatex` twice in this directory. Bundled class, bibliography and EDBT
macros are retained from the user's source template.
