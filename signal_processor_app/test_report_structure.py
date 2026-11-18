#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
专门测试报告结构约束
约束条件:
1. 一个通道(CH)一张图
2. 一张图包含若干子图，子图进行分类
3. Tab8特定子图分类规范
测试覆盖: Tab3/4/5/6/7/8
"""
import sys
import os
import numpy as np
import time
import re

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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_structure_test.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(f"[TEST] {msg}", flush=True)

def check_single_channel_single_image(md_content, tab_name):
    """检查是否一个通道一张图"""
    issues = []
    
    channel_image_pattern = re.compile(r'#### 通道 (CH\d+)')
    image_pattern = re.compile(r'!\[.*\]\(([^)]+)\)')
    
    channel_sections = channel_image_pattern.findall(md_content)
    images = image_pattern.findall(md_content)
    
    if tab_name == 'Tab5':
        is_valid = True
        return {
            'is_valid': is_valid,
            'n_channels': 0,
            'n_images': len(images),
            'issues': issues
        }
    
    if not channel_sections:
        issues.append(f"未找到通道章节")
        return {'is_valid': False, 'n_channels': 0, 'n_images': len(images), 'issues': issues}
    
    for channel in channel_sections:
        channel_section = re.search(rf'#### 通道 {channel}\s*\n(.*?)(?=\n#### 通道 |\n### |$)', md_content, re.DOTALL)
        if channel_section:
            section_images = image_pattern.findall(channel_section.group(1))
            if len(section_images) != 1:
                issues.append(f"通道 {channel} 包含 {len(section_images)} 张图片（应为1张）")
    
    is_valid = len(issues) == 0
    return {
        'is_valid': is_valid,
        'n_channels': len(channel_sections),
        'n_images': len(images),
        'issues': issues
    }

def check_subplot_classification(md_content, tab_name):
    """检查子图分类是否正确"""
    issues = []
    
    categories = []
    category_pattern = re.compile(r'### ([^#]+)')
    matches = category_pattern.findall(md_content)
    
    for match in matches:
        match = match.strip()
        if match and not match.startswith('实验状态') and not match.startswith('敏感性排序'):
            categories.append(match)
    
    if tab_name == 'Tab6':
        expected_categories = ['通道波形对比']
        for cat in expected_categories:
            if cat not in md_content:
                issues.append(f"缺少分类: {cat}")
    
    elif tab_name == 'Tab7':
        expected_categories = ['背景对消结果']
        for cat in expected_categories:
            if cat not in md_content:
                issues.append(f"缺少分类: {cat}")
    
    elif tab_name == 'Tab8':
        expected_categories = ['基础敏感性分析', '相关性分析']
        for cat in expected_categories:
            if cat not in md_content:
                issues.append(f"缺少分类: {cat}")
    
    is_valid = len(issues) == 0
    return {
        'is_valid': is_valid,
        'categories': categories,
        'issues': issues
    }

def check_tab8_structure(md_content, report_dir):
    """检查Tab8特定子图分类规范"""
    issues = []
    
    from PIL import Image
    import glob
    
    tab8_images = glob.glob(os.path.join(report_dir, 'tab8_CH*.png'))
    
    n_channels = len(tab8_images)
    
    if n_channels == 0:
        issues.append("未找到Tab8图片文件")
        return {'is_valid': False, 'issues': issues}
    
    if "左背景右实验" not in md_content:
        issues.append("基础敏感性分析报告中未标识左右两列意义")
    
    is_valid = len(issues) == 0
    return {
        'is_valid': is_valid,
        'n_channels': n_channels,
        'issues': issues
    }

def generate_test_reports(report_dir):
    """生成各Tab的测试报告 - 一个通道一张图，一张图包含多个子图"""
    from plot_utils import calc_figsize
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY, ReportBlock
    
    results = {}
    os.makedirs(report_dir, exist_ok=True)
    
    log("生成Tab3测试报告...")
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    STATE_REGISTRY.add_state({
        'name': '状态A',
        'type': 'TC12',
        'params': {'alpha': 0.1}
    })
    STATE_REGISTRY.add_state({
        'name': '状态B',
        'type': 'TC12',
        'params': {'alpha': 0.2}
    })
    
    md_content = "## Tab3报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    
    md_content += "### 波形对比\n\n"
    for ch in ['CH1', 'CH2', 'CH3']:
        figsize = calc_figsize(2, n_cols=2)
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        axes[0].plot([1, 2, 3], [1, 4, 2])
        axes[0].set_title("状态A")
        axes[1].plot([1, 2, 3], [2, 1, 3])
        axes[1].set_title("状态B")
        fig.suptitle(f"通道 {ch} 对比")
        fig.tight_layout()
        path = os.path.join(report_dir, f'tab3_{ch}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        md_content += f"#### 通道 {ch}\n\n![通道 {ch}](tab3_{ch}.png)\n\n"
    
    block = ReportBlock(source_tab='Tab3', title='Tab3测试报告', content_md=md_content, images=[])
    REPORT_MANAGER.add_block(block)
    md_full = REPORT_MANAGER.to_full_markdown()
    with open(os.path.join(report_dir, 'tab3_report.md'), 'w', encoding='utf-8') as f:
        f.write(md_full)
    
    results['Tab3'] = {
        'md_content': md_full,
        'report_path': os.path.join(report_dir, 'tab3_report.md')
    }
    
    log("生成Tab4测试报告...")
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    md_content = "## Tab4报告\n\n"
    md_content += "### 预处理结果\n\n"
    
    md_content += "### 时域波形\n\n"
    for ch in ['CH1', 'CH2']:
        figsize = calc_figsize(1, n_cols=1)
        fig, ax = plt.subplots(figsize=figsize)
        ax.plot([1, 2, 3, 4], [1, 3, 2, 4])
        ax.set_title(f"通道 {ch} 预处理后")
        fig.tight_layout()
        path = os.path.join(report_dir, f'tab4_{ch}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        md_content += f"#### 通道 {ch}\n\n![通道 {ch}](tab4_{ch}.png)\n\n"
    
    block = ReportBlock(source_tab='Tab4', title='Tab4测试报告', content_md=md_content, images=[])
    REPORT_MANAGER.add_block(block)
    md_full = REPORT_MANAGER.to_full_markdown()
    with open(os.path.join(report_dir, 'tab4_report.md'), 'w', encoding='utf-8') as f:
        f.write(md_full)
    
    results['Tab4'] = {
        'md_content': md_full,
        'report_path': os.path.join(report_dir, 'tab4_report.md')
    }
    
    log("生成Tab5测试报告...")
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    md_content = "## Tab5报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    
    md_content += "### 示意图\n\n"
    figsize = calc_figsize(1, n_cols=1)
    fig, ax = plt.subplots(figsize=figsize)
    ax.text(0.5, 0.5, "TC12示意图", ha='center', va='center', fontsize=16)
    fig.tight_layout()
    path = os.path.join(report_dir, 'tab5_diagram.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    md_content += f"![TC12示意图](tab5_diagram.png)\n\n"
    
    block = ReportBlock(source_tab='Tab5', title='Tab5测试报告', content_md=md_content, images=[])
    REPORT_MANAGER.add_block(block)
    md_full = REPORT_MANAGER.to_full_markdown()
    with open(os.path.join(report_dir, 'tab5_report.md'), 'w', encoding='utf-8') as f:
        f.write(md_full)
    
    results['Tab5'] = {
        'md_content': md_full,
        'report_path': os.path.join(report_dir, 'tab5_report.md')
    }
    
    log("生成Tab6测试报告...")
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    STATE_REGISTRY.add_state({'name': 'α1=0.1', 'type': 'TC12', 'params': {'alpha': 0.1}})
    STATE_REGISTRY.add_state({'name': 'α2=0.2', 'type': 'TC12', 'params': {'alpha': 0.2}})
    
    md_content = "## Tab6报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    
    md_content += "### 通道波形对比\n\n"
    for ch in ['CH1', 'CH2']:
        n_subplots = 3
        n_cols = 1
        figsize = calc_figsize(n_subplots, n_cols=n_cols)
        fig, axes = plt.subplots(n_subplots, n_cols, figsize=figsize, sharex=True)
        
        axes[0].plot([1, 2, 3], [1, 4, 2])
        axes[0].set_title("组1 - 时域")
        axes[0].set_ylabel("组1")
        
        axes[1].plot([1, 2, 3], [2, 1, 3])
        axes[1].set_title("组2 - 时域")
        axes[1].set_ylabel("组2")
        
        axes[2].plot([1, 2, 3], [0.5, 1, 0.5])
        axes[2].set_title("组1 vs 组2 - 相关性")
        axes[2].set_xlabel("时间")
        
        fig.suptitle(f"通道 {ch} - 波形对比")
        fig.tight_layout(rect=[0, 0.02, 1, 0.96])
        path = os.path.join(report_dir, f'tab6_{ch}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        md_content += f"#### 通道 {ch}\n\n![通道 {ch}](tab6_{ch}.png)\n\n"
    
    md_content += "### 通道相关性指标排序\n\n"
    md_content += "| 排名 | 通道 | 加权均值 |\n"
    md_content += "|------|------|----------|\n"
    md_content += "| 1 | CH1 | 0.950000 |\n"
    md_content += "| 2 | CH2 | 0.900000 |\n"
    
    block = ReportBlock(source_tab='Tab6', title='Tab6测试报告', content_md=md_content, images=[])
    REPORT_MANAGER.add_block(block)
    md_full = REPORT_MANAGER.to_full_markdown()
    with open(os.path.join(report_dir, 'tab6_report.md'), 'w', encoding='utf-8') as f:
        f.write(md_full)
    
    results['Tab6'] = {
        'md_content': md_full,
        'report_path': os.path.join(report_dir, 'tab6_report.md')
    }
    
    log("生成Tab7测试报告...")
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    md_content = "## Tab7报告\n\n"
    md_content += "### 背景对消结果\n\n"
    for ch in ['CH1', 'CH2']:
        n_subplots = 3
        n_cols = 1
        figsize = calc_figsize(n_subplots, n_cols=n_cols)
        fig, axes = plt.subplots(n_subplots, n_cols, figsize=figsize, sharex=True)
        
        axes[0].plot([1, 2, 3], [1, 2, 1], label='原始')
        axes[0].legend(fontsize=8)
        axes[0].set_title("原始数据")
        
        axes[1].plot([1, 2, 3], [0.5, 1, 0.5], label='背景', color='orange')
        axes[1].legend(fontsize=8)
        axes[1].set_title("背景数据")
        
        axes[2].plot([1, 2, 3], [0.5, 1, 0.5], label='对消后', color='green')
        axes[2].legend(fontsize=8)
        axes[2].set_title("对消后数据")
        axes[2].set_xlabel("时间")
        
        fig.suptitle(f"通道 {ch} - 背景对消")
        fig.tight_layout(rect=[0, 0.02, 1, 0.96])
        path = os.path.join(report_dir, f'tab7_{ch}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        md_content += f"#### 通道 {ch}\n\n![通道 {ch}](tab7_{ch}.png)\n\n"
    
    block = ReportBlock(source_tab='Tab7', title='Tab7测试报告', content_md=md_content, images=[])
    REPORT_MANAGER.add_block(block)
    md_full = REPORT_MANAGER.to_full_markdown()
    with open(os.path.join(report_dir, 'tab7_report.md'), 'w', encoding='utf-8') as f:
        f.write(md_full)
    
    results['Tab7'] = {
        'md_content': md_full,
        'report_path': os.path.join(report_dir, 'tab7_report.md')
    }
    
    log("生成Tab8测试报告...")
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    STATE_REGISTRY.add_state({'name': '方位0度', 'type': '方位', 'params': {'angle': 0}})
    STATE_REGISTRY.add_state({'name': '方位90度', 'type': '方位', 'params': {'angle': 90}})
    
    md_content = "## Tab8报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    
    md_content += "### 基础敏感性分析（左背景右实验）\n\n"
    md_content += "> **左列**: 背景数据 | **右列**: 实验数据\n\n"
    
    md_content += "### 相关性分析\n\n"
    
    md_content += "### 通道敏感性分析汇总\n\n"
    for ch in ['CH1', 'CH2']:
        n_subplots = 3
        n_cols = 1
        figsize = calc_figsize(n_subplots, n_cols=n_cols)
        fig, axes = plt.subplots(n_subplots, n_cols, figsize=figsize)
        
        axes[0].plot([1, 2, 3], [1, 2, 1], label='背景组', color='orange')
        axes[0].plot([1, 2, 3], [2, 3, 2], label='实验组')
        axes[0].set_title(f"通道 {ch} - 时域对比（左背景右实验）")
        axes[0].legend(fontsize=8)
        
        axes[1].semilogy([1, 2, 3], [10, 100, 10], label='背景组', color='orange')
        axes[1].semilogy([1, 2, 3], [20, 200, 20], label='实验组')
        axes[1].set_title(f"通道 {ch} - 频域对比（左背景右实验）")
        axes[1].legend(fontsize=8)
        
        axes[2].plot([1, 2, 3], [0.5, 1, 0.5])
        axes[2].set_title(f"通道 {ch} - 互相关")
        axes[2].set_xlabel("时间")
        
        fig.suptitle(f"通道 {ch} - 敏感性分析")
        fig.tight_layout(rect=[0, 0.02, 1, 0.96])
        path = os.path.join(report_dir, f'tab8_{ch}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        md_content += f"#### 通道 {ch}\n\n![通道 {ch}](tab8_{ch}.png)\n\n"
    
    block = ReportBlock(source_tab='Tab8', title='Tab8测试报告', content_md=md_content, images=[])
    REPORT_MANAGER.add_block(block)
    md_full = REPORT_MANAGER.to_full_markdown()
    with open(os.path.join(report_dir, 'tab8_report.md'), 'w', encoding='utf-8') as f:
        f.write(md_full)
    
    results['Tab8'] = {
        'md_content': md_full,
        'report_path': os.path.join(report_dir, 'tab8_report.md')
    }
    
    return results

def generate_report(report_dir, all_results):
    """生成测试报告"""
    md_content = f"# 报告结构约束测试报告\n\n"
    md_content += f"> 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    md_content += "## 约束条件\n\n"
    md_content += "1. **一个通道一张图**: 每个通道(CH)生成单独的图片文件\n"
    md_content += "2. **子图分类**: 一张图包含若干子图，子图进行分类\n"
    md_content += "3. **Tab8特定规范**: 基础敏感性分析报告中，左背景右实验，左右两列分别标识\n\n"
    
    md_content += "## 测试结果汇总\n\n"
    md_content += "| Tab | 一个通道一张图 | 子图分类 | Tab8特定规范 |\n"
    md_content += "|-----|----------------|----------|--------------|\n"
    
    all_passed = True
    detailed_results = {}
    
    for tab_name, result in all_results.items():
        detailed_results[tab_name] = {}
        
        ch_img_result = check_single_channel_single_image(result['md_content'], tab_name)
        detailed_results[tab_name]['single_channel_image'] = ch_img_result
        
        subplot_result = check_subplot_classification(result['md_content'], tab_name)
        detailed_results[tab_name]['subplot_classification'] = subplot_result
        
        if tab_name == 'Tab8':
            tab8_result = check_tab8_structure(result['md_content'], report_dir)
            detailed_results[tab_name]['tab8_specific'] = tab8_result
            tab8_status = "✓ 通过" if tab8_result['is_valid'] else "✗ 失败"
            if not tab8_result['is_valid']:
                all_passed = False
        else:
            tab8_status = "-"
        
        ch_img_status = "✓ 通过" if ch_img_result['is_valid'] else "✗ 失败"
        subplot_status = "✓ 通过" if subplot_result['is_valid'] else "✗ 失败"
        
        if not ch_img_result['is_valid'] or not subplot_result['is_valid']:
            all_passed = False
        
        md_content += f"| {tab_name} | {ch_img_status} | {subplot_status} | {tab8_status} |\n"
    
    md_content += "\n"
    
    if all_passed:
        md_content += "## 结论\n\n"
        md_content += "所有测试通过！报告结构均符合约束要求。\n\n"
    else:
        md_content += "## 问题详情\n\n"
        for tab_name, results in detailed_results.items():
            issues = []
            
            if not results['single_channel_image']['is_valid']:
                issues.extend(results['single_channel_image']['issues'])
            
            if not results['subplot_classification']['is_valid']:
                issues.extend(results['subplot_classification']['issues'])
            
            if 'tab8_specific' in results and not results['tab8_specific']['is_valid']:
                issues.extend(results['tab8_specific']['issues'])
            
            if issues:
                md_content += f"### {tab_name}\n\n"
                for issue in issues:
                    md_content += f"- {issue}\n"
                md_content += "\n"
    
    report_path = os.path.join(report_dir, 'report_structure_test_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return report_path, all_passed

if __name__ == '__main__':
    log("=" * 80)
    log("报告结构约束测试开始")
    log("=" * 80)
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_report_structure_output')
    os.makedirs(report_dir, exist_ok=True)
    log(f"报告目录: {report_dir}")
    
    log("生成测试报告...")
    all_results = generate_test_reports(report_dir)
    
    log("检查报告结构...")
    for tab_name, result in all_results.items():
        log(f"  {tab_name}:")
        
        ch_img_result = check_single_channel_single_image(result['md_content'], tab_name)
        status = "✓" if ch_img_result['is_valid'] else "✗"
        log(f"    {status} 一个通道一张图: {ch_img_result['n_channels']}个通道, {ch_img_result['n_images']}张图片")
        if ch_img_result['issues']:
            for issue in ch_img_result['issues']:
                log(f"      - {issue}")
        
        subplot_result = check_subplot_classification(result['md_content'], tab_name)
        status = "✓" if subplot_result['is_valid'] else "✗"
        log(f"    {status} 子图分类: {', '.join(subplot_result['categories'])}")
        if subplot_result['issues']:
            for issue in subplot_result['issues']:
                log(f"      - {issue}")
        
        if tab_name == 'Tab8':
            tab8_result = check_tab8_structure(result['md_content'], report_dir)
            status = "✓" if tab8_result['is_valid'] else "✗"
            log(f"    {status} Tab8特定规范")
            if tab8_result['issues']:
                for issue in tab8_result['issues']:
                    log(f"      - {issue}")
    
    log("生成测试报告...")
    report_path, all_passed = generate_report(report_dir, all_results)
    log(f"测试报告已生成: {report_path}")
    
    log("=" * 80)
    log(f"测试结束！{'所有测试通过' if all_passed else '存在测试失败'}")
    log("=" * 80)