#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成Tab6/7/8完整报告测试
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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'all_tabs_test.log')

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

def test_tab6(tdms_files, report_dir):
    """测试Tab6多组数据扫参对比"""
    log("=" * 80)
    log("测试Tab6: 多组数据扫参对比")
    log("=" * 80)
    
    try:
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        
        REPORT_MANAGER.clear()
        STATE_REGISTRY.clear()
        REPORT_MANAGER.set_report_dir(report_dir)
        
        log("创建实验状态...")
        alpha_values = [0.1, 0.2, 0.3, 0.4]
        for i, alpha in enumerate(alpha_values):
            STATE_REGISTRY.add_state({
                'name': f"α{i+1}={alpha}",
                'type': 'TC12',
                'params': {'alpha': alpha, 'beta': 0.5, 'gamma': 1.0}
            })
        
        log("加载数据组...")
        groups = []
        labels = []
        for i, tdms_file in enumerate(tdms_files):
            data, fs, meta = load_data(tdms_file)
            if data is not None:
                label = f"组{i+1}"
                groups.append({
                    'label': label,
                    'filepath': tdms_file,
                    'data': data,
                    'meta': meta,
                    'fs': fs,
                })
                labels.append(label)
        
        if not groups:
            log("未找到有效数据组，跳过Tab6测试")
            return
        
        n_channels = groups[0]['data'].shape[1] if groups[0]['data'].ndim > 1 else 1
        channels = [f'CH{i+1}' for i in range(n_channels)]
        log(f"测试通道: {channels}")
        
        log("应用预处理...")
        slice_start = 6.0
        slice_end = 10.0
        
        for group in groups:
            data = group['data']
            fs = group['fs']
            start_idx = int(slice_start * fs)
            end_idx = int(slice_end * fs)
            end_idx = min(end_idx, len(data))
            sliced_data = data[start_idx:end_idx]
            group['proc_data'] = sliced_data
            group['proc_meta'] = {
                'fs': fs,
                'slice_start': slice_start,
                'slice_end': slice_end,
            }
        
        calc_type = "时域"
        
        log("计算相似性...")
        results = []
        import itertools
        for i, (group_a, group_b) in enumerate(itertools.combinations(groups, 2)):
            for ch in channels:
                ch_idx = int(ch.replace('CH', '')) - 1
                if group_a['data'].ndim > 1:
                    data_a = group_a['proc_data'][:, ch_idx].flatten()
                    data_b = group_b['proc_data'][:, ch_idx].flatten()
                else:
                    data_a = group_a['proc_data'].flatten()
                    data_b = group_b['proc_data'].flatten()
                
                if len(data_a) > 0 and len(data_b) > 0:
                    from scipy import signal
                    corr = signal.correlate(data_a, data_b, mode='same')
                    corr = corr / np.max(np.abs(corr))
                    results.append({
                        'group_a': group_a['label'],
                        'group_b': group_b['label'],
                        'channel': ch,
                        'data_a': data_a,
                        'data_b': data_b,
                        'corr_data': corr,
                        'fs': group_a['fs'],
                        'value': np.max(np.abs(corr))
                    })
        
        log("生成报告...")
        from experiment_state import ReportBlock
        import matplotlib.pyplot as plt
        
        md_content = f"## 批量参数对比报告\n\n"
        md_content += "### 实验状态定义\n\n"
        md_content += STATE_REGISTRY.to_markdown_table()
        md_content += "\n"
        md_content += f"**数据组数**: {len(labels)}\n\n"
        md_content += f"**参数标签**: {', '.join(labels)}\n\n"
        md_content += f"**计算类型**: {calc_type}\n\n"
        
        from plot_utils import calc_figsize
        
        md_content += "### 时域波形对比\n\n"
        for ch in channels:
            figsize = calc_figsize(len(groups), n_cols=1)
            fig, axes = plt.subplots(len(groups), 1, figsize=figsize, sharex=True)
            if len(groups) == 1:
                axes = [axes]
            for i, (ax, group) in enumerate(zip(axes, groups)):
                ch_idx = int(ch.replace('CH', '')) - 1
                if group['data'].ndim > 1:
                    data = group['proc_data'][:, ch_idx].flatten()
                else:
                    data = group['proc_data'].flatten()
                if len(data) > 0:
                    display_start = group['proc_meta']['slice_start']
                    display_end = group['proc_meta']['slice_end']
                    t = np.linspace(display_start, display_end, len(data))
                    ax.plot(t, data, linewidth=1.0)
                    ax.set_ylabel(group['label'], rotation=0, labelpad=20)
            axes[-1].set_xlabel("时间 (s)")
            fig.suptitle(f"通道 {ch} - 时域对比")
            fig.tight_layout(rect=[0.08, 0.02, 1, 0.96])
            path = os.path.join(report_dir, f"tab6_time_{ch}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            md_content += f"#### 通道 {ch}\n\n![通道 {ch} 时域](tab6_time_{ch}.png)\n\n"
        
        md_content += "### 频域波形对比\n\n"
        for ch in channels:
            figsize = calc_figsize(len(groups), n_cols=1)
            fig, axes = plt.subplots(len(groups), 1, figsize=figsize, sharex=True)
            if len(groups) == 1:
                axes = [axes]
            for i, (ax, group) in enumerate(zip(axes, groups)):
                ch_idx = int(ch.replace('CH', '')) - 1
                if group['data'].ndim > 1:
                    data = group['proc_data'][:, ch_idx].flatten()
                else:
                    data = group['proc_data'].flatten()
                if len(data) > 0:
                    fs = group['fs']
                    from scipy import signal
                    f, Pxx = signal.welch(data, fs=fs, nperseg=min(len(data), 1024))
                    ax.semilogy(f, Pxx, linewidth=1.0)
                    ax.set_xlim(0, fs/2)
                    ax.set_ylabel(group['label'], rotation=0, labelpad=20)
            axes[-1].set_xlabel("频率 (Hz)")
            fig.suptitle(f"通道 {ch} - 频域对比")
            fig.tight_layout(rect=[0.08, 0.02, 1, 0.96])
            path = os.path.join(report_dir, f"tab6_freq_{ch}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            md_content += f"#### 通道 {ch}\n\n![通道 {ch} 频域](tab6_freq_{ch}.png)\n\n"
        
        md_content += "### 相关性可视化\n\n"
        import itertools
        for ch in channels:
            channel_results = [r for r in results if r.get('channel') == ch]
            pairs = list(itertools.combinations(labels, 2))
            n_pairs = len(pairs)
            if n_pairs == 0:
                continue
            n_rows = (n_pairs + 1) // 2
            n_cols = min(2, n_pairs)
            figsize = calc_figsize(n_pairs, n_cols=n_cols)
            fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
            axes = axes.flatten() if n_rows > 1 or n_cols > 1 else [axes]
            for (label_a, label_b), ax in zip(pairs, axes):
                result = None
                for r in channel_results:
                    if (r.get('group_a') == label_a and r.get('group_b') == label_b) or \
                       (r.get('group_a') == label_b and r.get('group_b') == label_a):
                        result = r
                        break
                if result and result.get('data_a') is not None and result.get('data_b') is not None:
                    from scipy import signal
                    corr = signal.correlate(result['data_a'], result['data_b'], mode='same')
                    corr = corr / np.max(np.abs(corr))
                    t = np.arange(len(corr)) / result['fs']
                    ax.plot(t, corr, linewidth=0.8)
                    ax.set_xlabel('时间延迟 (s)', fontsize=8)
                    ax.set_ylabel('归一化互相关', fontsize=8)
                ax.set_title(f"{label_a} vs {label_b}")
            fig.suptitle(f"通道 {ch} - 相关性对比")
            fig.tight_layout(rect=[0.02, 0.02, 1, 0.96])
            path = os.path.join(report_dir, f"tab6_corr_{ch}.png")
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            md_content += f"#### 通道 {ch}\n\n![通道 {ch} 相关性](tab6_corr_{ch}.png)\n\n"
        
        md_content += "### 通道相关性指标排序\n\n"
        md_content += "| 排名 | 通道 | 加权均值 |\n"
        md_content += "|------|------|----------|\n"
        channel_corr = {}
        for r in results:
            channel = r.get('channel', '')
            value = r.get('value', 0)
            if isinstance(value, (int, float)):
                if channel not in channel_corr:
                    channel_corr[channel] = []
                channel_corr[channel].append(value)
        ranking = []
        for channel, values in channel_corr.items():
            if values:
                ranking.append({'channel': channel, 'weighted_mean': sum(values)/len(values)})
        ranking.sort(key=lambda x: x['weighted_mean'], reverse=True)
        for i, item in enumerate(ranking, 1):
            md_content += f"| {i} | {item['channel']} | {item['weighted_mean']:.6f} |\n"
        
        block = ReportBlock(
            source_tab='批量参数对比',
            title=f"Tab6-批量对比-{', '.join(labels)}",
            content_md=md_content,
            images=[]
        )
        REPORT_MANAGER.add_block(block)
        
        md_full = REPORT_MANAGER.to_full_markdown()
        report_path = os.path.join(report_dir, 'tab6_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_full)
        
        log(f"Tab6报告生成成功！")
        log(f"报告路径: {report_path}")
        
    except Exception as e:
        log(f"Tab6测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")

def test_tab7(tdms_files, report_dir):
    """测试Tab7背景对消批处理"""
    log("=" * 80)
    log("测试Tab7: 背景对消批处理")
    log("=" * 80)
    
    try:
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        
        REPORT_MANAGER.clear()
        STATE_REGISTRY.clear()
        REPORT_MANAGER.set_report_dir(report_dir)
        
        log("创建实验状态...")
        for i in range(2):
            STATE_REGISTRY.add_state({
                'name': f"实验状态{i+1}",
                'type': 'TC12',
                'params': {'α或K': 0.1*(i+1), 'r': 1.0}
            })
        
        log("加载实验数据组...")
        exp_groups = []
        for i, tdms_file in enumerate(tdms_files[:2]):
            data, fs, meta = load_data(tdms_file)
            if data is not None:
                exp_groups.append({
                    'label': f"实验组{i+1}",
                    'data': data,
                    'fs': fs,
                    'meta': meta,
                })
        
        log("加载背景数据组...")
        bg_groups = []
        for i, tdms_file in enumerate(tdms_files[2:]):
            data, fs, meta = load_data(tdms_file)
            if data is not None:
                bg_groups.append({
                    'label': f"背景组{i+1}",
                    'data': data,
                    'fs': fs,
                    'meta': meta,
                })
        
        if not exp_groups or not bg_groups:
            log("未找到有效数据组，跳过Tab7测试")
            return
        
        log("计算背景对消...")
        results = {}
        from signal_processing import BACKGROUND_SUBTRACTION_METHODS, subtract_background
        
        for method in BACKGROUND_SUBTRACTION_METHODS[:2]:
            results[method] = []
            for exp_group, bg_group in zip(exp_groups, bg_groups):
                exp_data = exp_group['data'][:4096]
                bg_data = bg_group['data'][:4096]
                if exp_data.shape[0] == bg_data.shape[0]:
                    result = subtract_background(exp_data, bg_data, method)
                    if result is not None and len(result) > 0:
                        results[method].append(result)
        
        log("生成报告...")
        from experiment_state import ReportBlock
        import matplotlib.pyplot as plt
        from plot_utils import calc_figsize
        
        md_content = f"## 背景对消批处理报告\n\n"
        md_content += "### 实验状态定义\n\n"
        md_content += STATE_REGISTRY.to_markdown_table()
        md_content += "\n"
        
        for method, method_results in results.items():
            md_content += f"### {method}\n\n"
            for i, (exp_group, bg_group, result) in enumerate(zip(exp_groups, bg_groups, method_results)):
                figsize = calc_figsize(3, n_cols=1)
                fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)
                
                t = np.arange(len(exp_group['data'][:1000])) / exp_group.get('fs', 1.0)
                axes[0].plot(t, exp_group['data'][:1000], label='原始')
                axes[0].set_title(f"{exp_group['label']} - 原始信号")
                axes[0].legend()
                
                axes[1].plot(t, bg_group['data'][:1000], label='背景', color='orange')
                axes[1].set_title(f"{bg_group['label']} - 背景信号")
                axes[1].legend()
                
                if len(result) >= 1000:
                    axes[2].plot(t, result[:1000], label='对消后', color='green')
                axes[2].set_title(f"{method} - 对消结果")
                axes[2].legend()
                axes[2].set_xlabel("时间 (s)")
                
                fig.tight_layout()
                path = os.path.join(report_dir, f"tab7_{method}_group{i+1}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                md_content += f"#### {exp_group['label']} vs {bg_group['label']}\n\n![{method}对消](tab7_{method}_group{i+1}.png)\n\n"
        
        block = ReportBlock(
            source_tab='背景对消批处理',
            title="Tab7-背景对消批处理",
            content_md=md_content,
            images=[]
        )
        REPORT_MANAGER.add_block(block)
        
        md_full = REPORT_MANAGER.to_full_markdown()
        report_path = os.path.join(report_dir, 'tab7_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_full)
        
        log(f"Tab7报告生成成功！")
        log(f"报告路径: {report_path}")
        
    except Exception as e:
        log(f"Tab7测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")

def test_tab8(tdms_files, report_dir):
    """测试Tab8通道敏感性分析"""
    log("=" * 80)
    log("测试Tab8: 通道敏感性分析")
    log("=" * 80)
    
    try:
        from channel_sensitivity_tab import ChannelSensitivityTab
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        
        REPORT_MANAGER.clear()
        STATE_REGISTRY.clear()
        REPORT_MANAGER.set_report_dir(report_dir)
        
        log("创建实验状态...")
        STATE_REGISTRY.add_state({
            'name': "实验状态-实验组",
            'type': 'TC12',
            'params': {'alpha': '0.5', 'beta': '1.0'}
        })
        STATE_REGISTRY.add_state({
            'name': "实验状态-背景组",
            'type': 'TC12',
            'params': {'alpha': '0.0', 'beta': '0.0'}
        })
        
        log("创建ChannelSensitivityTab...")
        tab = ChannelSensitivityTab()
        
        log("刷新实验状态...")
        tab.refresh_experiment_states()
        
        basic_tab = tab.subtab_a
        
        log("加载实验数据...")
        exp_file = tdms_files[0]
        bg_file = tdms_files[2]
        
        exp_data, exp_fs, exp_meta = load_data(exp_file)
        bg_data, bg_fs, bg_meta = load_data(bg_file)
        
        if exp_data is not None and bg_data is not None:
            basic_tab.exp_data = exp_data
            basic_tab.exp_meta = {'fs': exp_fs, **exp_meta}
            basic_tab.bg_data = bg_data
            basic_tab.bg_meta = {'fs': bg_fs, **bg_meta}
            
            basic_tab.n_channels = exp_data.shape[1] if exp_data.ndim > 1 else 1
            basic_tab.channels = [f'CH{i+1}' for i in range(basic_tab.n_channels)]
            
            log("计算敏感性...")
            sensitivity_results = []
            
            from scipy import signal, stats
            
            for i in range(min(basic_tab.n_channels, 4)):
                ch_name = basic_tab.channels[i]
                if basic_tab.n_channels > 1:
                    exp_ch_data = exp_data[:, i].flatten()[:4096]
                    bg_ch_data = bg_data[:, i].flatten()[:4096]
                else:
                    exp_ch_data = exp_data.flatten()[:4096]
                    bg_ch_data = bg_data.flatten()[:4096]
                
                corr, _ = stats.pearsonr(exp_ch_data, bg_ch_data)
                
                f_exp, Pxx_exp = signal.welch(exp_ch_data, fs=exp_meta.get('fs', 1000), nperseg=min(len(exp_ch_data), 1024))
                f_bg, Pxx_bg = signal.welch(bg_ch_data, fs=bg_meta.get('fs', 1000), nperseg=min(len(bg_ch_data), 1024))
                
                ka = 1.0 - abs(corr)
                kb = np.mean(Pxx_exp) / np.mean(Pxx_bg) if np.mean(Pxx_bg) > 0 else 1.0
                
                sensitivity_results.append({
                    'channel': ch_name,
                    'exp_data': exp_ch_data,
                    'bg_data': bg_ch_data,
                    'fs': exp_meta.get('fs', 1000),
                    'ka': ka,
                    'kb': kb,
                    'correlation': corr
                })
            
            sensitivity_results.sort(key=lambda x: x['ka'], reverse=True)
            
            basic_tab.sensitivity_results = sensitivity_results
            
            log("生成报告...")
            from experiment_state import ReportBlock
            import matplotlib.pyplot as plt
            from plot_utils import calc_figsize
            
            md_content = f"## 通道敏感性分析报告\n\n"
            md_content += "### 实验状态定义\n\n"
            md_content += STATE_REGISTRY.to_markdown_table()
            md_content += "\n"
            
            md_content += "### 敏感性排序\n\n"
            md_content += "| 排名 | 通道 | Ka指标 | Kb指标 | 相关性 |\n"
            md_content += "|------|------|--------|--------|--------|\n"
            for i, item in enumerate(sensitivity_results, 1):
                md_content += f"| {i} | {item['channel']} | {item['ka']:.6f} | {item['kb']:.6f} | {item['correlation']:.6f} |\n"
            md_content += "\n> **说明**: Ka越大表示敏感性越高（相关性越小，敏感性越高）\n\n"
            
            md_content += "### 时域波形对比（左背景右实验）\n\n"
            for item in sensitivity_results:
                figsize = calc_figsize(2, n_cols=2)
                fig, axes = plt.subplots(1, 2, figsize=figsize)
                
                t = np.linspace(0, len(item['exp_data'])/item['fs'], len(item['exp_data']))
                axes[0].plot(t, item['bg_data'], label='背景组', color='orange')
                axes[0].set_title(f"通道 {item['channel']} - 背景组", fontsize=10)
                axes[0].set_xlabel("时间 (s)", fontsize=8)
                axes[0].legend(fontsize=8)
                
                axes[1].plot(t, item['exp_data'], label='实验组')
                axes[1].set_title(f"通道 {item['channel']} - 实验组", fontsize=10)
                axes[1].set_xlabel("时间 (s)", fontsize=8)
                axes[1].legend(fontsize=8)
                
                fig.tight_layout()
                path = os.path.join(report_dir, f"tab8_time_{item['channel']}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                md_content += f"#### 通道 {item['channel']}\n\n![通道 {item['channel']} 时域](tab8_time_{item['channel']}.png)\n\n"
            
            md_content += "### 频域分析（左背景右实验）\n\n"
            for item in sensitivity_results:
                figsize = calc_figsize(2, n_cols=2)
                fig, axes = plt.subplots(1, 2, figsize=figsize)
                
                from scipy import signal
                f_exp, Pxx_exp = signal.welch(item['exp_data'], fs=item['fs'], nperseg=min(len(item['exp_data']), 1024))
                f_bg, Pxx_bg = signal.welch(item['bg_data'], fs=item['fs'], nperseg=min(len(item['bg_data']), 1024))
                
                axes[0].semilogy(f_bg, Pxx_bg, label='背景组', color='orange')
                axes[0].set_title(f"通道 {item['channel']} - 背景组频谱", fontsize=10)
                axes[0].set_xlabel("频率 (Hz)", fontsize=8)
                axes[0].legend(fontsize=8)
                
                axes[1].semilogy(f_exp, Pxx_exp, label='实验组')
                axes[1].set_title(f"通道 {item['channel']} - 实验组频谱", fontsize=10)
                axes[1].set_xlabel("频率 (Hz)", fontsize=8)
                axes[1].legend(fontsize=8)
                
                fig.tight_layout()
                path = os.path.join(report_dir, f"tab8_freq_{item['channel']}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                md_content += f"#### 通道 {item['channel']}\n\n![通道 {item['channel']} 频域](tab8_freq_{item['channel']}.png)\n\n"
            
            md_content += "### 相关性分析\n\n"
            for item in sensitivity_results:
                figsize = calc_figsize(1, n_cols=1)
                fig, ax = plt.subplots(figsize=figsize)
                
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
                md_content += f"#### 通道 {item['channel']}\n\n![通道 {item['channel']} 相关性](tab8_corr_{item['channel']}.png)\n\n"
            
            block = ReportBlock(
                source_tab='通道敏感性分析',
                title="Tab8-通道敏感性分析",
                content_md=md_content,
                images=[]
            )
            REPORT_MANAGER.add_block(block)
            
            md_full = REPORT_MANAGER.to_full_markdown()
            report_path = os.path.join(report_dir, 'tab8_report.md')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(md_full)
            
            log(f"Tab8报告生成成功！")
            log(f"报告路径: {report_path}")
        else:
            log("数据加载失败，跳过Tab8测试")
        
    except Exception as e:
        log(f"Tab8测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")

if __name__ == '__main__':
    log("=" * 80)
    log("Tab6/7/8完整报告测试开始")
    log("=" * 80)
    
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_all_tabs_output')
    os.makedirs(report_dir, exist_ok=True)
    log(f"报告目录: {report_dir}")
    
    log("查找TDMS文件...")
    tdms_files = find_tdms_files()
    log(f"共使用 {len(tdms_files)} 个TDMS文件")
    
    from experiment_state import REPORT_MANAGER, STATE_REGISTRY
    
    if len(tdms_files) >= 4:
        REPORT_MANAGER.clear()
        STATE_REGISTRY.clear()
        test_tab6(tdms_files, report_dir)
        
        REPORT_MANAGER.clear()
        STATE_REGISTRY.clear()
        test_tab7(tdms_files, report_dir)
        
        REPORT_MANAGER.clear()
        STATE_REGISTRY.clear()
        test_tab8(tdms_files, report_dir)
    else:
        log(f"TDMS文件不足（需要4个），找到{len(tdms_files)}个，跳过测试")
    
    log("=" * 80)
    log("Tab6/7/8完整报告测试结束")
    log("=" * 80)
    
    app.quit()
