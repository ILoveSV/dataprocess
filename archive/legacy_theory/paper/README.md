# Paper

This folder is reserved for Chinese paper writing and integration.

The calculation package remains in `../ship_efield_theory/`. This folder should only contain manuscript text, references, selected figures, and final paper builds.

Suggested compile command after LaTeX is installed:

```powershell
xelatex -output-directory=build main.tex
bibtex build/main
xelatex -output-directory=build main.tex
xelatex -output-directory=build main.tex
```

From the parent folder, all preview PDFs can be regenerated with:

```powershell
.\compile_latex_previews.ps1
```
