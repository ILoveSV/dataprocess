#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
专门测试报告中图片比例约束
约束条件:
1. 每张子图的长度与高度之比（宽高比）≤ 3.3
2. 子图的高度与图中文字高度之比 ≤ 7.5
测试覆盖: Tab3/4/5/6/7/8
"""
import sys
import os
import numpy as np
import time

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

font_path = 'C:/Windows/Fonts/simhei.ttf'
if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    font_prop = fm.FontProperties(fname=font_path)
    font_name = font_prop.get_name()
    plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
else:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image_ratio_test.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(f"[TEST] {msg}", flush=True)

def check_figsize_ratio(figsize, n_subplots, n_cols=1, text_height=10):
    """直接验证figsize是否符合比例约束
    
    返回: (is_valid, subplot_aspect_ratio, height_text_ratio, issues)
    """
    issues = []
    max_aspect_ratio = 3.3
    max_height_ratio = 7.5
    
    width, height = figsize
    n_rows = (n_subplots + n_cols - 1) // n_cols
    
    subplot_width = width / n_cols
    subplot_height = height / n_rows
    
    subplot_aspect_ratio = subplot_width / subplot_height
    
    text_height_inch = text_height / 72.0
    height_text_ratio = subplot_height / text_height_inch
    
    if subplot_aspect_ratio > max_aspect_ratio:
        issues.append(f"子图宽高比 {subplot_aspect_ratio:.2f} > {max_aspect_ratio}")
    
    if height_text_ratio > max_height_ratio:
        issues.append(f"子图高/文字高比 {height_text_ratio:.2f} > {max_height_ratio}")
    
    is_valid = len(issues) == 0
    
    return {
        'is_valid': is_valid,
        'figsize': figsize,
        'n_subplots': n_subplots,
        'n_cols': n_cols,
        'n_rows': n_rows,
        'subplot_width': subplot_width,
        'subplot_height': subplot_height,
        'subplot_aspect_ratio': subplot_aspect_ratio,
        'height_text_ratio': height_text_ratio,
        'issues': issues
    }

def generate_test_images(report_dir):
    """生成各Tab的测试图片"""
    from plot_utils import calc_figsize
    
    results = {}
    
    os.makedirs(report_dir, exist_ok=True)
    
    log("生成Tab3测试图片...")
    tab3_images = []
    
    figsize = calc_figsize(2, n_cols=2)
    result = check_figsize_ratio(figsize, 2, n_cols=2)
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    axes[0].plot([1, 2, 3], [1, 4, 2])
    axes[0].set_title("状态A")
    axes[1].plot([1, 2, 3], [2, 1, 3])
    axes[1].set_title("状态B")
    fig.tight_layout()
    path = os.path.join(report_dir, 'tab3_compare.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab3_images.append(result)
    
    results['Tab3'] = tab3_images
    
    log("生成Tab4测试图片...")
    tab4_images = []
    
    figsize = calc_figsize(1, n_cols=1)
    result = check_figsize_ratio(figsize, 1, n_cols=1)
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot([1, 2, 3, 4], [1, 3, 2, 4])
    ax.set_title("预处理后波形")
    fig.tight_layout()
    path = os.path.join(report_dir, 'tab4_waveform.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab4_images.append(result)
    
    results['Tab4'] = tab4_images
    
    log("生成Tab5测试图片...")
    tab5_images = []
    
    figsize = calc_figsize(1, n_cols=1)
    result = check_figsize_ratio(figsize, 1, n_cols=1)
    fig, ax = plt.subplots(figsize=figsize)
    ax.text(0.5, 0.5, "TC12示意图", ha='center', va='center', fontsize=16)
    fig.tight_layout()
    path = os.path.join(report_dir, 'tab5_diagram.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab5_images.append(result)
    
    results['Tab5'] = tab5_images
    
    log("生成Tab6测试图片...")
    tab6_images = []
    
    figsize = calc_figsize(4, n_cols=1)
    result = check_figsize_ratio(figsize, 4, n_cols=1)
    fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [i+1, i+2, i+1])
        ax.set_ylabel(f"组{i+1}")
    axes[-1].set_xlabel("时间")
    fig.suptitle("Tab6时域对比")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    path = os.path.join(report_dir, 'tab6_time.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab6_images.append(result)
    
    figsize = calc_figsize(4, n_cols=1)
    result = check_figsize_ratio(figsize, 4, n_cols=1)
    fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
    for i, ax in enumerate(axes):
        ax.semilogy([1, 2, 3], [10**(i+1), 10**(i+2), 10**(i+1)])
        ax.set_ylabel(f"组{i+1}")
    axes[-1].set_xlabel("频率")
    fig.suptitle("Tab6频域对比")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    path = os.path.join(report_dir, 'tab6_freq.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab6_images.append(result)
    
    figsize = calc_figsize(6, n_cols=2)
    result = check_figsize_ratio(figsize, 6, n_cols=2)
    fig, axes = plt.subplots(3, 2, figsize=figsize)
    axes = axes.flatten()
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [1, 2, 1])
        ax.set_title(f"组{i//2+1} vs 组{i//2+2}")
    fig.suptitle("Tab6相关性对比")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    path = os.path.join(report_dir, 'tab6_corr.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab6_images.append(result)
    
    results['Tab6'] = tab6_images
    
    log("生成Tab7测试图片...")
    tab7_images = []
    
    figsize = calc_figsize(3, n_cols=1)
    result = check_figsize_ratio(figsize, 3, n_cols=1)
    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)
    axes[0].plot([1, 2, 3], [1, 2, 1], label='原始')
    axes[0].legend()
    axes[1].plot([1, 2, 3], [0.5, 1, 0.5], label='背景', color='orange')
    axes[1].legend()
    axes[2].plot([1, 2, 3], [0.5, 1, 0.5], label='对消后', color='green')
    axes[2].legend()
    fig.suptitle("Tab7背景对消")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    path = os.path.join(report_dir, 'tab7_bg_sub.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab7_images.append(result)
    
    results['Tab7'] = tab7_images
    
    log("生成Tab8测试图片...")
    tab8_images = []
    
    figsize = calc_figsize(2, n_cols=2)
    result = check_figsize_ratio(figsize, 2, n_cols=2)
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    axes[0].plot([1, 2, 3], [1, 2, 1], label='背景组', color='orange')
    axes[0].set_title("背景组")
    axes[0].legend()
    axes[1].plot([1, 2, 3], [2, 3, 2], label='实验组')
    axes[1].set_title("实验组")
    axes[1].legend()
    fig.suptitle("Tab8时域对比")
    fig.tight_layout()
    path = os.path.join(report_dir, 'tab8_time.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab8_images.append(result)
    
    figsize = calc_figsize(2, n_cols=2)
    result = check_figsize_ratio(figsize, 2, n_cols=2)
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    axes[0].semilogy([1, 2, 3], [10, 100, 10], label='背景组', color='orange')
    axes[0].set_title("背景组频谱")
    axes[0].legend()
    axes[1].semilogy([1, 2, 3], [20, 200, 20], label='实验组')
    axes[1].set_title("实验组频谱")
    axes[1].legend()
    fig.suptitle("Tab8频域对比")
    fig.tight_layout()
    path = os.path.join(report_dir, 'tab8_freq.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab8_images.append(result)
    
    figsize = calc_figsize(4, n_cols=1)
    result = check_figsize_ratio(figsize, 4, n_cols=1)
    fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [0.5, 1, 0.5])
        ax.set_ylabel(f"CH{i+1}")
    axes[-1].set_xlabel("时间延迟")
    fig.suptitle("Tab8相关性分析")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    path = os.path.join(report_dir, 'tab8_corr.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    result['path'] = path
    tab8_images.append(result)
    
    results['Tab8'] = tab8_images
    
    return results

def generate_report(report_dir, all_results):
    """生成测试报告"""
    md_content = f"# 图片比例约束测试报告\n\n"
    md_content += f"> 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    md_content += "## 约束条件\n\n"
    md_content += "1. **子图宽高比约束**: 每张子图的长度与高度之比 ≤ 3.3\n"
    md_content += "2. **子图高与文字高比约束**: 子图的高度与图中文字高度之比 ≤ 7.5\n\n"
    
    md_content += "## 测试结果汇总\n\n"
    md_content += "| Tab | 图片文件 | figsize | 子图数 | 子图宽高比 | 子图高/文字高 | 结果 |\n"
    md_content += "|-----|----------|---------|--------|------------|---------------|------|\n"
    
    all_passed = True
    detailed_results = {}
    
    for tab_name, image_results in all_results.items():
        detailed_results[tab_name] = []
        for result in image_results:
            if not result['is_valid']:
                all_passed = False
            
            status = "✓ 通过" if result['is_valid'] else "✗ 失败"
            
            md_content += f"| {tab_name} | {os.path.basename(result['path'])} | "
            md_content += f"{result['figsize']} | "
            md_content += f"{result['n_subplots']} | "
            md_content += f"{result['subplot_aspect_ratio']:.2f} | "
            md_content += f"{result['height_text_ratio']:.2f} | {status} |\n"
            
            detailed_results[tab_name].append(result)
    
    md_content += "\n"
    
    if all_passed:
        md_content += "## 结论\n\n"
        md_content += "所有测试通过！报告中的图片比例均符合约束要求。\n\n"
    else:
        md_content += "## 问题详情\n\n"
        for tab_name, results in detailed_results.items():
            failed = [r for r in results if not r['is_valid']]
            if failed:
                md_content += f"### {tab_name}\n\n"
                for result in failed:
                    md_content += f"**文件**: {os.path.basename(result['path'])}\n\n"
                    md_content += f"- figsize: {result['figsize']}\n"
                    md_content += f"- 子图数: {result['n_subplots']}\n"
                    md_content += f"- 子图宽高比: {result['subplot_aspect_ratio']:.2f} (上限: 3.3)\n"
                    md_content += f"- 子图高/文字高: {result['height_text_ratio']:.2f} (上限: 7.5)\n"
                    if result['issues']:
                        md_content += "- 问题:\n"
                        for issue in result['issues']:
                            md_content += f"  - {issue}\n"
                    md_content += "\n"
    
    md_content += "## 详细参数\n\n"
    md_content += "### calc_figsize 函数参数\n\n"
    md_content += "| 参数 | 值 | 说明 |\n"
    md_content += "|------|-----|------|\n"
    md_content += "| max_aspect_ratio | 3.3 | 子图宽高比上限 |\n"
    md_content += "| max_height_ratio | 7.5 | 子图高与文字高比上限 |\n"
    md_content += "| text_height | 10 | 文字高度（磅） |\n"
    md_content += "| text_height_inch | 0.1389 | 文字高度（英寸） |\n"
    md_content += "\n"
    
    report_path = os.path.join(report_dir, 'image_ratio_test_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return report_path, all_passed

if __name__ == '__main__':
    log("=" * 80)
    log("图片比例约束测试开始")
    log("=" * 80)
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_image_ratio_output')
    os.makedirs(report_dir, exist_ok=True)
    log(f"报告目录: {report_dir}")
    
    log("生成测试图片并检查比例...")
    all_results = generate_test_images(report_dir)
    
    for tab_name, results in all_results.items():
        log(f"  {tab_name}:")
        for r in results:
            status = "✓" if r['is_valid'] else "✗"
            log(f"    {status} {os.path.basename(r['path'])}: figsize={r['figsize']}, 宽高比={r['subplot_aspect_ratio']:.2f}, 子图高/文字高={r['height_text_ratio']:.2f}")
    
    log("生成测试报告...")
    report_path, all_passed = generate_report(report_dir, all_results)
    log(f"测试报告已生成: {report_path}")
    
    log("=" * 80)
    log(f"测试结束！{'所有测试通过' if all_passed else '存在测试失败'}")
    log("=" * 80)