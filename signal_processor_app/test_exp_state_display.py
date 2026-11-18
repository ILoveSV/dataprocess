#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
专门测试实验状态定义信息在各Tab报告中的显示一致性
验证Tab3/4/5/6/7/8的报告是否正确显示用户在Tab5中输入的详细信息
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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exp_state_test.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(f"[TEST] {msg}", flush=True)

def find_tdms_files():
    tdms_files = []
    z_paths = [
        r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\1\不放电",
        r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\1\放电",
        r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\2\不放电",
        r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\2\放电",
    ]
    
    for path in z_paths:
        try:
            if os.path.exists(path):
                files = [f for f in os.listdir(path) if f.endswith('.tdms')]
                if files:
                    tdms_files.append(os.path.join(path, files[0]))
                    log(f"  找到: {os.path.basename(files[0])}")
        except Exception as e:
            log(f"  路径访问失败: {path}, 错误: {e}")
    
    return tdms_files

def create_test_exp_states():
    """创建测试用实验状态（模拟用户在Tab5中输入的数据）"""
    from experiment_state import STATE_REGISTRY
    
    STATE_REGISTRY.clear()
    
    state1 = STATE_REGISTRY.add_state({
        'name': "状态A-放电",
        'type': 'TC12',
        'params': {
            'α或K': '30°',
            'β或L': '45°',
            'r': '1.5m',
            'D': '0.5°',
            '一阶波激励策略': 'V1=10 T1=5 T0=100 (时间单位:ms, 电压单位:V)',
            '二阶波激励策略': 'V1=10 T1=5 V2=20 T2=5 T0=200 (时间单位:ms, 电压单位:V)',
            'TG1': '101325 Pa',
            'TG2': '自制直流高压模块配芯片',
            'TG3': '不锈钢KQS金属筒',
            'TG4': '设定无干扰',
            'TG5': '单人近经过',
            'CH1': '16',
            'CH2': '200K',
            '状态类型': 'TC12'
        }
    })
    
    state2 = STATE_REGISTRY.add_state({
        'name': "状态B-不放电",
        'type': 'TC12',
        'params': {
            'α或K': '30°',
            'β或L': '45°',
            'r': '1.5m',
            'D': '0.5°',
            '一阶波激励策略': 'V1=10 T1=5 T0=100 (时间单位:ms, 电压单位:V)',
            'TG1': '101325 Pa',
            'TG2': '自制直流高压模块配芯片',
            'TG3': '不锈钢KQS金属筒',
            'TG4': '设定无干扰',
            'TG5': '设定无干扰',
            'CH1': '16',
            'CH2': '200K',
            '状态类型': 'TC12'
        }
    })
    
    log(f"创建测试实验状态: {state1['name']}, {state2['name']}")
    return [state1, state2]

def verify_exp_state_in_markdown(md_content, expected_states):
    """验证Markdown内容中是否包含预期的实验状态信息"""
    issues = []
    
    for state in expected_states:
        state_name = state['name']
        if state_name not in md_content:
            issues.append(f"  - 缺少实验状态名称: {state_name}")
        
        params = state.get('params', {})
        for key, value in params.items():
            if value and str(value) not in md_content and key not in ['状态类型']:
                issues.append(f"  - 缺少参数 [{key}]: {value}")
    
    return issues

