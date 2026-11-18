#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
压力测试2：两组数据完整处理流程
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

def main():
    log("=" * 80)
    log("压力测试2：两组数据完整处理流程")
    log("=" * 80)
    
    # 1. 导入模块
    log("步骤1: 导入模块")
    try:
        from PyQt5.QtWidgets import QApplication, QWidget, QTabWidget
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
        return
    
    # 2. 设置报告目录
    log("步骤2: 设置报告目录")
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_report_two')
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
            if len(tdms_files) >= 2:
                break
        if len(tdms_files) >= 2:
            break
    
    if len(tdms_files) < 2:
        log("警告: Z盘TDMS文件不足，使用本地测试文件")
        test_dir = 'Z:/TC1-DC-A-2m-110-270-0625/400K12/2/2/二阶波-Δ2/t2-10ms210ms/0v20ms-20v10ms-22v10ms'
        if os.path.exists(test_dir):
            for f in os.listdir(test_dir):
                if f.endswith('.tdms'):
                    tdms_files.append(os.path.join(test_dir, f))
                if len(tdms_files) >= 2:
                    break
    
    log(f"共找到 {len(tdms_files)} 个TDMS文件")
    if len(tdms_files) < 2:
        log("错误: 无法找到足够的TDMS文件")
        return
    
    file_a_path = tdms_files[0]
    file_b_path = tdms_files[1]
    log(f"数据文件A: {os.path.basename(file_a_path)}")
    log(f"数据文件B: {os.path.basename(file_b_path)}")
    
    # 4. 创建实验状态
    log("步骤4: 创建实验状态")
    STATE_REGISTRY.add_state({
        'name': '状态A',
        'type': 'TC12',
        'params': {'alpha': 0.3, 'kw': 100, 'voltage': 20}
    })
    STATE_REGISTRY.add_state({
        'name': '状态B',
        'type': 'TC12',
        'params': {'alpha': 0.7, 'kw': 200, 'voltage': 30}
    })
    log("实验状态创建成功")
    log("  状态A: α=0.3, KW=100, 电压=20V")
    log("  状态B: α=0.7, KW=200, 电压=30V")
    
    # 5. 加载数据并预处理
    log("步骤5: 加载数据并预处理")
    
    def load_and_preprocess(filepath, label):
        log(f"  加载 {label}: {filepath}")
        result = load_data(filepath)
        
        if result is None or len(result) < 2:
            log(f"  加载失败")
            return None, None, None
        
        data = result[0]
        fs = result[1]
        header = result[2] if len(result) > 2 else {}
        
        if data is None or len(data) == 0:
            log(f"  加载失败")
            return None, None, None
        log(f"  原始数据长度: {len(data)}, 采样率: {fs}")
        
        proc_data = data.copy()
        proc_data = proc_data - np.mean(proc_data)
        proc_data = sp_detrend(proc_data)
        
        from scipy import signal
        if len(proc_data) > 20000:
            proc_data = signal.resample(proc_data, 20000)
        
        log(f"  预处理后长度: {len(proc_data)}")
        return data, proc_data, fs
    
    data_a_raw, data_a, fs_a = load_and_preprocess(file_a_path, '数据A')
    data_b_raw, data_b, fs_b = load_and_preprocess(file_b_path, '数据B')
    
    if data_a is None or data_b is None:
        log("错误: 数据加载失败")
        return
    
    fs = min(fs_a, fs_b)
    log(f"统一采样率: {fs:.0f} Hz")
    
    # 6. 计算时域相似性
    log("步骤6: 计算时域相似性")
    time_methods = [
        '互相关系数', '互相关峰值', '协方差', '欧几里得距离',
        '曼哈顿距离', '余弦相似度', '最大信息系数(MIC)'
    ]
    
    time_results = []
    for method in time_methods:
        try:
            result = compute_time_similarity_batch(data_a, data_b, [method], fs=fs)
            if result and len(result) > 0 and result[0].get('ok', False):
                time_results.append({
                    'method': method,
                    'value': result[0]['value'],
                    'indicators': result[0].get('indicators', {}),
                    'domain': '时域'
                })
                log(f"  {method}: {result[0]['value']:.6f}")
            else:
                log(f"  {method}: 计算失败")
        except Exception as e:
            log(f"  {method}: 异常 - {e}")
    
    log(f"时域计算完成，成功 {len(time_results)}/{len(time_methods)}")
    
    # 7. 计算频域相似性
    log("步骤7: 计算频域相似性")
    freq_methods = [
        '频谱欧几里得距离', '频谱曼哈顿距离', '频谱余弦相似度',
        '频谱皮尔逊相关', '频谱MSE', '频谱RMSE', '频谱MAE',
        '频谱互相关', '频谱能量差', '频谱熵差', '频谱相干性'
    ]
    
    freq_results = []
    for method in freq_methods:
        try:
            result = compute_freq_similarity_batch(data_a, data_b, [method], fs=fs)
            if result and len(result) > 0 and result[0].get('ok', False):
                freq_results.append({
                    'method': method,
                    'value': result[0]['value'],
                    'indicators': result[0].get('indicators', {}),
                    'domain': '频域'
                })
                log(f"  {method}: {result[0]['value']:.6f}")
            else:
                log(f"  {method}: 计算失败")
        except Exception as e:
            log(f"  {method}: 异常 - {e}")
    
    log(f"频域计算完成，成功 {len(freq_results)}/{len(freq_methods)}")
    
    # 8. 可视化
    log("步骤8: 可视化")
    try:
        if data_a.ndim > 1:
            data_a_ch1 = data_a[:, 0]
            data_b_ch1 = data_b[:, 0]
        else:
            data_a_ch1 = data_a
            data_b_ch1 = data_b
        
        t = np.arange(len(data_a_ch1)) / fs
        
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        
        axes[0].plot(t, data_a_ch1, linewidth=0.5, color='C0')
        axes[0].set_title('状态A - 时域波形（通道1）')
        axes[0].set_ylabel('幅值')
        
        axes[1].plot(t, data_b_ch1, linewidth=0.5, color='C1')
        axes[1].set_title('状态B - 时域波形（通道1）')
        axes[1].set_xlabel('时间 (s)')
        axes[1].set_ylabel('幅值')
        
        plt.tight_layout()
        time_waveform_path = os.path.join(report_dir, 'time_waveform.png')
        fig.savefig(time_waveform_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        log(f"时域波形图已保存")
        
        from scipy import signal as sp_signal
        f_a, Pxx_a = sp_signal.welch(data_a_ch1, fs=fs, nperseg=min(len(data_a_ch1), 1024))
        f_b, Pxx_b = sp_signal.welch(data_b_ch1, fs=fs, nperseg=min(len(data_b_ch1), 1024))
        
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        
        axes[0].semilogy(f_a, Pxx_a, linewidth=0.5, color='C0')
        axes[0].set_title('状态A - 频域波形 (Welch PSD，通道1)')
        axes[0].set_ylabel('功率谱密度')
        
        axes[1].semilogy(f_b, Pxx_b, linewidth=0.5, color='C1')
        axes[1].set_title('状态B - 频域波形 (Welch PSD，通道1)')
        axes[1].set_xlabel('频率 (Hz)')
        axes[1].set_ylabel('功率谱密度')
        
        plt.tight_layout()
        freq_waveform_path = os.path.join(report_dir, 'freq_waveform.png')
        fig.savefig(freq_waveform_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        log(f"频域波形图已保存")
        
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(f_a, Pxx_a, linewidth=0.6, color='C0', label='状态A')
        ax.plot(f_b, Pxx_b, linewidth=0.6, color='C1', label='状态B')
        ax.set_xlabel('频率 (Hz)')
        ax.set_ylabel('功率谱密度')
        ax.set_title('两组数据频域对比（通道1）')
        ax.legend()
        plt.tight_layout()
        freq_compare_path = os.path.join(report_dir, 'freq_compare.png')
        fig.savefig(freq_compare_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        log(f"频域对比图已保存")
        
        log("可视化完成")
    except Exception as e:
        log(f"可视化失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")
    
    # 9. 生成报告
    log("步骤9: 生成报告")
    try:
        md_content = "# 两组数据对比实验报告\n\n"
        md_content += f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md_content += f"**数据文件A**: {os.path.basename(file_a_path)}\n\n"
        md_content += f"**数据文件B**: {os.path.basename(file_b_path)}\n\n"
        md_content += f"**采样频率**: {fs:.0f} Hz\n\n"
        md_content += f"**数据长度**: {len(data_a)} 点\n\n"
        md_content += f"**实验状态A**: α=0.3, KW=100, 电压=20V\n\n"
        md_content += f"**实验状态B**: α=0.7, KW=200, 电压=30V\n\n"
        md_content += f"---\n\n"
        
        md_content += "## 第一章：时域分析\n\n"
        md_content += "### 1.1 时域波形对比\n\n"
        md_content += "![时域波形对比](time_waveform.png)\n\n"
        
        md_content += "### 1.2 时域相似性计算结果\n\n"
        md_content += "| 算法 | 相似性值 |\n"
        md_content += "|------|----------|\n"
        for r in time_results:
            val = r.get('value', 0)
            if isinstance(val, (int, float)):
                md_content += f"| {r['method']} | {val:.6f} |\n"
            else:
                md_content += f"| {r['method']} | {val} |\n"
        md_content += "\n"
        
        md_content += "---\n\n"
        
        md_content += "## 第二章：频域分析\n\n"
        md_content += "### 2.1 频域波形对比\n\n"
        md_content += "![频域波形对比](freq_waveform.png)\n\n"
        
        md_content += "### 2.2 频域叠加对比\n\n"
        md_content += "![频域叠加对比](freq_compare.png)\n\n"
        md_content += f"**频域变换算法**: Welch功率谱密度估计（使用FFT计算）\n\n"
        
        md_content += "### 2.3 频域相似性计算结果\n\n"
        md_content += "| 算法 | 相似性值 |\n"
        md_content += "|------|----------|\n"
        for r in freq_results:
            val = r.get('value', 0)
            if isinstance(val, (int, float)):
                md_content += f"| {r['method']} | {val:.6f} |\n"
            else:
                md_content += f"| {r['method']} | {val} |\n"
        md_content += "\n"
        
        md_content += "---\n\n"
        
        md_content += "## 第三章：矩阵分析\n\n"
        md_content += "### 3.1 时域相似度矩阵（2×2）\n\n"
        md_content += "| | 状态A | 状态B |\n"
        md_content += "|----|-------|-------|\n"
        
        time_similarity = {}
        for r in time_results:
            time_similarity[r['method']] = r['value']
        
        md_content += f"| 状态A | 1.0000 | {time_similarity.get('互相关系数', 0):.4f} |\n"
        md_content += f"| 状态B | {time_similarity.get('互相关系数', 0):.4f} | 1.0000 |\n"
        md_content += "\n"
        md_content += "**注**: 以上矩阵使用互相关系数作为相似度指标\n\n"
        
        md_content += "### 3.2 频域相似度矩阵（2×2）\n\n"
        md_content += "| | 状态A | 状态B |\n"
        md_content += "|----|-------|-------|\n"
        
        freq_similarity = {}
        for r in freq_results:
            freq_similarity[r['method']] = r['value']
        
        md_content += f"| 状态A | 1.0000 | {freq_similarity.get('频谱余弦相似度', 0):.4f} |\n"
        md_content += f"| 状态B | {freq_similarity.get('频谱余弦相似度', 0):.4f} | 1.0000 |\n"
        md_content += "\n"
        md_content += "**注**: 以上矩阵使用频谱余弦相似度作为相似度指标\n\n"
        
        md_content += "### 3.3 各算法相似度汇总\n\n"
        md_content += "| 算法类型 | 算法名称 | 相似性值 |\n"
        md_content += "|----------|----------|----------|\n"
        for r in time_results:
            val = r.get('value', 0)
            if isinstance(val, (int, float)):
                md_content += f"| 时域 | {r['method']} | {val:.4f} |\n"
            else:
                md_content += f"| 时域 | {r['method']} | {val} |\n"
        for r in freq_results:
            val = r.get('value', 0)
            if isinstance(val, (int, float)):
                md_content += f"| 频域 | {r['method']} | {val:.4f} |\n"
            else:
                md_content += f"| 频域 | {r['method']} | {val} |\n"
        md_content += "\n"
        
        block = ReportBlock(
            source_tab='两组数据对比',
            title='两组数据完整对比报告',
            content_md=md_content
        )
        REPORT_MANAGER.add_block(block)
        log("报告BLOCK添加成功")
        
        report_path = os.path.join(report_dir, 'test_report_two.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        log(f"完整报告已保存: {report_path}")
        
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        log(f"报告长度: {len(content)} 字符")
        log(f"报告包含表格: {'|' in content}")
        log(f"报告包含图片: {'!' in content and '[' in content}")
        
    except Exception as e:
        log(f"报告生成失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")
    
    # 10. 检查输出文件
    log("步骤10: 检查输出文件")
    png_count = 0
    md_count = 0
    for f in os.listdir(report_dir):
        if f.endswith('.png'):
            size_kb = os.path.getsize(os.path.join(report_dir, f)) / 1024
            log(f"  {f}: {size_kb:.2f} KB")
            png_count += 1
        elif f.endswith('.md'):
            md_count += 1
    log(f"PNG图片数量: {png_count}")
    log(f"MD文件数量: {md_count}")
    
    log("=" * 80)
    log("压力测试2结束")
    log("=" * 80)

if __name__ == '__main__':
    main()
