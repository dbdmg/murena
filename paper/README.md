# Conversational MURENA — editable EDBT LaTeX source

This is a **reconstructed manuscript draft** based on the provided EDBT LaTeX template and the methodological decisions from this conversation. The exact previously generated `.tex` file was not mounted in the current session.

The draft retains the inherited six-dimension MURENA query template, pre-analysis clarification, explicit user opt-outs, SAGE-inspired clarification policy, and a minor regulatory-catalogue extension. It updates the evaluation section to the missingness-v2 protocol: eight base oracle intents, five omission levels (40 incomplete scenarios), eight zero-missing controls, and the original 24 robustness scenarios as a separate suite.

Ranking agreement uses the fully specified oracle query as an **operational reference**, not independent relevance ground truth. Planned metrics include atomic-requirement F1, completion, latency, Top-5 Jaccard and RBO@5. **No experimental results are reported.**

Edit `edbt-paper-template.tex` and `sample-base.bib`; replace the author and affiliation placeholders. Compile from this directory:

```bash
pdflatex -interaction=nonstopmode -halt-on-error edbt-paper-template.tex
bibtex edbt-paper-template  # on this environment: bibtex.original
pdflatex -interaction=nonstopmode -halt-on-error edbt-paper-template.tex
pdflatex -interaction=nonstopmode -halt-on-error edbt-paper-template.tex
```

The bundled template is from the original `MURENA_demo(1).zip`. The rendered PDF currently contains three pages, including references. Check the submission-year call, final author metadata and any figures/screenshots before submission.
