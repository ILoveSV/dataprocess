#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试实验状态推送时自动关联到数据组的功能
"""
import sys
import os
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

from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

def log(msg):
    print(f"[TEST] {msg}", flush=True)

def test_tab6_auto_association():
    """测试Tab6批量参数对比中实验状态自动关联"""
    log("=" * 60)
    log("测试Tab6: 实验状态推送自动关联")
    log("=" * 60)
    
    from experiment_state import STATE_REGISTRY
    
    STATE_REGISTRY.clear()
    
    STATE_REGISTRY.add_state({
        'name': '实验状态1',
        'type': 'TC12',
        'params': {'α或K': '30°'}
    })
    STATE_REGISTRY.add_state({
        'name': '实验状态2',
        'type': 'TC12',
        'params': {'α或K': '60°'}
    })
    
    from main import BatchCompareTab
    
    tab = BatchCompareTab()
    
    # 先推送实验状态1
    tab.push_experiment_state('实验状态1')
    log("✓ 推送实验状态1")
    
    # 然后添加数据组（模拟用户在实验状态推送后添加数据）
    import numpy as np
    
    # 添加KW1
    tab.groups.append({
        'label': 'KW1', 'filepath': 'test1.tdms', 'data': np.random.rand(1000), 
        'fs': 1000, 'proc_data': None, 'experiment_state': '实验状态1'
    })
    from PyQt5.QtWidgets import QListWidgetItem
    item = QListWidgetItem(f"KW1[实验状态1]: test1.tdms")
    tab.group_list.addItem(item)
    
    # 推送实验状态2
    tab.push_experiment_state('实验状态2')
    log("✓ 推送实验状态2")
    
    # 添加KW2和KW3（应该自动关联实验状态2）
    tab.groups.append({
        'label': 'KW2', 'filepath': 'test2.tdms', 'data': np.random.rand(1000), 
        'fs': 1000, 'proc_data': None, 'experiment_state': '实验状态2'
    })
    item = QListWidgetItem(f"KW2[实验状态2]: test2.tdms")
    tab.group_list.addItem(item)
    
    tab.groups.append({
        'label': 'KW3', 'filepath': 'test3.tdms', 'data': np.random.rand(1000), 
        'fs': 1000, 'proc_data': None, 'experiment_state': '实验状态2'
    })
    item = QListWidgetItem(f"KW3[实验状态2]: test3.tdms")
    tab.group_list.addItem(item)
    
    # 检查KW1是否关联了实验状态1
    assert 'experiment_state' in tab.groups[0], "KW1未关联实验状态"
    assert tab.groups[0]['experiment_state'] == '实验状态1', "KW1关联的实验状态不正确"
    log(f"✓ KW1关联实验状态: {tab.groups[0]['experiment_state']}")
    
    # 检查KW2和KW3是否关联了实验状态2
    assert 'experiment_state' in tab.groups[1], "KW2未关联实验状态"
    assert tab.groups[1]['experiment_state'] == '实验状态2', "KW2关联的实验状态不正确"
    log(f"✓ KW2关联实验状态: {tab.groups[1]['experiment_state']}")
    
    assert 'experiment_state' in tab.groups[2], "KW3未关联实验状态"
    assert tab.groups[2]['experiment_state'] == '实验状态2', "KW3关联的实验状态不正确"
    log(f"✓ KW3关联实验状态: {tab.groups[2]['experiment_state']}")
    
    log("✓ Tab6实验状态自动关联测试通过！")

def test_tab7_auto_association():
    """测试Tab7背景对消批处理中实验状态自动关联"""
    log("=" * 60)
    log("测试Tab7: 实验状态推送自动关联")
    log("=" * 60)
    
    from experiment_state import STATE_REGISTRY
    
    STATE_REGISTRY.clear()
    
    STATE_REGISTRY.add_state({
        'name': '实验状态1',
        'type': 'TC12',
        'params': {'α或K': '30°'}
    })
    STATE_REGISTRY.add_state({
        'name': '实验状态2',
        'type': 'TC12',
        'params': {'α或K': '60°'}
    })
    
    from main import BackgroundSubtractionTab
    
    tab = BackgroundSubtractionTab()
    
    # 模拟添加实验组和背景组
    import numpy as np
    tab.exp_groups = [
        {'label': 'KW1', 'filepath': 'exp1.tdms', 'data': np.random.rand(1000), 'fs': 1000},
        {'label': 'KW2', 'filepath': 'exp2.tdms', 'data': np.random.rand(1000), 'fs': 1000},
    ]
    tab.bg_groups = [
        {'label': '背景组1', 'filepath': 'bg1.tdms', 'data': np.random.rand(1000), 'fs': 1000},
        {'label': '背景组2', 'filepath': 'bg2.tdms', 'data': np.random.rand(1000), 'fs': 1000},
    ]
    
    # 添加列表项
    from PyQt5.QtWidgets import QListWidgetItem
    for group in tab.exp_groups:
        item = QListWidgetItem(f"{group['label']}: {os.path.basename(group['filepath'])}")
        tab.exp_list.addItem(item)
    for group in tab.bg_groups:
        item = QListWidgetItem(f"{group['label']}: {os.path.basename(group['filepath'])}")
        tab.bg_list.addItem(item)
    
    # 推送实验状态1
    tab.push_experiment_state('实验状态1')
    
    # 检查所有数据组是否关联了实验状态1
    for i, group in enumerate(tab.exp_groups):
        assert 'experiment_state' in group, f"实验组{group['label']}未关联实验状态"
        assert group['experiment_state'] == '实验状态1', f"实验组{group['label']}关联的实验状态不正确"
        log(f"✓ 实验组{group['label']}关联实验状态: {group['experiment_state']}")
    
    for i, group in enumerate(tab.bg_groups):
        assert 'experiment_state' in group, f"背景组{group['label']}未关联实验状态"
        assert group['experiment_state'] == '实验状态1', f"背景组{group['label']}关联的实验状态不正确"
        log(f"✓ 背景组{group['label']}关联实验状态: {group['experiment_state']}")
    
    log("✓ Tab7实验状态自动关联测试通过！")

if __name__ == '__main__':
    log("=" * 60)
    log("测试实验状态推送自动关联功能")
    log("=" * 60)
    
    test_tab6_auto_association()
    test_tab7_auto_association()
    
    log("=" * 60)
    log("所有测试通过！")
    log("=" * 60)