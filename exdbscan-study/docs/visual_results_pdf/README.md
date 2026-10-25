# LaTeX Version of the Visual Results Report

The original English Markdown report remains at `../visual_results.md`.
This folder contains its complete LaTeX version, all five figure images, and
the PDF rendered from that source.

## Files

- `main.tex`: complete, editable LaTeX source.
- `images/`: the five report figures, copied from `../../results/figures/`.
- `visual_results.pdf`: the compiled report.
- `compilation.json`: compiler information and hashes for the verified PDF,
  source, Markdown report, and figure inputs.

## Compile

From this directory, with Tectonic installed:

```bash
mkdir -p build
tectonic --untrusted --keep-logs --outdir build main.tex
cp build/main.pdf visual_results.pdf
```

Alternatively, with a standard TeX distribution and latexmk:

```bash
latexmk -pdf -outdir=build main.tex
cp build/main.pdf visual_results.pdf
```

The first Tectonic run may download standard TeX packages and fonts. Compilation
uses the local source and images. These rendering tools are optional and do not
change the dependencies of DBSCAN or ExDBSCAN.

The Markdown report and LaTeX source are separate editable files. Keep their
content synchronized when revising the report. The recorded hashes describe
the delivered version and must be refreshed after changes if used for auditing.
