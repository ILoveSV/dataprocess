# 论文工程

[论文大纲 PDF](论文终稿/build/outline.pdf)用于审阅目录和分段安排。[大纲入口](论文终稿/outline.tex)包含全篇结构，[绪论大纲](论文终稿/chapter01-plan.tex)记录第一章各节与段落的写作安排。更新大纲时在终稿目录运行两次 `xelatex -output-directory=build outline.tex`。

[论文终稿 PDF](论文终稿/build/main.pdf)与大纲 PDF 并列存放。[终稿入口](论文终稿/main.tex)通过 [manuscript.tex](论文终稿/manuscript.tex)组织章节和参考文献。更新终稿时，在终稿目录依次运行 `xelatex -output-directory=build main.tex`、`biber --input-directory=build --output-directory=build main`，再运行两次相同的 XeLaTeX 命令。

当前论文只在 `论文终稿/` 编辑。[历史论文资料](history/README.md)保留旧 LaTeX、Word、章节源稿及历史导出供参考，不接入当前正文，也不替代研究数据和计算结果。

正文引文按首次出现顺序编码。转述写作 `[8]`。直接引述原文时，在序号后加所引页码，例如 `[8]113`。确需在正文定位到某一段落时可使用脚注。正文引文在 LaTeX 正文中维护，文献条目集中存放于 [references.bib](论文终稿/references.bib)。大纲记录章节结构、写作内容和需要明确的研究问题。提交版按学院模板统一引文样式。
