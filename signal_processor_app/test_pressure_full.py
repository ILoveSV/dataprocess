#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整压力测试：Tab1、Tab2和批量处理Tab的报告生成
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
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['font.size'] = 10
plt.rcParams['legend.fontsize'] = 8
plt.rcParams['xtick.labelsize'] = 8
plt.rcParams['ytick.labelsize'] = 8

def log(msg):
    print(f"[TEST] {msg}")

def generate_report_md(title, data_info, sections):
    md_content = f"# {title}\n\n"
    md_content += f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for key, value in data_info.items():
        md_content += f"**{key}**: {value}\n\n"
    
    md_content += "---\n\n"
    
    for section in sections:
        md_content += f"{section}\n\n"
    
    return md_content

def generate_matrix_table(labels, matrix, title, domain, method):
    md = f"#### {title}（{domain}）\n\n"
    md += f"**算法**: {method}\n\n"
    md += "| | " + " | ".join(labels) + " |\n"
    md += "|-" + "|-".join(["-"*3 for _ in labels]) + "|\n"
    for i, label_i in enumerate(labels):
        row = [f"{matrix[i,j]:.4f}" for j in range(len(labels))]
        md += f"| {label_i} | " + " | ".join(row) + " |\n"
    md += "\n"
    return md

def main():
    log("=" * 80)
    log("完整压力测试：Tab1、Tab2和批量处理Tab报告生成")
    log("=" * 80)
    
    # 1. 导入模块
    log("步骤1: 导入模块")
    try:
        from experiment_state import STATE_REGISTRY, REPORT_MANAGER, ReportBlock
        from file_reader import load_data
        from signal_processing import (
            compute_time_similarity_batch,
            compute_freq_similarity_batch
        )
        from scipy.signal import detrend as sp_detrend
        log("模块导入成功")
    except Exception as e:
        log(f"模块导入失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")
        return
    
    # 2. 设置报告目录
    log("步骤2: 设置报告目录")
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_report_full')
    os.makedirs(report_dir, exist_ok=True)
    REPORT_MANAGER.set_report_dir(report_dir)
    log(f"报告目录: {report_dir}")
    
    # 3. 查找TDMS文件
    log("步骤3: 查找TDMS文件")
    tdms_files = []
    for root, dirs, files in os.walk('Z:/'):
        for f in files:
            if f.endswith('.tdms'):
                tdms_files.append(os.path.join(root, f))
            if len(tdms_files) >= 9:
                break
        if len(tdms_files) >= 9:
            break
    
    if len(tdms_files) < 9:
        log("警告: Z盘TDMS文件不足")
    
    log(f"共找到 {len(tdms_files)} 个TDMS文件")
    
    # 4. 创建实验状态
    log("步骤4: 创建实验状态")
    for i in range(9):
        STATE_REGISTRY.add_state({
            'name': f'状态α{i+1}',
            'type': 'TC12',
            'params': {'alpha': 0.1 * (i + 1), 'kw': 100 + i * 20, 'voltage': 20 + i * 2}
        })
    log("9种实验状态创建成功")
    
    # 5. 加载数据并预处理
    log("步骤5: 加载数据并预处理")
    
    def load_and_preprocess(filepath, idx):
        try:
            result = load_data(filepath)
            if result is None or len(result) < 2:
                return None, None, None
            
            data = result[0]
            fs = result[1]
            
            if data.ndim > 1:
                data = data[:, 0]
            
            proc_data = data.copy()
            proc_data = proc_data - np.mean(proc_data)
            proc_data = sp_detrend(proc_data)
            
            from scipy import signal
            if len(proc_data) > 10000:
                proc_data = signal.resample(proc_data, 10000)
            
            log(f"  数据组α{idx+1}: {len(data)} -> {len(proc_data)} 点, fs={fs:.0f}")
            return data, proc_data, fs
        except Exception as e:
            log(f"  数据组α{idx+1}加载失败: {e}")
            return None, None, None
    
    groups = []
    for i, filepath in enumerate(tdms_files[:9]):
        data_raw, data_proc, fs = load_and_preprocess(filepath, i)
        if data_proc is not None:
            groups.append({
                'label': f"α{i+1}",
                'data': data_raw,
                'proc_data': data_proc,
                'fs': fs,
                'filepath': filepath
            })
    
    log(f"成功加载 {len(groups)} 组数据")
    
    if len(groups) < 2:
        log("错误: 数据不足")
        return
    
    # ===== Tab1: 两组数据时域处理 =====
    log("=" * 60)
    log("Tab1: 两组数据时域处理")
    log("=" * 60)
    
    group_a = groups[0]
    group_b = groups[4]
    
    time_methods = ['互相关系数', '互相关峰值', '协方差', '余弦相似度', '欧几里得距离']
    tab1_results = []
    
    for method in time_methods:
        try:
            result = compute_time_similarity_batch(group_a['proc_data'], group_b['proc_data'], [method], fs=group_a['fs'])
            if result and len(result) > 0 and result[0].get('ok', False):
                tab1_results.append({
                    'method': method,
                    'value': result[0]['value'],
                    'domain': '时域'
                })
                log(f"  {method}: {result[0]['value']:.6f}")
        except Exception as e:
            log(f"  {method}: 失败 - {e}")
    
    # Tab1报告生成
    tab1_data_info = {
        '数据文件A': os.path.basename(group_a['filepath']),
        '数据文件B': os.path.basename(group_b['filepath']),
        '采样频率': f"{group_a['fs']:.0f} Hz",
        '实验状态A': f"α={group_a['label']}, KW=100, 电压=20V",
        '实验状态B': f"α={group_b['label']}, KW=180, 电压=28V"
    }
    
    tab1_sections = []
    
    tab1_sections.append("## 实验状态列表\n\n")
    tab1_sections.append("| 编号 | 标签 | α值 | KW值 | 电压 | 数据文件 |\n")
    tab1_sections.append("|------|------|-----|------|------|----------|\n")
    tab1_sections.append(f"| 1 | {group_a['label']} | 0.1 | 100 | 20V | {os.path.basename(group_a['filepath'])} |\n")
    tab1_sections.append(f"| 2 | {group_b['label']} | 0.5 | 180 | 28V | {os.path.basename(group_b['filepath'])} |\n")
    tab1_sections.append("\n")
    
    t = np.arange(len(group_a['proc_data'])) / group_a['fs']
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    axes[0].plot(t, group_a['proc_data'], linewidth=0.5, color='C0')
    axes[0].set_title('状态A - 时域波形')
    axes[1].plot(t, group_b['proc_data'], linewidth=0.5, color='C1')
    axes[1].set_title('状态B - 时域波形')
    axes[1].set_xlabel('时间 (s)')
    plt.tight_layout()
    tab1_waveform_path = os.path.join(report_dir, 'tab1_waveform.png')
    fig.savefig(tab1_waveform_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    tab1_sections.append("## 第一章：时域波形对比\n\n")
    tab1_sections.append("![时域波形](tab1_waveform.png)\n\n")
    
    tab1_sections.append("## 第二章：时域相似性计算结果\n\n")
    tab1_sections.append("| 算法 | 相似性值 |\n")
    tab1_sections.append("|------|----------|\n")
    for r in tab1_results:
        val = r.get('value', 0)
        if isinstance(val, (int, float)):
            tab1_sections.append(f"| {r['method']} | {val:.6f} |\n")
        else:
            tab1_sections.append(f"| {r['method']} | {val} |\n")
    tab1_sections.append("\n")
    
    tab1_sections.append("## 第三章：相似度矩阵（2×2）\n\n")
    tab1_sections.append("### 互相关系数矩阵\n\n")
    corr_val = next((r['value'] for r in tab1_results if r['method'] == '互相关系数'), 0)
    tab1_sections.append("| | 状态A | 状态B |\n")
    tab1_sections.append("|----|-------|-------|\n")
    tab1_sections.append(f"| 状态A | 1.0000 | {corr_val:.4f} |\n")
    tab1_sections.append(f"| 状态B | {corr_val:.4f} | 1.0000 |\n")
    tab1_sections.append("\n")
    
    tab1_md = generate_report_md("Tab1: 两组数据时域对比报告", tab1_data_info, tab1_sections)
    tab1_block = ReportBlock(
        source_tab='两组数据时域处理',
        title='Tab1-两组数据时域对比',
        content_md=tab1_md
    )
    REPORT_MANAGER.add_block(tab1_block)
    log("Tab1报告BLOCK添加成功")
    
    # ===== Tab2: 两组数据频域处理 =====
    log("=" * 60)
    log("Tab2: 两组数据频域处理")
    log("=" * 60)
    
    freq_methods = ['频谱余弦相似度', '频谱皮尔逊相关', '频谱欧几里得距离', '频谱能量差']
    tab2_results = []
    
    for method in freq_methods:
        try:
            result = compute_freq_similarity_batch(group_a['proc_data'], group_b['proc_data'], [method], fs=group_a['fs'])
            if result and len(result) > 0 and result[0].get('ok', False):
                tab2_results.append({
                    'method': method,
                    'value': result[0]['value'],
                    'domain': '频域'
                })
                log(f"  {method}: {result[0]['value']:.6f}")
        except Exception as e:
            log(f"  {method}: 失败 - {e}")
    
    # Tab2报告生成
    tab2_data_info = {
        '数据文件A': os.path.basename(group_a['filepath']),
        '数据文件B': os.path.basename(group_b['filepath']),
        '采样频率': f"{group_a['fs']:.0f} Hz",
        '频域变换算法': 'Welch功率谱密度估计（使用FFT计算）',
        '实验状态A': f"α={group_a['label']}, KW=100, 电压=20V",
        '实验状态B': f"α={group_b['label']}, KW=180, 电压=28V"
    }
    
    tab2_sections = []
    
    tab2_sections.append("## 实验状态列表\n\n")
    tab2_sections.append("| 编号 | 标签 | α值 | KW值 | 电压 | 数据文件 |\n")
    tab2_sections.append("|------|------|-----|------|------|----------|\n")
    tab2_sections.append(f"| 1 | {group_a['label']} | 0.1 | 100 | 20V | {os.path.basename(group_a['filepath'])} |\n")
    tab2_sections.append(f"| 2 | {group_b['label']} | 0.5 | 180 | 28V | {os.path.basename(group_b['filepath'])} |\n")
    tab2_sections.append("\n")
    
    from scipy import signal as sp_signal
    f_a, Pxx_a = sp_signal.welch(group_a['proc_data'], fs=group_a['fs'], nperseg=min(len(group_a['proc_data']), 1024))
    f_b, Pxx_b = sp_signal.welch(group_b['proc_data'], fs=group_b['fs'], nperseg=min(len(group_b['proc_data']), 1024))
    
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    axes[0].semilogy(f_a, Pxx_a, linewidth=0.5, color='C0')
    axes[0].set_title('状态A - 频域波形')
    axes[1].semilogy(f_b, Pxx_b, linewidth=0.5, color='C1')
    axes[1].set_title('状态B - 频域波形')
    axes[1].set_xlabel('频率 (Hz)')
    plt.tight_layout()
    tab2_spectrum_path = os.path.join(report_dir, 'tab2_spectrum.png')
    fig.savefig(tab2_spectrum_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(f_a, Pxx_a, linewidth=0.6, color='C0', label='状态A')
    ax.plot(f_b, Pxx_b, linewidth=0.6, color='C1', label='状态B')
    ax.set_xlabel('频率 (Hz)')
    ax.set_title('频域叠加对比')
    ax.legend()
    plt.tight_layout()
    tab2_compare_path = os.path.join(report_dir, 'tab2_compare.png')
    fig.savefig(tab2_compare_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    tab2_sections.append("## 第一章：频域波形对比\n\n")
    tab2_sections.append("![频域波形](tab2_spectrum.png)\n\n")
    tab2_sections.append("![频域叠加对比](tab2_compare.png)\n\n")
    
    tab2_sections.append("## 第二章：频域相似性计算结果\n\n")
    tab2_sections.append("| 算法 | 相似性值 |\n")
    tab2_sections.append("|------|----------|\n")
    for r in tab2_results:
        val = r.get('value', 0)
        if isinstance(val, (int, float)):
            tab2_sections.append(f"| {r['method']} | {val:.6f} |\n")
        else:
            tab2_sections.append(f"| {r['method']} | {val} |\n")
    tab2_sections.append("\n")
    
    tab2_sections.append("## 第三章：相似度矩阵（2×2）\n\n")
    tab2_sections.append("### 频谱余弦相似度矩阵\n\n")
    cos_val = next((r['value'] for r in tab2_results if r['method'] == '频谱余弦相似度'), 0)
    tab2_sections.append("| | 状态A | 状态B |\n")
    tab2_sections.append("|----|-------|-------|\n")
    tab2_sections.append(f"| 状态A | 1.0000 | {cos_val:.4f} |\n")
    tab2_sections.append(f"| 状态B | {cos_val:.4f} | 1.0000 |\n")
    tab2_sections.append("\n")
    
    tab2_md = generate_report_md("Tab2: 两组数据频域对比报告", tab2_data_info, tab2_sections)
    tab2_block = ReportBlock(
        source_tab='两组数据频域处理',
        title='Tab2-两组数据频域对比',
        content_md=tab2_md
    )
    REPORT_MANAGER.add_block(tab2_block)
    log("Tab2报告BLOCK添加成功")
    
    # ===== 批量处理Tab =====
    log("=" * 60)
    log("批量处理Tab: 9组数据对比")
    log("=" * 60)
    
    time_methods_batch = ['互相关系数', '互相关峰值', '协方差']
    freq_methods_batch = ['频谱余弦相似度', '频谱皮尔逊相关', '频谱相干性']
    
    all_results = []
    heatmap_results = {}
    
    for method in time_methods_batch:
        heatmap_results[f"{method}（时域）"] = np.zeros((len(groups), len(groups)))
    for method in freq_methods_batch:
        heatmap_results[f"{method}（频域）"] = np.zeros((len(groups), len(groups)))
    
    labels = [g['label'] for g in groups]
    fs_ref = groups[0]['fs']
    
    log(f"开始计算 {len(groups)}×{len(groups)} 两两相似性")
    
    for i, gi in enumerate(groups):
        for j, gj in enumerate(groups):
            data_i = gi['proc_data']
            data_j = gj['proc_data']
            
            for method in time_methods_batch:
                try:
                    result = compute_time_similarity_batch(data_i, data_j, [method], fs=fs_ref)
                    if result and len(result) > 0 and result[0].get('ok', False):
                        val = result[0]['value']
                        all_results.append({
                            'method': method, 'value': val, 'group_a': gi['label'], 
                            'group_b': gj['label'], 'domain': '时域'
                        })
                        heatmap_results[f"{method}（时域）"][i, j] = val
                except Exception as e:
                    log(f"  时域 {method}({gi['label']},{gj['label']}) 失败: {e}")
            
            for method in freq_methods_batch:
                try:
                    result = compute_freq_similarity_batch(data_i, data_j, [method], fs=fs_ref)
                    if result and len(result) > 0 and result[0].get('ok', False):
                        val = result[0]['value']
                        all_results.append({
                            'method': method, 'value': val, 'group_a': gi['label'], 
                            'group_b': gj['label'], 'domain': '频域'
                        })
                        heatmap_results[f"{method}（频域）"][i, j] = val
                except Exception as e:
                    log(f"  频域 {method}({gi['label']},{gj['label']}) 失败: {e}")
    
    log(f"计算完成，共 {len(all_results)} 个结果")
    
    # 批量处理报告生成
    batch_data_info = {
        '数据组数': len(groups),
        '参数标签': ', '.join(labels),
        '采样频率': f"{fs_ref:.0f} Hz",
        '计算类型': '时域+频域',
        '时域算法': ', '.join(time_methods_batch),
        '频域算法': ', '.join(freq_methods_batch),
        '频域变换算法': 'Welch功率谱密度估计（使用FFT计算）'
    }
    
    batch_sections = []
    
    batch_sections.append("## 实验状态列表\n\n")
    batch_sections.append("| 编号 | 标签 | α值 | KW值 | 电压 | 数据文件 |\n")
    batch_sections.append("|------|------|-----|------|------|----------|\n")
    for i, group in enumerate(groups):
        alpha = 0.1 * (i + 1)
        kw = 100 + i * 20
        voltage = 20 + i * 2
        filename = os.path.basename(group['filepath'])
        batch_sections.append(f"| {i+1} | {group['label']} | {alpha:.1f} | {kw} | {voltage}V | {filename} |\n")
    batch_sections.append("\n")
    
    # 时域波形堆叠图
    fig, axes = plt.subplots(len(groups), 1, figsize=(10, len(groups)*1.2), sharex=True)
    if len(groups) == 1:
        axes = [axes]
    for idx, (group, ax) in enumerate(zip(groups, axes)):
        ax.plot(t, group['proc_data'], linewidth=0.5, color=f'C{idx}')
        ax.set_ylabel(group['label'], fontsize=8)
    axes[-1].set_xlabel('时间 (s)')
    fig.suptitle('9组数据时域波形对比', y=0.98)
    plt.tight_layout()
    batch_time_path = os.path.join(report_dir, 'batch_time_waveform.png')
    fig.savefig(batch_time_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    batch_sections.append("## 第一章：时域分析\n\n")
    batch_sections.append("### 1.1 时域波形堆叠图\n\n")
    batch_sections.append("![时域波形](batch_time_waveform.png)\n\n")
    
    # 时域结果表格
    batch_sections.append("### 1.2 时域相似性计算结果\n\n")
    batch_sections.append("| 算法 | 组A | 组B | 值 |\n")
    batch_sections.append("|------|-----|-----|----|\n")
    time_results = [r for r in all_results if r.get('domain') == '时域']
    for r in time_results[:30]:
        val = r.get('value', 0)
        if isinstance(val, (int, float)):
            batch_sections.append(f"| {r['method']} | {r['group_a']} | {r['group_b']} | {val:.6f} |\n")
        else:
            batch_sections.append(f"| {r['method']} | {r['group_a']} | {r['group_b']} | {val} |\n")
    batch_sections.append("\n")
    
    # 时域9×9矩阵表格
    batch_sections.append("### 1.3 时域相似度矩阵（9×9）\n\n")
    for method in time_methods_batch:
        key = f"{method}（时域）"
        if key in heatmap_results:
            batch_sections.append(generate_matrix_table(labels, heatmap_results[key], method, "时域", method))
    
    # 频域波形堆叠图
    fig, axes = plt.subplots(len(groups), 1, figsize=(10, len(groups)*1.2), sharex=True)
    if len(groups) == 1:
        axes = [axes]
    for idx, (group, ax) in enumerate(zip(groups, axes)):
        f, Pxx = sp_signal.welch(group['proc_data'], fs=group['fs'], nperseg=min(len(group['proc_data']), 1024))
        ax.semilogy(f, Pxx, linewidth=0.5, color=f'C{idx}')
        ax.set_ylabel(group['label'], fontsize=8)
    axes[-1].set_xlabel('频率 (Hz)')
    fig.suptitle('9组数据频域波形对比', y=0.98)
    plt.tight_layout()
    batch_freq_path = os.path.join(report_dir, 'batch_freq_waveform.png')
    fig.savefig(batch_freq_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    batch_sections.append("## 第二章：频域分析\n\n")
    batch_sections.append("### 2.1 频域波形堆叠图\n\n")
    batch_sections.append("![频域波形](batch_freq_waveform.png)\n\n")
    
    # 频域结果表格
    batch_sections.append("### 2.2 频域相似性计算结果\n\n")
    batch_sections.append("| 算法 | 组A | 组B | 值 |\n")
    batch_sections.append("|------|-----|-----|----|\n")
    freq_results = [r for r in all_results if r.get('domain') == '频域']
    for r in freq_results[:30]:
        val = r.get('value', 0)
        if isinstance(val, (int, float)):
            batch_sections.append(f"| {r['method']} | {r['group_a']} | {r['group_b']} | {val:.6f} |\n")
        else:
            batch_sections.append(f"| {r['method']} | {r['group_a']} | {r['group_b']} | {val} |\n")
    batch_sections.append("\n")
    
    # 频域9×9矩阵表格
    batch_sections.append("### 2.3 频域相似度矩阵（9×9）\n\n")
    for method in freq_methods_batch:
        key = f"{method}（频域）"
        if key in heatmap_results:
            batch_sections.append(generate_matrix_table(labels, heatmap_results[key], method, "频域", method))
    
    # 热力图
    batch_sections.append("## 第三章：热力图可视化\n\n")
    for alg_name, heatmap_data in heatmap_results.items():
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(heatmap_data, cmap='viridis')
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_title(f"{alg_name}相似度热力图")
        plt.colorbar(im)
        plt.tight_layout()
        heatmap_path = os.path.join(report_dir, f"batch_heatmap_{alg_name}.png")
        fig.savefig(heatmap_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        batch_sections.append(f"### {alg_name}热力图\n\n")
        batch_sections.append(f"![{alg_name}热力图](batch_heatmap_{alg_name}.png)\n\n")
    
    batch_md = generate_report_md("批量参数对比报告", batch_data_info, batch_sections)
    batch_block = ReportBlock(
        source_tab='批量参数对比',
        title='批量对比-9组数据',
        content_md=batch_md
    )
    REPORT_MANAGER.add_block(batch_block)
    log("批量处理报告BLOCK添加成功")
    
    # 保存完整报告
    md_content_full = REPORT_MANAGER.to_full_markdown()
    report_path = os.path.join(report_dir, 'test_report_full.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content_full)
    log(f"完整报告已保存: {report_path}")
    
    # 检查输出文件
    log("步骤6: 检查输出文件")
    png_count = 0
    for f in os.listdir(report_dir):
        if f.endswith('.png'):
            size_kb = os.path.getsize(os.path.join(report_dir, f)) / 1024
            log(f"  {f}: {size_kb:.2f} KB")
            png_count += 1
    log(f"PNG图片数量: {png_count}")
    log(f"MD文件数量: 1")
    
    log("=" * 80)
    log("完整压力测试结束")
    log("=" * 80)

if __name__ == '__main__':
    main()
