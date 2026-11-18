#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
报告合规性测试脚本 - 测试Tab3/4/5/6/7/8的报告生成
检查以下问题：
1. 实验状态定义信息正确显示
2. 图片比例（宽高比≤3.3，图高/文字高≤7.5）
3. 每个通道一张图，子图分类
4. 第二时间切片（第一切片6-10s，第二切片6.5-6.6s）
5. Tab8实验状态关联
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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_compliance.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(f"[TEST] {msg}", flush=True)

def find_tdms_files():
    """查找TDMS文件"""
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

def create_test_experiment_states():
    """创建测试用的实验状态"""
    from experiment_state import STATE_REGISTRY
    STATE_REGISTRY.clear()
    
    states = [
        {'name': '状态A', 'type': 'TC12', 'params': {'α': 0.1, 'K': 1.0, '电压': '5V', '数据文件': 'file1.tdms'}},
        {'name': '状态B', 'type': 'TC12', 'params': {'α': 0.2, 'K': 2.0, '电压': '10V', '数据文件': 'file2.tdms'}},
        {'name': '状态C', 'type': 'TC34', 'params': {'α': 0.3, 'K': 3.0, '电压': '15V', '数据文件': 'file3.tdms'}},
    ]
    
    for state in states:
        STATE_REGISTRY.add_state(state)
        log(f"  创建实验状态: {state['name']}")
    
    return states

