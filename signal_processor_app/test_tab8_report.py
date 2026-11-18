#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用模拟数据生成Tab8报告，供用户验证修改效果
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

def generate_tab8_report():
    """生成Tab8报告"""
    print("=" * 60)
    print("生成Tab8通道敏感性分析报告")
    print("=" * 60)
    
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    from channel_sensitivity_tab import ChannelSensitivityTab, BasicResponseSensitivityTab
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tab8_report_output')
    os.makedirs(report_dir, exist_ok=True)
    REPORT_MANAGER.set_report_dir(report_dir)
    
    print("\n创建实验状态...")
    STATE_REGISTRY.add_state({
        'name': "状态A-放电",
        'type': 'TC12',
        'params': {'α或K': '30°', 'β或L': '45°', 'r': '1.5m'}
    })
    STATE_REGISTRY.add_state({
        'name': "状态B-不放电", 
        'type': 'TC12',
        'params': {'α或K': '30°', 'β或L': '45°', 'r': '1.5m'}
    })
    
    print("\n创建Tab8组件...")
    tab = ChannelSensitivityTab()
    
    print("\n测试基础响应敏感性分析...")
    subtab = tab.subtab_a
    
    fs = 400000
    n_channels = 12
    duration = 6
    
    exp_data = np.random.randn(n_channels, fs * duration) * 0.05 + 5.0
    bg_data = np.random.randn(n_channels, fs * duration) * 0.03 + 5.0
    
    subtab.fs = fs
    subtab.n_channels = n_channels
    subtab.channels = [f'CH{i+1}' for i in range(n_channels)]
    subtab.exp_raw_data = exp_data
    subtab.bg_raw_data = bg_data
    
    subtab.slice_start_spin = type('obj', (), {'value': lambda: 6.0})()
    subtab.slice_end_spin = type('obj', (), {'value': lambda: 12.0})()
    subtab.corr_method_combo = type('obj', (), {'currentText': lambda: '皮尔逊相关系数'})()
    subtab.secondary_slice_start = type('obj', (), {'value': lambda: 0.5})()
    subtab.secondary_slice_end = type('obj', (), {'value': lambda: 0.6})()
    
    subtab.exp_state_combo = type('obj', (), {'currentData': lambda: '状态A-放电'})()
    subtab.bg_state_combo = type('obj', (), {'currentData': lambda: '状态B-不放电'})()
    
    subtab.process_data()
    
    print("\n计算相关性...")
    subtab.calculate_correlation()
    
    print("\n生成报告...")
    report_path = subtab.generate_report()
    
    print(f"\n报告已生成: {report_path}")
    print(f"\n报告目录: {report_dir}")
    
    files = os.listdir(report_dir)
    print("\n生成的文件:")
    for f in files:
        fpath = os.path.join(report_dir, f)
        size = os.path.getsize(fpath) / 1024
        print(f"  {f} - {size:.2f} KB")
    
    return report_path

if __name__ == '__main__':
    generate_tab8_report()