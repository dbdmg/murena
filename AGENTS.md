## Knowledge Base and Paper Maintenance

The `docs/okf/` directory is the authoritative technical and scientific knowledge base of MURENA.
The `paper/` directory contains the editable LaTeX sources of the current research paper.
Keep both aligned with the implementation and verified evidence, without treating every code change as a paper contribution.

### Before starting a task
- Read `docs/okf/index.md` and `docs/okf/project/overview.md`.
- Consult relevant OKF documents based on the task.
- Check `docs/okf/project/evidence-boundaries.md` when dealing with scientific claims or experimental results.
- For tasks affecting research framing, experiments, benchmarks, methodology, or reported results, inspect the relevant LaTeX files, bibliography, and any paper-specific instructions in `paper/` before editing them.
- Identify whether the change affects the original MURENA pipeline, the conversational extension, or only supporting resources; preserve that distinction.

### After completing a task: OKF
- Update `docs/okf/` when architecture, APIs, data models, agent behavior, configurations, scientific results, or research decisions change.
- Update `docs/okf/log.md` with significant changes.
- Update `docs/okf/project/overview.md` when the general project context changes.
- Update relevant documents in `docs/okf/research/` when new evidence affects scientific claims.
- Keep documentation consistent with the actual implementation.
- Preserve historical findings, sources, and provenance.
- Distinguish verified evidence, paper-reported results, and hypotheses.
- Do not modify `docs/okf/` for trivial code changes.

### After completing a task: LaTeX paper
- Assess whether the completed work affects the paper's scientific content. If it does, update the relevant sources in `paper/` **in the same task**, alongside the OKF changes.
- In particular, synchronize relevant changes to the system architecture, clarification strategy, scenario generation, experimental protocol, baselines, metrics, evaluation findings, limitations, and research claims.
- Keep the abstract, contributions, methodology, evaluation, discussion, figures/tables, and bibliography mutually consistent; edit only sections affected by the change.
- Preserve the paper's established scientific scope: the six optional query dimensions, specialized agents, SQL construction, and ranking pipeline are inherited from MURENA. The conversational elicitation and confirmation stage is the primary contribution; the expanded regulatory catalogue is supporting coverage rather than a new query template or algorithm. Attribute the EVPI-inspired clarification strategy to SAGE-Agent.
- Describe benchmark conditions precisely (e.g., one-shot, refined, and oracle). Distinguish an oracle query or reference ranking from independently verified ground truth on property relevance. Do not report unexecuted experiments or planned metrics as measured findings.
- When benchmark inputs or evaluation scripts change, update the paper's experimental setup only to reflect the version actually used or explicitly planned, and document the version/status. Do not silently replace earlier reported results or mix results from different benchmark versions.
- Update bibliography entries when adding or removing cited work. Preserve citation keys and project-specific LaTeX conventions.
- If LaTeX sources change and the required tools are available, compile the paper, resolve introduced errors, and check page limits and major layout regressions. Do not manually edit generated PDFs in place of the source.
- When a change is not relevant to the paper, leave `paper/` untouched. Never add unsupported novelty claims, placeholder numbers presented as results, or speculative conclusions.
- Summarize in the final response which OKF and paper files were updated, or why no paper change was warranted.

### Consistency Rules
- Treat source code as the authority for implemented behavior.
- Treat the original paper and verified experiments as the authority for established scientific claims.
- Treat OKF as the detailed research record and `paper/` as a selective, publication-oriented synthesis: do not copy all OKF notes into the manuscript.
- Distinguish implemented, tested, planned, and hypothesized behavior in both locations.
- Never invent experimental results or present unverified claims as facts.
- Do not duplicate information unnecessarily across OKF documents.
- Preserve OKF structure, metadata, and internal links.
- Preserve author-written LaTeX content and existing citations unless an evidence-backed change requires revision.
- Never modify runtime configuration or agent prompts solely to synchronize documentation.
- Include relevant OKF and paper updates in the same Git commit as the implementation, whenever they form part of the same change.
