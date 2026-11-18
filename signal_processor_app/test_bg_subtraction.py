#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
背景对消批处理Tab压力测试：测试9组数据的背景对消功能
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
    log("背景对消批处理Tab压力测试")
    log("=" * 80)
    
    log("步骤1: 导入模块")
    try:
        from experiment_state import STATE_REGISTRY, REPORT_MANAGER, ReportBlock
        from file_reader import load_data
        from signal_processing import (
            compute_time_similarity_batch,
            compute_freq_similarity_batch,
            subtract_background,
            BACKGROUND_SUBTRACTION_METHODS
        )
        from scipy.signal import detrend as sp_detrend
        log("模块导入成功")
        log(f"可用背景对消算法: {BACKGROUND_SUBTRACTION_METHODS}")
    except Exception as e:
        log(f"模块导入失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")
        return
    
    log("步骤2: 设置报告目录")
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_bg_subtraction')
    os.makedirs(report_dir, exist_ok=True)
    REPORT_MANAGER.set_report_dir(report_dir)
    log(f"报告目录: {report_dir}")
    
    log("步骤3: 查找TDMS文件")
    tdms_files = []
    for root, dirs, files in os.walk('Z:/'):
        for f in files:
            if f.endswith('.tdms'):
                tdms_files.append(os.path.join(root, f))
            if len(tdms_files) >= 10:
                break
        if len(tdms_files) >= 10:
            break
    
    if len(tdms_files) < 2:
        log("错误: Z盘TDMS文件不足")
        return
    
    log(f"共找到 {len(tdms_files)} 个TDMS文件")
    
    log("步骤4: 创建实验状态")
    for i in range(9):
        STATE_REGISTRY.add_state({
            'name': f'状态α{i+1}',
            'type': 'TC12',
            'params': {'alpha': 0.1 * (i + 1), 'kw': 100 + i * 20, 'voltage': 20 + i * 2}
        })
    log("9种实验状态创建成功")
    
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
    
    log(f"成功加载 {len(groups)} 组实验数据")
    
    if len(groups) < 2:
        log("错误: 实验数据不足")
        return
    
    log("步骤6: 加载背景数据")
    bg_filepath = tdms_files[-1]
    bg_data_raw, bg_data_proc, bg_fs = load_and_preprocess(bg_filepath, 9)
    
    if bg_data_proc is None:
        log("错误: 背景数据加载失败")
        return
    
    log(f"背景数据: {len(bg_data_raw)} -> {len(bg_data_proc)} 点, fs={bg_fs:.0f}")
    
    for group in groups:
        group['bg_data'] = bg_data_proc.copy()
        group['bg_fs'] = bg_fs
        group['bg_filepath'] = bg_filepath
    
    for i, group in enumerate(groups):
        exp_fs = group['fs']
        bg_fs = group['bg_fs']
        if abs(exp_fs - bg_fs) > 1:
            log(f"警告: 数据组 {group['label']} 采样率不匹配 (实验={exp_fs:.0f}, 背景={bg_fs:.0f})")
    
    log("步骤7: 测试背景对消算法")
    
    bg_methods_to_test = ['直接相减', '归一化相减']
    log(f"测试算法: {bg_methods_to_test}")
    
    all_results_by_method = {}
    heatmap_results_by_method = {}
    
    for bg_method in bg_methods_to_test:
        log(f"=" * 60)
        log(f"测试背景对消算法: {bg_method}")
        log(f"=" * 60)
        
        subtracted_groups = []
        for group in groups:
            try:
                subtracted_data = subtract_background(group['proc_data'], group['bg_data'], method=bg_method)
                subtracted_groups.append({
                    'label': group['label'],
                    'data': subtracted_data,
                    'fs': group['fs'],
                    'filepath': group['filepath'],
                    'bg_filepath': group['bg_filepath']
                })
                log(f"  {group['label']}: 对消完成, 长度={len(subtracted_data)}")
            except Exception as e:
                log(f"  {group['label']}: 对消失败 - {e}")
        
        time_methods_batch = ['互相关系数', '互相关峰值', '协方差']
        freq_methods_batch = ['频谱余弦相似度', '频谱皮尔逊相关', '频谱相干性']
        
        all_results = []
        heatmap_results = {}
        
        for method in time_methods_batch:
            heatmap_results[f"{method}（时域）"] = np.zeros((len(subtracted_groups), len(subtracted_groups)))
        for method in freq_methods_batch:
            heatmap_results[f"{method}（频域）"] = np.zeros((len(subtracted_groups), len(subtracted_groups)))
        
        labels = [g['label'] for g in subtracted_groups]
        fs_ref = subtracted_groups[0]['fs']
        
        log(f"开始计算 {len(subtracted_groups)}×{len(subtracted_groups)} 两两相似性")
        
        for i, gi in enumerate(subtracted_groups):
            for j, gj in enumerate(subtracted_groups):
                data_i = gi['data']
                data_j = gj['data']
                
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
        
        all_results_by_method[bg_method] = all_results
        heatmap_results_by_method[bg_method] = heatmap_results
    
    log("步骤8: 生成报告")
    
    for bg_method in bg_methods_to_test:
        all_results = all_results_by_method[bg_method]
        heatmap_results = heatmap_results_by_method[bg_method]
        
        batch_data_info = {
            '数据组数': len(groups),
            '参数标签': ', '.join([g['label'] for g in groups]),
            '采样频率': f"{groups[0]['fs']:.0f} Hz",
            '计算类型': '时域+频域',
            '时域算法': ', '.join(['互相关系数', '互相关峰值', '协方差']),
            '频域算法': ', '.join(['频谱余弦相似度', '频谱皮尔逊相关', '频谱相干性']),
            '频域变换算法': 'Welch功率谱密度估计（使用FFT计算）',
            '背景对消算法': bg_method,
            '背景数据文件': os.path.basename(bg_filepath)
        }
        
        batch_sections = []
        
        batch_sections.append("## 实验状态列表\n\n")
        batch_sections.append("| 编号 | 标签 | α值 | KW值 | 电压 | 实验数据文件 | 背景数据文件 |\n")
        batch_sections.append("|------|------|-----|------|------|--------------|--------------|\n")
        for i, group in enumerate(groups):
            alpha = 0.1 * (i + 1)
            kw = 100 + i * 20
            voltage = 20 + i * 2
            exp_filename = os.path.basename(group['filepath'])
            bg_filename = os.path.basename(group.get('bg_filepath', ''))
            batch_sections.append(f"| {i+1} | {group['label']} | {alpha:.1f} | {kw} | {voltage}V | {exp_filename} | {bg_filename} |\n")
        batch_sections.append("\n")
        
        labels = [g['label'] for g in groups]
        t = np.arange(len(groups[0]['proc_data'])) / groups[0]['fs']
        
        fig, axes = plt.subplots(len(groups), 1, figsize=(10, len(groups)*1.2), sharex=True)
        if len(groups) == 1:
            axes = [axes]
        for idx, (group, ax) in enumerate(zip(groups, axes)):
            subtracted_data = subtract_background(group['proc_data'], group['bg_data'], method=bg_method)
            ax.plot(t[:len(subtracted_data)], subtracted_data, linewidth=0.5, color=f'C{idx}')
            ax.set_ylabel(group['label'], fontsize=8)
        axes[-1].set_xlabel('时间 (s)')
        fig.suptitle(f'9组数据时域波形对比（{bg_method}后）', y=0.98)
        plt.tight_layout()
        batch_time_path = os.path.join(report_dir, f'bg_{bg_method}_time_waveform.png')
        fig.savefig(batch_time_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        batch_sections.append("## 第一章：时域分析（背景对消后）\n\n")
        batch_sections.append("### 1.1 时域波形堆叠图\n\n")
        batch_sections.append(f"![时域波形](bg_{bg_method}_time_waveform.png)\n\n")
        
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
        
        batch_sections.append("### 1.3 时域相似度矩阵（9×9）\n\n")
        for method in ['互相关系数', '互相关峰值', '协方差']:
            key = f"{method}（时域）"
            if key in heatmap_results:
                batch_sections.append(generate_matrix_table(labels, heatmap_results[key], method, "时域", method))
        
        from scipy import signal as sp_signal
        
        fig, axes = plt.subplots(len(groups), 1, figsize=(10, len(groups)*1.2), sharex=True)
        if len(groups) == 1:
            axes = [axes]
        for idx, (group, ax) in enumerate(zip(groups, axes)):
            subtracted_data = subtract_background(group['proc_data'], group['bg_data'], method=bg_method)
            f, Pxx = sp_signal.welch(subtracted_data, fs=group['fs'], nperseg=min(len(subtracted_data), 1024))
            ax.semilogy(f, Pxx, linewidth=0.5, color=f'C{idx}')
            ax.set_ylabel(group['label'], fontsize=8)
        axes[-1].set_xlabel('频率 (Hz)')
        fig.suptitle(f'9组数据频域波形对比（{bg_method}后）', y=0.98)
        plt.tight_layout()
        batch_freq_path = os.path.join(report_dir, f'bg_{bg_method}_freq_waveform.png')
        fig.savefig(batch_freq_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        batch_sections.append("## 第二章：频域分析（背景对消后）\n\n")
        batch_sections.append("### 2.1 频域波形堆叠图\n\n")
        batch_sections.append(f"![频域波形](bg_{bg_method}_freq_waveform.png)\n\n")
        
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
        
        batch_sections.append("### 2.3 频域相似度矩阵（9×9）\n\n")
        for method in ['频谱余弦相似度', '频谱皮尔逊相关', '频谱相干性']:
            key = f"{method}（频域）"
            if key in heatmap_results:
                batch_sections.append(generate_matrix_table(labels, heatmap_results[key], method, "频域", method))
        
        batch_sections.append("## 第三章：热力图可视化（背景对消后）\n\n")
        for alg_name, heatmap_data in heatmap_results.items():
            fig, ax = plt.subplots(figsize=(8, 6))
            im = ax.imshow(heatmap_data, cmap='viridis')
            ax.set_xticks(range(len(labels)))
            ax.set_yticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
            ax.set_yticklabels(labels, fontsize=8)
            ax.set_title(f"{alg_name}相似度热力图（{bg_method}后）")
            plt.colorbar(im)
            plt.tight_layout()
            heatmap_path = os.path.join(report_dir, f"bg_{bg_method}_heatmap_{alg_name}.png")
            fig.savefig(heatmap_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
            batch_sections.append(f"### {alg_name}热力图\n\n")
            batch_sections.append(f"![{alg_name}热力图](bg_{bg_method}_heatmap_{alg_name}.png)\n\n")
        
        batch_md = generate_report_md(f"背景对消批处理报告（{bg_method}）", batch_data_info, batch_sections)
        batch_block = ReportBlock(
            source_tab='背景对消批处理',
            title=f'背景对消-{bg_method}-9组数据',
            content_md=batch_md
        )
        REPORT_MANAGER.add_block(batch_block)
        log(f"背景对消报告BLOCK({bg_method})添加成功")
    
    md_content_full = REPORT_MANAGER.to_full_markdown()
    report_path = os.path.join(report_dir, 'test_bg_subtraction_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_content_full)
    log(f"完整报告已保存: {report_path}")
    
    log("步骤9: 检查输出文件")
    png_count = 0
    for f in os.listdir(report_dir):
        if f.endswith('.png'):
            size_kb = os.path.getsize(os.path.join(report_dir, f)) / 1024
            log(f"  {f}: {size_kb:.2f} KB")
            png_count += 1
    log(f"PNG图片数量: {png_count}")
    log(f"MD文件数量: 1")
    
    log("=" * 80)
    log("背景对消批处理压力测试结束")
    log("=" * 80)

if __name__ == '__main__':
    main()
