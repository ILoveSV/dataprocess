#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试Tab6报告图片生成
"""
import sys
import os
import numpy as np

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

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

from plot_utils import calc_figsize

def test_tab6_figure():
    """测试Tab6报告图片生成"""
    print("=" * 60)
    print("测试Tab6报告图片生成")
    print("=" * 60)
    
    labels = ['KW1', 'KW2', 'KW3']
    channels = ['CH1', 'CH2', 'CH3']
    n_groups = len(labels)
    
    import itertools
    
    for ch_idx, channel_name in enumerate(channels):
        pairs = list(itertools.combinations(labels, 2))
        n_pairs = len(pairs)
        
        n_rows = n_groups + n_groups + n_pairs
        n_cols = 1
        
        print(f"\n通道 {channel_name}:")
        print(f"  子图数: {n_rows}")
        print(f"  数据组数: {n_groups}")
        print(f"  相关性对: {n_pairs}")
        
        fig_height = n_rows * 2.0
        fig_width = 10.0
        if fig_height > 20:
            fig_height = 20
        figsize = (fig_width, fig_height)
        print(f"  figsize: {figsize}")
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        row_idx = 0
        
        # 时域波形
        for i, group in enumerate(labels):
            data = np.random.rand(1000) * 2 - 1
            t = np.linspace(0, 1, len(data))
            axes[row_idx].plot(t, data, linewidth=1.0)
            axes[row_idx].set_title(f"时域 - {group}", fontsize=10)
            axes[row_idx].set_xlabel("时间(s)", fontsize=8)
            axes[row_idx].tick_params(axis='both', labelsize=8)
            axes[row_idx].grid(True, alpha=0.3)
            row_idx += 1
        
        # 频域波形
        for i, group in enumerate(labels):
            f = np.linspace(0, 500, 500)
            Pxx = np.random.rand(500) * 100 + 1
            axes[row_idx].semilogy(f, Pxx, linewidth=1.0)
            axes[row_idx].set_xlim(0, 500)
            axes[row_idx].set_title(f"频域 - {group}", fontsize=10)
            axes[row_idx].set_xlabel("频率(Hz)", fontsize=8)
            axes[row_idx].tick_params(axis='both', labelsize=8)
            axes[row_idx].grid(True, alpha=0.3)
            row_idx += 1
        
        # 相关性散点图（Tab8风格）
        for (label_a, label_b) in pairs:
            data_a = np.random.rand(500) * 2 - 1
            data_b = data_a * 0.8 + np.random.rand(500) * 0.2
            corr_value = 0.8
            
            axes[row_idx].scatter(data_a, data_b, s=2, alpha=0.4)
            axes[row_idx].set_title(f"{label_a} vs {label_b}", fontsize=10)
            axes[row_idx].set_xlabel(label_a, fontsize=8)
            axes[row_idx].set_ylabel(label_b, fontsize=8)
            axes[row_idx].tick_params(axis='both', labelsize=8)
            axes[row_idx].grid(True, alpha=0.3)
            axes[row_idx].text(0.05, 0.95, f"相关性系数: {corr_value:.4f}", 
                              transform=axes[row_idx].transAxes, 
                              ha='left', va='top', fontsize=8,
                              bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            row_idx += 1
        
        fig.suptitle(f"通道 {channel_name} - 综合分析", fontsize=12)
        fig.tight_layout(rect=[0.02, 0.02, 1, 0.96])
        
        report_dir = 'test_tab6_output'
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, f"batch_{channel_name}.png")
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  图片已保存: {path}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == '__main__':
    test_tab6_figure()