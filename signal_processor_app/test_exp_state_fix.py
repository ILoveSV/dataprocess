#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试Tab7和Tab8报告中的实验状态定义表
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

def log(msg):
    print(f"[TEST] {msg}", flush=True)

def test_tab7_exp_state():
    """测试Tab7背景对消批处理报告中的实验状态定义表"""
    from experiment_state import STATE_REGISTRY, ReportBlock, REPORT_MANAGER
    
    STATE_REGISTRY.clear()
    REPORT_MANAGER.clear()
    
    STATE_REGISTRY.add_state({
        'name': '状态A-放电',
        'type': 'TC12',
        'params': {
            'α或K': '30°',
            'β或L': '45°',
            'r': '1.5m'
        }
    })
    
    STATE_REGISTRY.add_state({
        'name': '状态B-不放电',
        'type': 'TC12',
        'params': {
            'α或K': '30°',
            'β或L': '45°',
            'r': '1.5m'
        }
    })
    
    state_names = ['状态A-放电', '状态B-不放电']
    md_content = "## 背景对消批量参数对比报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
    md_content += "\n"
    
    block = ReportBlock(
        source_tab='背景对消批处理',
        title='Tab7测试',
        content_md=md_content,
        images=[]
    )
    REPORT_MANAGER.add_block(block)
    
    md_full = REPORT_MANAGER.to_full_markdown()
    
    print("\nTab7报告内容:")
    print("=" * 60)
    print(md_full)
    print("=" * 60)
    
    assert '状态A-放电' in md_full, "状态A-放电未显示"
    assert '状态B-不放电' in md_full, "状态B-不放电未显示"
    assert 'TC12' in md_full, "类型未显示"
    assert 'α或K' in md_full, "参数α或K未显示"
    assert '30°' in md_full, "参数值未显示"
    
    log("✓ Tab7实验状态定义表显示正确")

def test_tab8_exp_state():
    """测试Tab8通道敏感性分析报告中的实验状态定义表"""
    from experiment_state import STATE_REGISTRY, ReportBlock, REPORT_MANAGER
    
    STATE_REGISTRY.clear()
    REPORT_MANAGER.clear()
    
    STATE_REGISTRY.add_state({
        'name': '方位0度',
        'type': '方位',
        'params': {
            '角度': '0°',
            '距离': '10m'
        }
    })
    
    STATE_REGISTRY.add_state({
        'name': '方位90度',
        'type': '方位',
        'params': {
            '角度': '90°',
            '距离': '10m'
        }
    })
    
    state_names = ['方位0度', '方位90度']
    md_content = "## 敏感性分析报告\n\n"
    md_content += "### 1. 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
    md_content += "\n"
    
    block = ReportBlock(
        source_tab='通道敏感性分析',
        title='Tab8测试',
        content_md=md_content,
        images=[]
    )
    REPORT_MANAGER.add_block(block)
    
    md_full = REPORT_MANAGER.to_full_markdown()
    
    print("\nTab8报告内容:")
    print("=" * 60)
    print(md_full)
    print("=" * 60)
    
    assert '方位0度' in md_full, "状态方位0度未显示"
    assert '方位90度' in md_full, "状态方位90度未显示"
    assert '方位' in md_full, "类型未显示"
    assert '角度' in md_full, "参数角度未显示"
    assert '0°' in md_full, "参数值未显示"
    
    log("✓ Tab8实验状态定义表显示正确")

if __name__ == '__main__':
    log("=" * 60)
    log("测试Tab7和Tab8实验状态定义表")
    log("=" * 60)
    
    test_tab7_exp_state()
    test_tab8_exp_state()
    
    log("=" * 60)
    log("所有测试通过！")
    log("=" * 60)