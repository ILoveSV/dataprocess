#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
单独测试Tab8通道敏感性分析
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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tab8_test.log')

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

def test_tab8(tdms_files, report_dir):
    """测试Tab8通道敏感性分析"""
    log("=" * 80)
    log("测试Tab8: 通道敏感性分析")
    log("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from channel_sensitivity_tab import ChannelSensitivityTab
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        
        REPORT_MANAGER.set_report_dir(report_dir)
        
        log("创建实验状态...")
        STATE_REGISTRY.add_state({
            'name': "实验状态-实验组",
            'type': 'TC12',
            'params': {'α或K': 0.1, 'r': 1.0}
        })
        STATE_REGISTRY.add_state({
            'name': "实验状态-背景组",
            'type': 'TC12',
            'params': {'α或K': 0.0, 'r': 1.0}
        })
        
        log("创建ChannelSensitivityTab...")
        tab = ChannelSensitivityTab()
        
        log("加载实验组数据...")
        exp_file = tdms_files[0] if len(tdms_files) > 0 else tdms_files[-1]
        data_array, fs, meta = load_data(exp_file)
        
        start_idx = 0
        end_idx = min(int(0.5 * fs), len(data_array))
        proc_data = data_array[start_idx:end_idx]
        
        from scipy import signal
        if len(proc_data) > 10000:
            proc_data = signal.resample(proc_data, 10000)
        
        tab.subtab_a.exp_data = proc_data
        tab.subtab_a.exp_meta = {'fs': fs}
        tab.subtab_a.channels = [f"CH{i+1}" for i in range(min(4, proc_data.shape[1]))]
        tab.subtab_a.n_channels = min(4, proc_data.shape[1])
        tab.subtab_a.fs = fs
        
        log("加载背景组数据...")
        bg_file = tdms_files[1] if len(tdms_files) > 1 else tdms_files[-1]
        data_array_bg, fs_bg, meta_bg = load_data(bg_file)
        
        proc_data_bg = data_array_bg[start_idx:end_idx]
        if len(proc_data_bg) > 10000:
            proc_data_bg = signal.resample(proc_data_bg, 10000)
        
        tab.subtab_a.bg_data = proc_data_bg
        tab.subtab_a.bg_meta = {'fs': fs_bg}
        tab.subtab_a.bg_channels = tab.subtab_a.channels
        
        log("计算敏感性...")
        channels = tab.subtab_a.channels[:4]
        
        sensitivity_results = []
        for ch_idx, ch_name in enumerate(channels):
            exp_ch_data = proc_data[:, ch_idx] if len(proc_data.shape) > 1 else proc_data
            bg_ch_data = proc_data_bg[:, ch_idx] if len(proc_data_bg.shape) > 1 else proc_data_bg
            
            from scipy.stats import pearsonr
            corr, _ = pearsonr(exp_ch_data, bg_ch_data)
            
            ka = 1 - abs(corr)
            kb = np.mean(np.abs(exp_ch_data - bg_ch_data)) / (np.std(exp_ch_data) + np.std(bg_ch_data) + 1e-10)
            
            sensitivity_results.append({
                'channel': ch_name,
                'ka': ka,
                'kb': kb,
                'correlation': corr,
                'exp_data': exp_ch_data,
                'bg_data': bg_ch_data,
                'fs': fs
            })
        
        sensitivity_results.sort(key=lambda x: x['ka'], reverse=True)
        tab.subtab_a.sensitivity_results = sensitivity_results
        
        log("生成报告...")
        from experiment_state import ReportBlock
        import matplotlib.pyplot as plt
        
        md_content = f"## 通道敏感性分析报告\n\n"
        md_content += "### 实验状态定义\n\n"
        md_content += STATE_REGISTRY.to_markdown_table()
        md_content += "\n"
        
        all_images = []
        
        md_content += "### 敏感性排序\n\n"
        md_content += "| 排名 | 通道 | Ka指标 | Kb指标 | 相关性 |\n"
        md_content += "|------|------|--------|--------|--------|\n"
        for i, item in enumerate(sensitivity_results, 1):
            md_content += f"| {i} | {item['channel']} | {item['ka']:.6f} | {item['kb']:.6f} | {item['correlation']:.6f} |\n"
        md_content += "\n> **说明**: Ka越大表示敏感性越高（相关性越小，敏感性越高）\n\n"
        
        md_content += "### 时域波形对比\n\n"
        for item in sensitivity_results:
            fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
            
            t = np.arange(len(item['exp_data'])) / item['fs']
            axes[0].plot(t, item['exp_data'], label='实验组')
            axes[0].set_title(f"通道 {item['channel']} - 实验组")
            axes[0].legend()
            
            axes[1].plot(t, item['bg_data'], label='背景组', color='orange')
            axes[1].set_title(f"通道 {item['channel']} - 背景组")
            axes[1].legend()
            axes[1].set_xlabel("时间 (s)")
            
            fig.tight_layout()
            path = os.path.join(report_dir, f"tab8_time_{item['channel']}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            all_images.append(path)
            md_content += f"#### 通道 {item['channel']}\n\n![通道 {item['channel']} 时域](tab8_time_{item['channel']}.png)\n\n"
        
        md_content += "### 频域分析\n\n"
        for item in sensitivity_results:
            fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
            
            from scipy import signal
            f_exp, Pxx_exp = signal.welch(item['exp_data'], fs=item['fs'], nperseg=min(len(item['exp_data']), 1024))
            f_bg, Pxx_bg = signal.welch(item['bg_data'], fs=item['fs'], nperseg=min(len(item['bg_data']), 1024))
            
            axes[0].semilogy(f_exp, Pxx_exp, label='实验组')
            axes[0].set_title(f"通道 {item['channel']} - 实验组频谱")
            axes[0].legend()
            
            axes[1].semilogy(f_bg, Pxx_bg, label='背景组', color='orange')
            axes[1].set_title(f"通道 {item['channel']} - 背景组频谱")
            axes[1].legend()
            axes[1].set_xlabel("频率 (Hz)")
            
            fig.tight_layout()
            path = os.path.join(report_dir, f"tab8_freq_{item['channel']}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            all_images.append(path)
            md_content += f"#### 通道 {item['channel']}\n\n![通道 {item['channel']} 频域](tab8_freq_{item['channel']}.png)\n\n"
        
        md_content += "### 相关性分析\n\n"
        for item in sensitivity_results:
            fig, ax = plt.subplots(figsize=(8, 4))
            
            from scipy import signal
            corr = signal.correlate(item['exp_data'], item['bg_data'], mode='same')
            corr = corr / np.max(np.abs(corr))
            t = np.arange(len(corr)) / item['fs']
            
            ax.plot(t, corr, linewidth=0.8)
            ax.set_xlabel('时间延迟 (s)')
            ax.set_ylabel('归一化互相关')
            ax.set_title(f"通道 {item['channel']} - 互相关")
            
            fig.tight_layout()
            path = os.path.join(report_dir, f"tab8_corr_{item['channel']}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            all_images.append(path)
            md_content += f"#### 通道 {item['channel']}\n\n![通道 {item['channel']} 相关性](tab8_corr_{item['channel']}.png)\n\n"
        
        block = ReportBlock(
            source_tab='通道敏感性分析',
            title="Tab8-通道敏感性分析",
            content_md=md_content,
            images=all_images
        )
        REPORT_MANAGER.add_block(block)
        
        md_full = REPORT_MANAGER.to_full_markdown()
        report_path = os.path.join(report_dir, 'tab8_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_full)
        
        log(f"Tab8报告生成成功！图片数: {len(all_images)}")
        log(f"报告路径: {report_path}")
        
        app.quit()
        
    except Exception as e:
        log(f"Tab8测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")

def main():
    log("=" * 80)
    log("Tab8通道敏感性分析测试开始")
    log("=" * 80)
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_all_tabs_output')
    os.makedirs(report_dir, exist_ok=True)
    log(f"报告目录: {report_dir}")
    
    log("查找TDMS文件...")
    tdms_files = find_tdms_files()
    
    if len(tdms_files) < 2:
        log(f"警告：只找到 {len(tdms_files)} 个文件，重复使用")
        while len(tdms_files) < 2:
            tdms_files.append(tdms_files[-1])
    
    log(f"共使用 {len(tdms_files)} 个TDMS文件")
    
    test_tab8(tdms_files, report_dir)
    
    log("=" * 80)
    log("Tab8通道敏感性分析测试结束")
    log("=" * 80)
    
    log("检查输出文件...")
    files = os.listdir(report_dir)
    png_files = [f for f in files if f.endswith('.png')]
    md_files = [f for f in files if f.endswith('.md')]
    
    log(f"\n生成的PNG图片: {len(png_files)} 张")
    for png in sorted(png_files):
        size = os.path.getsize(os.path.join(report_dir, png)) / 1024
        log(f"  {png}: {size:.2f} KB")
    
    log(f"\n生成的MD报告: {len(md_files)} 个")
    for md in sorted(md_files):
        size = os.path.getsize(os.path.join(report_dir, md)) / 1024
        log(f"  {md}: {size:.2f} KB")

if __name__ == '__main__':
    main()