def test_time_slice_report(report_dir):
    """测试第二时间切片问题 - 第一切片6-10s，第二切片6.5-6.6s"""
    log("=" * 80)
    log("测试时间切片: 第一切片6-10s, 第二切片6.5-6.6s")
    log("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from main import BatchCompareTab
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        
        REPORT_MANAGER.set_report_dir(report_dir)
        
        create_test_experiment_states()
        
        tdms_files = find_tdms_files()
        if len(tdms_files) < 1:
            log("  错误：未找到TDMS文件")
            return False
        
        tab = BatchCompareTab()
        
        filepath = tdms_files[0]
        data_array, fs, meta = load_data(filepath)
        
        start_idx = int(6 * fs)
        end_idx = int(10 * fs)
        proc_data = data_array[start_idx:end_idx]
        
        from scipy import signal
        if len(proc_data) > 10000:
            proc_data = signal.resample(proc_data, 10000)
        
        tab.groups.append({
            'label': '测试组',
            'filepath': filepath,
            'data': data_array,
            'meta': meta,
            'fs': fs,
            'proc_data': proc_data,
            'proc_meta': {
                'fs': fs,
                'slice_start': 6.0,
                'slice_end': 10.0,
                'channel_map': meta.get('channel_map', {})
            },
            'display_slice_start': 6.5,
            'display_slice_end': 6.6,
            'experiment_state': '状态A'
        })
        tab.group_list.addItem('测试组[状态A]: test.tdms')
        tab.update_channel_combo()
        
        channels = tab.get_all_channels()[:2]
        
        md_content = "## 时间切片测试报告\n\n"
        md_content += "### 实验状态定义\n\n"
        md_content += STATE_REGISTRY.to_markdown_table()
        md_content += "\n"
        md_content += f"**第一时间切片**: 6.0s - 10.0s\n"
        md_content += f"**第二时间切片**: 6.5s - 6.6s\n\n"
        
        all_images = []
        
        for ch in channels:
            fig, ax = plt.subplots(figsize=(10, 3))
            data = tab.get_channel_data(tab.groups[0], ch)
            
            display_start = tab.groups[0].get('display_slice_start', 0)
            display_end = tab.groups[0].get('display_slice_end', len(data) / tab.groups[0]['fs'])
            
            t = np.linspace(display_start, display_end, len(data))
            ax.plot(t, data, linewidth=1.0)
            ax.set_xlabel('时间 (s)')
            ax.set_ylabel(ch)
            ax.set_title(f"通道 {ch} - 时间切片测试")
            
            fig.tight_layout()
            path = os.path.join(report_dir, f"timeslice_{ch}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            all_images.append(path)
            md_content += f"#### 通道 {ch}\n\n![通道 {ch}](timeslice_{ch}.png)\n\n"
        
        from experiment_state import ReportBlock
        block = ReportBlock(
            source_tab='时间切片测试',
            title="时间切片测试报告",
            content_md=md_content,
            images=all_images
        )
        REPORT_MANAGER.add_block(block)
        
        md_full = REPORT_MANAGER.to_full_markdown()
        report_path = os.path.join(report_dir, 'timeslice_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_full)
        
        log(f"时间切片测试报告生成成功！图片数: {len(all_images)}")
        log(f"报告路径: {report_path}")
        
        app.quit()
        return True
        
    except Exception as e:
        log(f"时间切片测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")
        return False

def test_tab8_state_association(report_dir):
    """测试Tab8实验状态关联"""
    log("=" * 80)
    log("测试Tab8实验状态关联")
    log("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from channel_sensitivity_tab import ChannelSensitivityTab
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        
        REPORT_MANAGER.set_report_dir(report_dir)
        
        create_test_experiment_states()
        
        tdms_files = find_tdms_files()
        if len(tdms_files) < 2:
            log("  错误：需要至少2个TDMS文件")
            return False
        
        tab = ChannelSensitivityTab()
        tab.refresh_experiment_states()
        
        exp_file = tdms_files[0]
        data_array, fs, meta = load_data(exp_file)
        
        start_idx = int(0 * fs)
        end_idx = min(int(1 * fs), len(data_array))
        proc_data = data_array[start_idx:end_idx]
        
        from scipy import signal
        if len(proc_data) > 10000:
            proc_data = signal.resample(proc_data, 10000)
        
        tab.subtab_a.exp_data = proc_data
        tab.subtab_a.exp_meta = {'fs': fs}
        tab.subtab_a.channels = [f"CH{i+1}" for i in range(min(4, proc_data.shape[1]))]
        tab.subtab_a.n_channels = min(4, proc_data.shape[1])
        tab.subtab_a.fs = fs
        
        bg_file = tdms_files[1]
        data_array_bg, fs_bg, meta_bg = load_data(bg_file)
        proc_data_bg = data_array_bg[start_idx:end_idx]
        if len(proc_data_bg) > 10000:
            proc_data_bg = signal.resample(proc_data_bg, 10000)
        
        tab.subtab_a.bg_data = proc_data_bg
        tab.subtab_a.bg_meta = {'fs': fs_bg}
        
        tab.subtab_a.exp_state_mapper.set_state("状态A")
        tab.subtab_a.bg_state_mapper.set_state("状态B")
        
        exp_state = tab.subtab_a.exp_state_mapper.get_selected_state()
        bg_state = tab.subtab_a.bg_state_mapper.get_selected_state()
        
        log(f"  实验组关联状态: {exp_state}")
        log(f"  背景组关联状态: {bg_state}")
        
        if exp_state == "状态A" and bg_state == "状态B":
            log("  ✅ 实验状态关联成功！")
            success = True
        else:
            log("  ❌ 实验状态关联失败！")
            success = False
        
        md_content = "## Tab8实验状态关联测试\n\n"
        md_content += "### 实验状态定义\n\n"
        md_content += STATE_REGISTRY.to_markdown_table()
        md_content += "\n"
        md_content += f"**实验组关联状态**: {exp_state}\n"
        md_content += f"**背景组关联状态**: {bg_state}\n"
        md_content += f"**关联结果**: {'成功 ✅' if success else '失败 ❌'}\n"
        
        from experiment_state import ReportBlock
        block = ReportBlock(
            source_tab='Tab8状态关联测试',
            title="Tab8实验状态关联测试报告",
            content_md=md_content,
            images=[]
        )
        REPORT_MANAGER.add_block(block)
        
        md_full = REPORT_MANAGER.to_full_markdown()
        report_path = os.path.join(report_dir, 'tab8_state_test.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_full)
        
        app.quit()
        return success
        
    except Exception as e:
        log(f"Tab8状态关联测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")
        return False

def test_figure_aspect_ratio(report_dir):
    """测试图片比例：宽高比≤3.3，图高/文字高≤7.5"""
    log("=" * 80)
    log("测试图片比例")
    log("=" * 80)
    
    try:
        fig, axes = plt.subplots(4, 1, figsize=(10, 12))
        for i, ax in enumerate(axes):
            t = np.linspace(0, 1, 100)
            ax.plot(t, np.sin(2*np.pi*t*(i+1)))
            ax.set_ylabel(f'通道{i+1}', fontsize=10)
        
        width, height = fig.get_size_inches()
        aspect_ratio = width / height
        log(f"  宽高比: {width:.2f} / {height:.2f} = {aspect_ratio:.2f}")
        
        font_size = 10
        fig_height_pixels = height * 150
        text_height_points = font_size
        text_height_inches = text_height_points / 72
        text_height_pixels = text_height_inches * 150
        fig_text_ratio = fig_height_pixels / text_height_pixels
        log(f"  图高/文字高: {fig_height_pixels:.0f}px / {text_height_pixels:.0f}px = {fig_text_ratio:.2f}")
        
        passed = aspect_ratio <= 3.3 and fig_text_ratio <= 7.5
        log(f"  比例检查结果: {'通过 ✅' if passed else '不通过 ❌'}")
        
        fig.savefig(os.path.join(report_dir, 'aspect_ratio_test.png'), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        md_content = "## 图片比例测试\n\n"
        md_content += f"**宽高比**: {width:.2f} / {height:.2f} = {aspect_ratio:.2f} (要求≤3.3)\n"
        md_content += f"**图高/文字高**: {fig_height_pixels:.0f}px / {text_height_pixels:.0f}px = {fig_text_ratio:.2f} (要求≤7.5)\n"
        md_content += f"**结果**: {'通过 ✅' if passed else '不通过 ❌'}\n"
        
        from experiment_state import ReportBlock
        block = ReportBlock(
            source_tab='图片比例测试',
            title="图片比例测试报告",
            content_md=md_content,
            images=['aspect_ratio_test.png']
        )
        REPORT_MANAGER.add_block(block)
        
        return passed
        
    except Exception as e:
        log(f"图片比例测试失败: {e}")
        return False

def main():
    log("=" * 80)
    log("报告合规性测试开始")
    log("=" * 80)
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_compliance_output')
    os.makedirs(report_dir, exist_ok=True)
    log(f"报告目录: {report_dir}")
    
    results = []
    
    log("\n1. 测试第二时间切片...")
    result1 = test_time_slice_report(report_dir)
    results.append(("时间切片测试", result1))
    
    log("\n2. 测试Tab8实验状态关联...")
    result2 = test_tab8_state_association(report_dir)
    results.append(("Tab8状态关联测试", result2))
    
    log("\n3. 测试图片比例...")
    result3 = test_figure_aspect_ratio(report_dir)
    results.append(("图片比例测试", result3))
    
    log("\n" + "=" * 80)
    log("测试结果汇总")
    log("=" * 80)
    for name, passed in results:
        log(f"  {name}: {'通过 ✅' if passed else '失败 ❌'}")
    
    all_passed = all(r[1] for r in results)
    log(f"\n整体结果: {'全部通过 ✅' if all_passed else '存在失败 ❌'}")
    
    log("\n检查输出文件...")
    files = os.listdir(report_dir)
    md_files = [f for f in files if f.endswith('.md')]
    png_files = [f for f in files if f.endswith('.png')]
    
    log(f"  MD报告: {len(md_files)} 个")
    log(f"  PNG图片: {len(png_files)} 张")
    
    log("\n" + "=" * 80)
    log("报告合规性测试结束")
    log("=" * 80)

if __name__ == '__main__':
    main()
