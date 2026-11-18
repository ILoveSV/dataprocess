# -*- coding: utf-8 -*-
"""
Markdown 报告生成辅助模块
- 自动分析文字生成
- BLOCK内容构建
"""
import os
import numpy as np
from datetime import datetime


def _fmt(v, digits=4):
    """格式化数值"""
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            return f"{v:.{digits}g}"
        return str(v)
    return str(v)


def build_similarity_block_md(state_names, method_results, viz_img=None, preprocess_info=None):
    """构建相似性计算的BLOCK内容

    state_names: [name_a, name_b]
    method_results: list[dict] 每项 {'method', 'value'}
    viz_img: 可视化图片路径（可选）
    preprocess_info: 预处理方法信息字符串（可选）
    """
    from experiment_state import STATE_REGISTRY

    parts = []
    parts.append("### 实验状态详细信息")
    parts.append("")
    parts.append(STATE_REGISTRY.to_markdown_table(state_names))
    parts.append("")

    if preprocess_info:
        parts.append("### 数据预处理方法信息")
        parts.append("")
        parts.append(preprocess_info)
        parts.append("")

    parts.append("### 计算结果列表")
    parts.append("")
    parts.append("| 方法 | " + " | ".join(state_names) + " |")
    parts.append("| " + " | ".join(["---"] * (len(state_names) + 1)) + " |")
    for r in method_results:
        parts.append(f"| {r['method']} | {r['value']} |")
    parts.append("")

    if viz_img:
        parts.append("### 可视化图")
        parts.append("")
        parts.append(f"![相似性可视化]({viz_img})")
        parts.append("")

    # 自动分析文字
    parts.append("### 自动分析")
    parts.append("")
    parts.append(_auto_analysis(state_names, method_results))
    parts.append("")
    return "\n".join(parts)


def _auto_analysis(state_names, method_results):
    """根据计算结果生成简单的分析文字"""
    numeric = [r for r in method_results if isinstance(r['value'], (int, float))]
    if not numeric:
        return "本次计算未得到有效数值结果，请检查数据或方法。"

    lines = []
    lines.append(f"本次对 **{', '.join(state_names)}** 进行了 {len(method_results)} 种方法的相似性计算，"
                 f"其中 {len(numeric)} 种方法得到有效数值结果。")

    # 找出最大/最小相似性
    try:
        vals = [(r['method'], float(r['value'])) for r in numeric]
        # 区分距离型（越小越相似）和相似度型（越大越相似）
        sim_keywords = ['相似度', '相关', '互信息', '重叠', '相干', 'SSIM', 'NMI']
        sim_vals = [(m, v) for m, v in vals if any(k in m for k in sim_keywords)]
        dist_vals = [(m, v) for m, v in vals if not any(k in m for k in sim_keywords)]

        if sim_vals:
            best = max(sim_vals, key=lambda x: x[1])
            worst = min(sim_vals, key=lambda x: x[1])
            lines.append(f"在相似度类指标中，**{best[0]}** 取得最大值 {_fmt(best[1])}，"
                         f"表明两状态在该度量下最为接近；**{worst[0]}** 取得最小值 {_fmt(worst[1])}。")
        if dist_vals:
            best = min(dist_vals, key=lambda x: x[1])
            worst = max(dist_vals, key=lambda x: x[1])
            lines.append(f"在距离类指标中，**{best[0]}** 取得最小值 {_fmt(best[1])}，"
                         f"表明两状态在该度量下差异最小；**{worst[0]}** 取得最大值 {_fmt(worst[1])}。")
    except Exception:
        pass

    lines.append("综合各指标可判断两实验状态在时域/频域特征上的整体相似程度，"
                 "建议结合具体物理意义选择关键指标进行重点分析。")
    return "\n\n".join(lines)


def build_matrix_block_md(state_name, matrix_results, viz_img=None, preprocess_info=None):
    """构建矩阵转换的BLOCK内容"""
    from experiment_state import STATE_REGISTRY

    parts = []
    parts.append("### 实验状态详细信息")
    parts.append("")
    parts.append(STATE_REGISTRY.to_markdown_table([state_name] if state_name else None))
    parts.append("")

    if preprocess_info:
        parts.append("### 数据预处理方法信息")
        parts.append("")
        parts.append(preprocess_info)
        parts.append("")

    parts.append("### 矩阵转换结果")
    parts.append("")
    parts.append("| 方法 | 形状 | 最小值 | 最大值 | 均值 |")
    parts.append("| --- | --- | --- | --- | --- |")
    for r in matrix_results:
        m = r.get('matrix')
        if m is not None:
            try:
                parts.append(f"| {r['method']} | {r['shape']} | "
                             f"{np.min(m):.4g} | {np.max(m):.4g} | {np.mean(m):.4g} |")
            except Exception:
                parts.append(f"| {r['method']} | {r.get('shape','-')} | - | - | - |")
        else:
            parts.append(f"| {r['method']} | - | - | - | - |")
    parts.append("")

    if viz_img:
        parts.append("### 可视化图")
        parts.append("")
        parts.append(f"![矩阵可视化]({viz_img})")
        parts.append("")

    parts.append("### 自动分析")
    parts.append("")
    parts.append(_matrix_analysis(matrix_results))
    parts.append("")
    return "\n".join(parts)


def _matrix_analysis(matrix_results):
    valid = [r for r in matrix_results if r.get('matrix') is not None]
    if not valid:
        return "本次未得到有效矩阵结果。"
    lines = [f"本次共完成 {len(valid)} 种矩阵转换方法。"]
    for r in valid:
        m = r['matrix']
        try:
            lines.append(f"- **{r['method']}**：形状 {r['shape']}，"
                         f"数值范围 [{np.min(m):.4g}, {np.max(m):.4g}]，均值 {np.mean(m):.4g}。")
        except Exception:
            pass
    lines.append("各矩阵从不同角度刻画了信号的时频/统计特征，可结合可视化图进一步解读。")
    return "\n".join(lines)


def save_figure_to_file(canvas, fpath, prefix=None):
    """保存canvas或figure当前图像到文件，返回文件路径"""
    if prefix is not None:
        save_dir = fpath
        os.makedirs(save_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d%H%M%S%f')
        fname = f"{prefix}_{ts}.png"
        fpath = os.path.join(save_dir, fname)
    else:
        save_dir = os.path.dirname(fpath)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
    
    try:
        if hasattr(canvas, 'fig'):
            fig = canvas.fig
        else:
            fig = canvas
        fig.savefig(fpath, dpi=120, bbox_inches='tight')
        return fpath
    except Exception as e:
        import traceback
        print(f"[ERROR] save_figure_to_file失败: {e}")
        print(f"[ERROR] 堆栈跟踪:\n{traceback.format_exc()}")
        return None
