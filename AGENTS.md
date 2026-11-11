## Knowledge Base Maintenance

The `docs/okf/` directory is the authoritative technical and scientific knowledge base of MURENA.

### Before starting a task
- Read `docs/okf/index.md` and `docs/okf/project/overview.md`.
- Consult relevant OKF documents based on the task.
- Check `docs/okf/project/evidence-boundaries.md` when dealing with scientific claims or experimental results.

### After completing a task
- Update `docs/okf/` when architecture, APIs, data models, agent behavior, configurations, scientific results, or research decisions change.
- Update `docs/okf/log.md` with significant changes.
- Update `docs/okf/project/overview.md` when the general project context changes.
- Update relevant documents in `docs/okf/research/` when new evidence affects scientific claims.
- Keep documentation consistent with the actual implementation.
- Preserve historical findings, sources, and provenance.
- Distinguish verified evidence, paper-reported results, and hypotheses.
- Do not modify `docs/okf/` for trivial code changes.
- Include relevant OKF updates in the same Git commit as the implementation.

### Consistency Rules
- Treat source code as the authority for implemented behavior.
- Treat the original paper and verified experiments as the authority for scientific claims.
- Never invent experimental results or present unverified claims as facts.
- Do not duplicate information unnecessarily across OKF documents.
- Preserve OKF structure, metadata, and internal links.
- Never modify runtime configuration or agent prompts solely to synchronize documentation.