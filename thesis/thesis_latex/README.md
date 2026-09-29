# thesis_latex

## 当前状态（2026-09-26）

当前论文主线以[论文总体判断与写作主线](../../docs/论文总体判断与写作主线.md)为准，采用六章结构。本轮仅重写第一章，旧第二至五章尚未迁移；`main.tex`和旧`build/main.pdf`不能作为当前六章终稿。

- [第一章阅读稿](第一章_绪论_初稿_20260926.md)：与LaTeX正文一致的Markdown副本，含数字引用和11条参考文献。
- [第一章可编辑源文件](chapters/chapter01_introduction.tex)：正文的唯一编辑源。
- [文献核查与待补项](第一章_文献核查与待补项_20260926.md)：区分全文/摘要依据、引用边界和待导师确认事项。
- [单章PDF](../../deliverables/pdf/第一章_绪论_初稿_20260926.pdf)：独立编译，不覆盖旧整篇PDF。
- [历史文件快照](../../archive/snapshots/thesis_planning_20260926/README.md)：含本轮修改前的第一章和参考文献。

在本目录生成阅读稿：

```powershell
pandoc chapters/chapter01_introduction.tex references.tex --from=latex --to=gfm --wrap=none --lua-filter=chapter01_to_markdown.lua --output=第一章_绪论_初稿_20260926.md
```

单章预览入口是`chapter01_preview.tex`，使用原工程样式。可运行两次`xelatex -interaction=nonstopmode -halt-on-error chapter01_preview.tex`解析交叉引用；建议另设输出目录，不混入历史整篇构建目录。本轮机器的`latexmk`因缺Perl未成功，直接调用已有XeLaTeX两次已成功，没有安装或改动工具链。

封面题目、作者和样式中的旧日期没有擅自调整；第一章预览不含旧封面。现有样式来自历史Word模板，不表示已经核验最新学校提交要求。

## 历史迁移说明

本工程由两个 Word 文件迁移生成：

- 内容来源：`../程家诺-极化带效应水下目标探测感知.docx`
- 格式来源：`../极化带效应水下目标探测感知.docx`

## 编译方法

Windows 下运行：

```bat
compile.bat
```

或手动运行：

```bat
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
```

输出 PDF：`build/main.pdf`。

## 已实现格式

- A4 页面；上 3.5 cm，下 4 cm，左侧含 0.5 cm 装订线，右 2.5 cm。
- 中文优先宋体，标题优先黑体，英文和数字优先 Times New Roman。
- 若本机没有对应字体，样式文件回退到 Fandol/TeX Gyre 字体，不复制或嵌入字体文件。
- 标题、目录、正文、图表、公式编号按 Word 模板批注近似实现。
- 当前参考文献使用`references.tex`中的`thebibliography`与正文引用键关联；最终格式仍需按学校要求复核。

## 清理与 TODO

- 草稿摘要为模板示例文本，已删除并用 TODO 标注。
- “本文……”“各学科和学院自定”“学位论文是研究生……”等模板占位未进入正文。
- Word 中 3 个媒体文件已导出到 `figures/`；SVG/EMF 暂未自动嵌入。
- Word 中的高频感应加热表格明显为模板示例，已在第 4 章作为占位并标注 TODO。
- 原迁移稿只保留两条信号处理参考；本轮已备份原件，按第一章实际引用替换为11篇核查过的文献。

## 结构

- `main.tex`：主入口
- `sjtu_thesis_style.tex`：页面、字体、标题、目录、图表样式
- `frontmatter/`：封面、声明、摘要
- `chapters/`：第一章新稿及尚未迁移的旧第二至五章
- `backmatter/`：附录、致谢、成果目录
- `figures/`：从 Word 提取的媒体文件
- `format_requirements.md`：从模板批注整理的格式要求
