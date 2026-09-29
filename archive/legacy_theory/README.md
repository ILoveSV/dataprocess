# Calculation and Paper

This folder is for pure theoretical calculations and later LaTeX-based paper integration.

## Structure

- `main.tex`: main LaTeX entry point.
- `sections/calculations.tex`: theoretical derivations and formula notes.
- `references.bib`: bibliography database.
- `figures/`: optional figures for the final paper.
- `build/`: generated PDF and auxiliary files.

## Suggested Compile Command

```powershell
xelatex -output-directory=build main.tex
bibtex build/main
xelatex -output-directory=build main.tex
xelatex -output-directory=build main.tex
```

## Compile All Previews

```powershell
.\compile_latex_previews.ps1
```
