# thesis_latex

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
- 参考文献暂用 `references.tex` 手工列表，接近 GB/T 7714-2015。

## 清理与 TODO

- 草稿摘要为模板示例文本，已删除并用 TODO 标注。
- “本文……”“各学科和学院自定”“学位论文是研究生……”等模板占位未进入正文。
- Word 中 3 个媒体文件已导出到 `figures/`；SVG/EMF 暂未自动嵌入。
- Word 中的高频感应加热表格明显为模板示例，已在第 4 章作为占位并标注 TODO。
- 草稿参考文献中大量条目为模板示例，目前只保留与信号处理相关的前两条，其余需按正文实际引用补充。

## 结构

- `main.tex`：主入口
- `sjtu_thesis_style.tex`：页面、字体、标题、目录、图表样式
- `frontmatter/`：封面、声明、摘要
- `chapters/`：五章正文
- `backmatter/`：附录、致谢、成果目录
- `figures/`：从 Word 提取的媒体文件
- `format_requirements.md`：从模板批注整理的格式要求
