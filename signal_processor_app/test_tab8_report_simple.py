#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用模拟数据生成Tab8报告，供用户验证修改效果
"""
import sys
import os
import numpy as np

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

def generate_time_domain_plot(output_dir):
    """生成时域对比图"""
    print("生成时域对比图...")
    
    n_channels = 8
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 2.2
    fig_width = 16.0
    if fig_height > 24:
        fig_height = 24
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
    
    channels = [f'CH{i+1}' for i in range(n_channels)]
    start_time = 8.5
    end_time = 8.55
    
    for i in range(n_rows):
        for j in range(n_cols):
            ax = fig.add_subplot(gs[i, j])
            if j == 0:
                data = np.random.rand(500) * 0.05 + 5.0
                title = f"背景组 {channels[i]}"
                ax.plot(np.linspace(start_time, end_time, 500), data, linewidth=1.0, color='#FF9800')
            else:
                data = np.random.rand(500) * 0.05 + 5.0
                title = f"实验组 {channels[i]}"
                ax.plot(np.linspace(start_time, end_time, 500), data, linewidth=1.0, color='#2196F3')
            
            ax.set_title(title, fontsize=10, fontweight='bold', pad=12)
            ax.set_xlabel("时间(s)", fontsize=8, labelpad=8)
            ax.set_ylabel("信号值", fontsize=8, labelpad=8)
            ax.tick_params(axis='both', labelsize=7, pad=6)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_facecolor('#f8f9fa')
    
    fig.suptitle(f"时域对比（第二时间切片: {start_time:.3f}s - {end_time:.3f}s）", fontsize=14, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
    
    path = os.path.join(output_dir, "basic_time_viz.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已保存: {path}")

def generate_freq_domain_plot(output_dir):
    """生成频域对比图"""
    print("生成频域对比图...")
    
    n_channels = 8
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 2.2
    fig_width = 16.0
    if fig_height > 24:
        fig_height = 24
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
    
    channels = [f'CH{i+1}' for i in range(n_channels)]
    fs = 400000
    
    for i in range(n_rows):
        for j in range(n_cols):
            ax = fig.add_subplot(gs[i, j])
            f = np.linspace(0, fs/2, 500)
            if j == 0:
                data = np.random.rand(500) * 1e-10 + 1e-12
                title = f"背景组 {channels[i]}"
                ax.semilogy(f, data, linewidth=1.0, color='#FF9800')
            else:
                data = np.random.rand(500) * 1e-10 + 1e-12
                title = f"实验组 {channels[i]}"
                ax.semilogy(f, data, linewidth=1.0, color='#2196F3')
            
            ax.set_title(title, fontsize=10, fontweight='bold', pad=12)
            ax.set_xlabel("频率(Hz)", fontsize=8, labelpad=8)
            ax.set_ylabel("功率谱密度", fontsize=8, labelpad=8)
            ax.tick_params(axis='both', labelsize=7, pad=6)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_xlim(0, fs/2)
            ax.set_facecolor('#f8f9fa')
    
    fig.suptitle("频域对比", fontsize=14, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
    
    path = os.path.join(output_dir, "basic_freq_viz.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已保存: {path}")

def generate_time_correlation_plot(output_dir):
    """生成时域相关性图"""
    print("生成时域相关性图...")
    
    channels = ['CH10', 'CH2', 'CH3', 'CH4', 'CH12', 'CH7', 'CH5', 'CH1']
    n_channels = len(channels)
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 1.6
    fig_width = 16.0
    if fig_height > 20:
        fig_height = 20
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.5, wspace=0.4)
    
    idx = 0
    for i in range(n_rows):
        for j in range(n_cols):
            if idx >= n_channels:
                break
            ax = fig.add_subplot(gs[i, j])
            
            ch_name = channels[idx]
            kb = np.random.uniform(-0.01, 0.01)
            ka = np.random.uniform(0, 0.001)
            
            data_a = np.random.rand(500) * 0.05 + 5.0
            data_b = data_a * 0.95 + np.random.rand(500) * 0.02
            
            ax.scatter(data_a, data_b, s=3, alpha=0.4, color='#2196F3')
            ax.set_title(f"{ch_name}", fontsize=10, fontweight='bold', pad=12)
            ax.set_xlabel('实验组', fontsize=8, labelpad=8)
            ax.set_ylabel('背景组', fontsize=8, labelpad=8)
            ax.tick_params(axis='both', labelsize=7, pad=6)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_facecolor('#f8f9fa')
            ax.text(0.05, 0.92, f"Kb={kb:.4f}, Ka={ka:.4f}", 
                    transform=ax.transAxes, 
                    ha='left', va='top', fontsize=7,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
            
            idx += 1
    
    fig.suptitle("时域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.06, right=0.98, hspace=0.5, wspace=0.4)
    
    path = os.path.join(output_dir, "basic_time_corr.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已保存: {path}")

def generate_freq_correlation_plot(output_dir):
    """生成频域相关性图"""
    print("生成频域相关性图...")
    
    channels = ['CH10', 'CH2', 'CH3', 'CH4', 'CH12', 'CH7', 'CH5', 'CH1']
    n_channels = len(channels)
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 1.6
    fig_width = 16.0
    if fig_height > 20:
        fig_height = 20
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.5, wspace=0.4)
    
    idx = 0
    for i in range(n_rows):
        for j in range(n_cols):
            if idx >= n_channels:
                break
            ax = fig.add_subplot(gs[i, j])
            
            ch_name = channels[idx]
            kb = np.random.uniform(-0.01, 0.01)
            ka = np.random.uniform(0, 0.001)
            
            data_a = np.random.rand(500) * 0.00001 + 0.000001
            data_b = data_a * 0.9 + np.random.rand(500) * 0.000002
            
            ax.scatter(data_a, data_b, s=3, alpha=0.4, color='#2196F3')
            ax.set_title(f"{ch_name}", fontsize=10, fontweight='bold', pad=12)
            ax.set_xlabel('实验组频谱', fontsize=8, labelpad=8)
            ax.set_ylabel('背景组频谱', fontsize=8, labelpad=8)
            ax.tick_params(axis='both', labelsize=7, pad=6)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_facecolor('#f8f9fa')
            ax.text(0.05, 0.92, f"Kb={kb:.4f}, Ka={ka:.4f}", 
                    transform=ax.transAxes, 
                    ha='left', va='top', fontsize=7,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
            
            idx += 1
    
    fig.suptitle("频域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.06, right=0.98, hspace=0.5, wspace=0.4)
    
    path = os.path.join(output_dir, "basic_freq_corr.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已保存: {path}")

def generate_report(output_dir):
    """生成完整报告"""
    print("\n生成Markdown报告...")
    
    md_content = f"## 基础响应敏感性分析报告\n\n"
    
    md_content += "### 1. 实验状态定义\n\n"
    md_content += "| 序号 | 状态名称 | 类型 | α或K | β或L | r |\n"
    md_content += "| --- | --- | --- | --- | --- | --- |\n"
    md_content += "| 1 | 状态A-放电 | TC12 | 30° | 45° | 1.5m |\n"
    md_content += "| 2 | 状态B-不放电 | TC12 | 30° | 45° | 1.5m |\n\n"
    
    md_content += "| 参数 | 值 |\n"
    md_content += "|------|----|\n"
    md_content += "| 采样率 | 400000 Hz |\n"
    md_content += "| 通道数 | 12 |\n"
    md_content += "| 时间切片 | 6.00s - 12.00s |\n"
    md_content += "| 相关性算法 | 皮尔逊相关系数 |\n\n"
    
    md_content += "### 2. 可视化结果\n\n"
    
    md_content += "#### 2.1 时域二次切片对比\n\n"
    md_content += "![时域对比](basic_time_viz.png)\n\n"
    md_content += "**说明**: 显示各通道背景组与实验组的时域信号对比。\n\n"
    
    md_content += "#### 2.2 频域对比\n\n"
    md_content += "![频域对比](basic_freq_viz.png)\n\n"
    md_content += "**说明**: 显示各通道背景组与实验组的频域频谱对比。\n\n"
    
    md_content += "#### 2.3 时域相关性\n\n"
    md_content += "![时域相关性](basic_time_corr.png)\n\n"
    md_content += "**说明**: 各通道实验组与背景组的时域散点图，按敏感性(Kb)降序排列。\n\n"
    
    md_content += "#### 2.4 频域相关性\n\n"
    md_content += "![频域相关性](basic_freq_corr.png)\n\n"
    md_content += "**说明**: 各通道实验组与背景组的频域散点图，按敏感性(Kb)降序排列。\n\n"
    
    md_content += "### 3. 敏感性排序\n\n"
    md_content += "> **敏感性判断**: 实验组与背景组越不相关(Kb越小)，通道越敏感。\n\n"
    md_content += "| 排名 | 通道 | Ka (频域峰值差) | Kb (相关性系数) |\n"
    md_content += "|------|------|----------------|----------------|\n"
    
    channels = ['CH10', 'CH2', 'CH3', 'CH4', 'CH12', 'CH7', 'CH5', 'CH1']
    for rank, ch in enumerate(channels, 1):
        ka = np.random.uniform(0, 0.001)
        kb = np.random.uniform(-0.01, 0.01)
        md_content += f"| {rank} | {ch} | {ka:.6f} | {kb:.6f} |\n"
    
    report_path = os.path.join(output_dir, "basic_response_sensitivity_report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"  已保存: {report_path}")
    return report_path

def main():
    """主函数"""
    print("=" * 60)
    print("生成Tab8通道敏感性分析报告")
    print("=" * 60)
    
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tab8_report_output')
    os.makedirs(output_dir, exist_ok=True)
    
    generate_time_domain_plot(output_dir)
    generate_freq_domain_plot(output_dir)
    generate_time_correlation_plot(output_dir)
    generate_freq_correlation_plot(output_dir)
    
    report_path = generate_report(output_dir)
    
    print(f"\n{'=' * 60}")
    print("报告生成完成！")
    print(f"报告目录: {output_dir}")
    print(f"报告文件: {report_path}")
    print(f"{'=' * 60}")
    
    files = os.listdir(output_dir)
    print("\n生成的文件:")
    for f in files:
        fpath = os.path.join(output_dir, f)
        size = os.path.getsize(fpath) / 1024
        print(f"  {f} - {size:.2f} KB")

if __name__ == '__main__':
    main()