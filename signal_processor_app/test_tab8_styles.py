#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试Tab8图表样式美化
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

def test_time_domain():
    """测试时域对比图"""
    print("=" * 60)
    print("测试时域对比图")
    print("=" * 60)
    
    n_channels = 8
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 1.8
    fig_width = 16.0
    if fig_height > 20:
        fig_height = 20
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.5, wspace=0.4)
    
    for i in range(n_rows):
        for j in range(n_cols):
            ax = fig.add_subplot(gs[i, j])
            if j == 0:
                data = np.random.rand(500) * 0.05 + 5.0
                title = f"背景组 CH{i+1}"
                t = np.linspace(8.5, 8.55, len(data))
                ax.plot(t, data, linewidth=1.0, color='#FF9800')
            else:
                data = np.random.rand(500) * 0.05 + 5.0
                title = f"实验组 CH{i+1}"
                t = np.linspace(8.5, 8.55, len(data))
                ax.plot(t, data, linewidth=1.0, color='#2196F3')
            
            ax.set_title(title, fontsize=11, fontweight='bold')
            ax.set_xlabel("时间(s)", fontsize=9)
            ax.set_ylabel("信号值", fontsize=9)
            ax.tick_params(axis='both', labelsize=8)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_facecolor('#f8f9fa')
    
    fig.suptitle(f"时域对比（第二时间切片: 8.500s - 8.550s）", fontsize=16, fontweight='bold')
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    os.makedirs('test_tab8_output', exist_ok=True)
    path = os.path.join('test_tab8_output', 'time_domain.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"图片已保存: {path}")

def test_freq_domain():
    """测试频域对比图"""
    print("\n" + "=" * 60)
    print("测试频域对比图")
    print("=" * 60)
    
    n_channels = 8
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 1.8
    fig_width = 16.0
    if fig_height > 20:
        fig_height = 20
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.5, wspace=0.4)
    
    for i in range(n_rows):
        for j in range(n_cols):
            ax = fig.add_subplot(gs[i, j])
            if j == 0:
                f = np.linspace(0, 200000, 500)
                data = np.random.rand(500) * 1e-10 + 1e-12
                title = f"背景组 CH{i+1}"
                ax.semilogy(f, data, linewidth=1.0, color='#FF9800')
            else:
                f = np.linspace(0, 200000, 500)
                data = np.random.rand(500) * 1e-10 + 1e-12
                title = f"实验组 CH{i+1}"
                ax.semilogy(f, data, linewidth=1.0, color='#2196F3')
            
            ax.set_title(title, fontsize=11, fontweight='bold')
            ax.set_xlabel("频率(Hz)", fontsize=9)
            ax.set_ylabel("功率谱密度", fontsize=9)
            ax.tick_params(axis='both', labelsize=8)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_xlim(0, 200000)
            ax.set_facecolor('#f8f9fa')
    
    fig.suptitle("频域对比", fontsize=16, fontweight='bold')
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    path = os.path.join('test_tab8_output', 'freq_domain.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"图片已保存: {path}")

def test_time_correlation():
    """测试时域相关性图"""
    print("\n" + "=" * 60)
    print("测试时域相关性图")
    print("=" * 60)
    
    channels = ['CH10', 'CH2', 'CH3', 'CH4', 'CH12', 'CH7', 'CH5', 'CH1']
    n_channels = len(channels)
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 1.2
    fig_width = 14.0
    if fig_height > 16:
        fig_height = 16
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.4, wspace=0.3)
    
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
            
            ax.scatter(data_a, data_b, s=2, alpha=0.4, color='#2196F3')
            ax.set_title(f"{ch_name}", fontsize=10, fontweight='bold')
            ax.set_xlabel("实验组", fontsize=8)
            ax.set_ylabel("背景组", fontsize=8)
            ax.tick_params(axis='both', labelsize=7)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_facecolor('#f8f9fa')
            ax.text(0.05, 0.95, f"Kb={kb:.4f}, Ka={ka:.4f}", 
                    transform=ax.transAxes, 
                    ha='left', va='top', fontsize=7,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
            
            idx += 1
    
    fig.suptitle("时域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    path = os.path.join('test_tab8_output', 'time_correlation.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"图片已保存: {path}")

def test_freq_correlation():
    """测试频域相关性图"""
    print("\n" + "=" * 60)
    print("测试频域相关性图")
    print("=" * 60)
    
    channels = ['CH10', 'CH2', 'CH3', 'CH4', 'CH12', 'CH7', 'CH5', 'CH1']
    n_channels = len(channels)
    n_rows = n_channels
    n_cols = 2
    
    fig_height = n_rows * 1.2
    fig_width = 14.0
    if fig_height > 16:
        fig_height = 16
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.4, wspace=0.3)
    
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
            data_b = data_a * 0.95 + np.random.rand(500) * 0.000002
            
            ax.scatter(data_a, data_b, s=2, alpha=0.4, color='#2196F3')
            ax.set_title(f"{ch_name}", fontsize=10, fontweight='bold')
            ax.set_xlabel("实验组频谱", fontsize=8)
            ax.set_ylabel("背景组频谱", fontsize=8)
            ax.tick_params(axis='both', labelsize=7)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_facecolor('#f8f9fa')
            ax.text(0.05, 0.95, f"Kb={kb:.4f}, Ka={ka:.4f}", 
                    transform=ax.transAxes, 
                    ha='left', va='top', fontsize=7,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
            
            idx += 1
    
    fig.suptitle("频域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    path = os.path.join('test_tab8_output', 'freq_correlation.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"图片已保存: {path}")

if __name__ == '__main__':
    test_time_domain()
    test_freq_domain()
    test_time_correlation()
    test_freq_correlation()
    
    print("\n" + "=" * 60)
    print("所有样图已生成！")
    print("路径: test_tab8_output/")
    print("=" * 60)