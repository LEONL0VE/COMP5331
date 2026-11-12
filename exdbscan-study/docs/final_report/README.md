# COMP 5331 Final Report Draft

This directory contains the editable LaTeX source, compiled draft, and the figure files used in the report.

- `main.tex`: report source.
- `references.bib`: BibTeX records for the sources cited in the report.
- `main.pdf`: compiled draft for review.
- `images/`: figures from the visual-results materials and Explorer screenshots.

Compile from this directory with a standard LaTeX installation:

```text
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Before submission, have each member verify their own contribution statement and the course declaration. Each contribution must be 100--500 words.

## Robustness extension in the paper

The methods section covers certified positional robustness and fixed-endpoint
parameter stability. The experiment protocol and paired three-method table use
[the summary](../../results/robust/summary.json) and
[per-case results](../../results/robust/cases.csv); they are separate from the
original coverage experiments and the USGS parameter sweeps. See
[the detailed extension notes](../robust_extension.md) for implementation and
reproduction commands. Contribution statements retain the current group wording.