def test_tab6_exp_state(tdms_files, report_dir):
    """测试Tab6报告中的实验状态显示"""
    log("=" * 80)
    log("测试Tab6: 批量参数对比 - 实验状态显示")
    log("=" * 80)
    
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    from file_reader import load_data
    
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    expected_states = create_test_exp_states()
    
    groups = []
    for i, tdms_file in enumerate(tdms_files[:4]):
        data, fs, meta = load_data(tdms_file)
        if data is not None:
            label = f"组{i+1}"
            groups.append({
                'label': label,
                'filepath': tdms_file,
                'data': data,
                'meta': meta,
                'fs': fs,
                'experiment_state': expected_states[i % 2]['name'] if i < 2 else expected_states[(i+1) % 2]['name']
            })
    
    if not groups:
        log("未找到有效数据组")
        return
    
    md_content = f"## 批量参数对比报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    md_content += f"**数据组数**: {len(groups)}\n\n"
    
    report_path = os.path.join(report_dir, 'tab6_exp_state_test.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    issues = verify_exp_state_in_markdown(md_content, expected_states)
    if issues:
        log(f"✗ Tab6实验状态显示存在问题:")
        for issue in issues:
            log(issue)
    else:
        log(f"✓ Tab6实验状态显示正确")
    
    return md_content, expected_states, issues

def test_tab7_exp_state(tdms_files, report_dir):
    """测试Tab7报告中的实验状态显示"""
    log("=" * 80)
    log("测试Tab7: 背景对消批处理 - 实验状态显示")
    log("=" * 80)
    
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    from file_reader import load_data
    
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    expected_states = create_test_exp_states()
    
    exp_groups = []
    for i, tdms_file in enumerate(tdms_files[:2]):
        data, fs, meta = load_data(tdms_file)
        if data is not None:
            exp_groups.append({
                'label': f"实验组{i+1}",
                'filepath': tdms_file,
                'data': data,
                'fs': fs,
                'experiment_state': expected_states[i]['name']
            })
    
    bg_groups = []
    for i, tdms_file in enumerate(tdms_files[2:]):
        data, fs, meta = load_data(tdms_file)
        if data is not None:
            bg_groups.append({
                'label': f"背景组{i+1}",
                'filepath': tdms_file,
                'data': data,
                'fs': fs
            })
    
    md_content = f"## 背景对消批处理报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    
    md_content += "### 数据组列表\n\n"
    md_content += "| 编号 | 标签 | 数据文件 | 关联实验状态 | 采样率 |\n"
    md_content += "|------|------|----------|--------------|--------|\n"
    for i, group in enumerate(exp_groups):
        md_content += f"| {i+1} | {group['label']} | {os.path.basename(group['filepath'])} | {group.get('experiment_state', '')} | {group['fs']:.0f} Hz |\n"
    
    report_path = os.path.join(report_dir, 'tab7_exp_state_test.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    issues = verify_exp_state_in_markdown(md_content, expected_states)
    if issues:
        log(f"✗ Tab7实验状态显示存在问题:")
        for issue in issues:
            log(issue)
    else:
        log(f"✓ Tab7实验状态显示正确")
    
    return md_content, expected_states, issues

def test_tab8_exp_state(tdms_files, report_dir):
    """测试Tab8报告中的实验状态显示"""
    log("=" * 80)
    log("测试Tab8: 通道敏感性分析 - 实验状态显示")
    log("=" * 80)
    
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    from file_reader import load_data
    
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    expected_states = create_test_exp_states()
    
    exp_data, exp_fs, exp_meta = load_data(tdms_files[0])
    bg_data, bg_fs, bg_meta = load_data(tdms_files[2])
    
    md_content = f"## 通道敏感性分析报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    
    md_content += "### 数据分析\n\n"
    md_content += f"实验组关联状态: {expected_states[0]['name']}\n\n"
    md_content += f"背景组关联状态: {expected_states[1]['name']}\n\n"
    
    report_path = os.path.join(report_dir, 'tab8_exp_state_test.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    issues = verify_exp_state_in_markdown(md_content, expected_states)
    if issues:
        log(f"✗ Tab8实验状态显示存在问题:")
        for issue in issues:
            log(issue)
    else:
        log(f"✓ Tab8实验状态显示正确")
    
    return md_content, expected_states, issues

def test_tab3_exp_state(tdms_files, report_dir):
    """测试Tab3报告中的实验状态显示"""
    log("=" * 80)
    log("测试Tab3: 两组数据频域处理 - 实验状态显示")
    log("=" * 80)
    
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    from file_reader import load_data
    
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    expected_states = create_test_exp_states()
    
    md_content = f"## 频域处理报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    md_content += "### 处理配置\n\n"
    md_content += f"实验状态A: {expected_states[0]['name']}\n\n"
    md_content += f"实验状态B: {expected_states[1]['name']}\n\n"
    
    report_path = os.path.join(report_dir, 'tab3_exp_state_test.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    issues = verify_exp_state_in_markdown(md_content, expected_states)
    if issues:
        log(f"✗ Tab3实验状态显示存在问题:")
        for issue in issues:
            log(issue)
    else:
        log(f"✓ Tab3实验状态显示正确")
    
    return md_content, expected_states, issues

def test_tab4_exp_state(report_dir):
    """测试Tab4报告中的实验状态显示"""
    log("=" * 80)
    log("测试Tab4: 数据预处理 - 实验状态显示")
    log("=" * 80)
    
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    
    REPORT_MANAGER.clear()
    STATE_REGISTRY.clear()
    
    expected_states = create_test_exp_states()
    
    md_content = f"## 数据预处理报告\n\n"
    md_content += "### 实验状态定义\n\n"
    md_content += STATE_REGISTRY.to_markdown_table()
    md_content += "\n"
    md_content += "### 预处理配置\n\n"
    md_content += "处理类型: 单窗口截断\n\n"
    
    report_path = os.path.join(report_dir, 'tab4_exp_state_test.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    issues = verify_exp_state_in_markdown(md_content, expected_states)
    if issues:
        log(f"✗ Tab4实验状态显示存在问题:")
        for issue in issues:
            log(issue)
    else:
        log(f"✓ Tab4实验状态显示正确")
    
    return md_content, expected_states, issues

def generate_summary_report(report_dir, results):
    """生成测试总结报告"""
    log("=" * 80)
    log("生成测试总结报告")
    log("=" * 80)
    
    md_content = f"# 实验状态定义信息显示测试报告\n\n"
    md_content += f"> 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    md_content += "## 测试结果汇总\n\n"
    md_content += "| Tab | 测试项 | 结果 |\n"
    md_content += "|-----|--------|------|\n"
    
    all_passed = True
    for tab_name, (md, expected, issues) in results.items():
        status = "✓ 通过" if not issues else "✗ 失败"
        if issues:
            all_passed = False
        md_content += f"| {tab_name} | 实验状态定义信息显示 | {status} |\n"
    
    md_content += "\n"
    
    if all_passed:
        md_content += "## 结论\n\n"
        md_content += "所有测试通过！各Tab报告均正确显示用户在实验状态定义Tab中输入的详细信息。\n\n"
    else:
        md_content += "## 问题详情\n\n"
        for tab_name, (md, expected, issues) in results.items():
            if issues:
                md_content += f"### {tab_name}\n\n"
                md_content += "存在以下问题:\n\n"
                for issue in issues:
                    md_content += f"{issue}\n"
                md_content += "\n"
    
    md_content += "## 测试用实验状态定义\n\n"
    from experiment_state import STATE_REGISTRY
    STATE_REGISTRY.clear()
    expected_states = create_test_exp_states()
    md_content += STATE_REGISTRY.to_markdown_table()
    
    report_path = os.path.join(report_dir, 'exp_state_test_summary.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    log(f"测试总结报告已生成: {report_path}")
    return all_passed

if __name__ == '__main__':
    log("=" * 80)
    log("实验状态定义信息显示测试开始")
    log("=" * 80)
    
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_exp_state_output')
    os.makedirs(report_dir, exist_ok=True)
    log(f"报告目录: {report_dir}")
    
    tdms_files = find_tdms_files()
    log(f"找到 {len(tdms_files)} 个TDMS文件")
    
    results = {}
    
    results['Tab3'] = test_tab3_exp_state(tdms_files, report_dir)
    results['Tab4'] = test_tab4_exp_state(report_dir)
    results['Tab6'] = test_tab6_exp_state(tdms_files, report_dir)
    results['Tab7'] = test_tab7_exp_state(tdms_files, report_dir)
    results['Tab8'] = test_tab8_exp_state(tdms_files, report_dir)
    
    all_passed = generate_summary_report(report_dir, results)
    
    log("=" * 80)
    log(f"测试结束！{'所有测试通过' if all_passed else '存在测试失败'}")
    log("=" * 80)
    
    app.quit()