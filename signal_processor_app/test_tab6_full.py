#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试Tab6完整报告生成
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

def test_channel_composite():
    """测试通道综合分析图（包含时域、频域、相关性）"""
    print("=" * 60)
    print("测试通道综合分析图")
    print("=" * 60)
    
    labels = ['KW1', 'KW2', 'KW3']
    channels = [f'CH{i}' for i in range(1, 13)]
    n_groups = len(labels)
    
    import itertools
    
    for ch_idx, channel_name in enumerate(channels):
        pairs = list(itertools.combinations(labels, 2))
        n_pairs = len(pairs)
        
        n_rows = n_groups + n_groups + n_pairs + n_pairs
        n_cols = 1
        
        fig_height = n_rows * 1.8
        fig_width = 12.0
        if fig_height > 24:
            fig_height = 24
        figsize = (fig_width, fig_height)
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        row_idx = 0
        
        for i, group in enumerate(labels):
            data = np.random.rand(1000) * 2 - 1
            t = np.linspace(0, 1, len(data))
            axes[row_idx].plot(t, data, linewidth=1.0)
            axes[row_idx].set_title(f"时域 - {group}", fontsize=10)
            axes[row_idx].set_xlabel("时间(s)", fontsize=8)
            axes[row_idx].tick_params(axis='both', labelsize=8)
            axes[row_idx].grid(True, alpha=0.3)
            row_idx += 1
        
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
        
        for (label_a, label_b) in pairs:
            data_a = np.random.rand(500) * 2 - 1
            data_b = data_a * 0.8 + np.random.rand(500) * 0.2
            corr_value = 0.8
            
            axes[row_idx].scatter(data_a, data_b, s=2, alpha=0.4)
            axes[row_idx].set_title(f"时域相关性 - {label_a} vs {label_b}", fontsize=10)
            axes[row_idx].set_xlabel(label_a, fontsize=8)
            axes[row_idx].set_ylabel(label_b, fontsize=8)
            axes[row_idx].tick_params(axis='both', labelsize=8)
            axes[row_idx].grid(True, alpha=0.3)
            axes[row_idx].text(0.05, 0.95, f"相关性系数: {corr_value:.4f}", 
                              transform=axes[row_idx].transAxes, 
                              ha='left', va='top', fontsize=8,
                              bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            row_idx += 1
        
        for (label_a, label_b) in pairs:
            data_a = np.random.rand(500) * 0.001 + 0.0001
            data_b = data_a * 0.9 + np.random.rand(500) * 0.0002
            corr_value = 0.7
            
            axes[row_idx].scatter(data_a, data_b, s=2, alpha=0.4)
            axes[row_idx].set_title(f"频域相关性 - {label_a} vs {label_b}", fontsize=10)
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
        
        os.makedirs('test_tab6_full_output', exist_ok=True)
        path = os.path.join('test_tab6_full_output', f"batch_{channel_name}.png")
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  通道 {channel_name}: {figsize}, 子图数: {n_rows}")
    
    print("\n通道综合分析图测试完成！")

def test_matrix_plots():
    """测试相似度矩阵图"""
    print("\n" + "=" * 60)
    print("测试相似度矩阵图")
    print("=" * 60)
    
    labels = ['KW1', 'KW2', 'KW3']
    channels = [f'CH{i}' for i in range(1, 13)]
    n_groups = len(labels)
    
    for ch_idx, channel_name in enumerate(channels):
        time_matrix = np.eye(n_groups)
        freq_matrix = np.eye(n_groups)
        
        for i in range(n_groups):
            for j in range(n_groups):
                if i != j:
                    time_matrix[i, j] = np.random.uniform(0, 1)
                    freq_matrix[i, j] = np.random.uniform(0, 1)
        
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        im = axes[0].imshow(time_matrix, cmap='viridis', aspect='auto')
        axes[0].set_title(f"{channel_name} - 时域相似度矩阵", fontsize=12)
        axes[0].set_xlabel("组B")
        axes[0].set_ylabel("组A")
        axes[0].set_xticks(range(n_groups))
        axes[0].set_yticks(range(n_groups))
        axes[0].set_xticklabels(labels)
        axes[0].set_yticklabels(labels)
        for i in range(n_groups):
            for j in range(n_groups):
                axes[0].text(j, i, f"{time_matrix[i, j]:.3f}", ha='center', va='center', 
                            color='white' if time_matrix[i, j] < 0.5 else 'black', fontsize=8)
        fig.colorbar(im, ax=axes[0])
        
        im = axes[1].imshow(freq_matrix, cmap='viridis', aspect='auto')
        axes[1].set_title(f"{channel_name} - 频域相似度矩阵", fontsize=12)
        axes[1].set_xlabel("组B")
        axes[1].set_ylabel("组A")
        axes[1].set_xticks(range(n_groups))
        axes[1].set_yticks(range(n_groups))
        axes[1].set_xticklabels(labels)
        axes[1].set_yticklabels(labels)
        for i in range(n_groups):
            for j in range(n_groups):
                axes[1].text(j, i, f"{freq_matrix[i, j]:.3f}", ha='center', va='center', 
                            color='white' if freq_matrix[i, j] < 0.5 else 'black', fontsize=8)
        fig.colorbar(im, ax=axes[1])
        
        fig.tight_layout()
        path = os.path.join('test_tab6_full_output', f"matrix_{channel_name}.png")
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  通道 {channel_name}: 矩阵图已生成")
    
    print("\n相似度矩阵图测试完成！")

if __name__ == '__main__':
    test_channel_composite()
    test_matrix_plots()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("路径: test_tab6_full_output/")
    print("=" * 60)