#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全面GUI功能检查程序：测试批量处理Tab的完整功能
"""
import sys
import os
import numpy as np
import time
import json

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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui_debug.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [GUI_TEST] {msg}\n")
    print(f"[GUI_TEST] {msg}", flush=True)

def main():
    log("=" * 80)
    log("全面GUI功能检查程序启动")
    log("=" * 80)
    
    try:
        # 1. 导入模块
        log("步骤1: 导入PyQt5和项目模块")
        from PyQt5.QtWidgets import QApplication, QWidget
        app = QApplication(sys.argv)
        
        from main import BatchCompareTab, ComputeWorker
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        from signal_processing import (
            compute_time_similarity_batch, compute_freq_similarity_batch
        )
        log("模块导入成功")
        
        # 2. 设置报告目录
        log("步骤2: 设置报告目录")
        report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_gui_report')
        os.makedirs(report_dir, exist_ok=True)
        REPORT_MANAGER.set_report_dir(report_dir)
        log(f"报告目录: {report_dir}")
        
        # 3. 查找TDMS文件
        log("步骤3: 查找TDMS文件")
        tdms_files = []
        
        z_paths = [
            r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\1\不放电",
            r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\1\放电",
            r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\2\不放电",
            r"Z:\16路测试\板卡a\AB1-AB2-CB1-CB2\线组1\2\放电",
            r"Z:\16路测试\板卡a\AC\线组1\1\不放电",
            r"Z:\16路测试\板卡a\AC\线组1\1\放电",
            r"Z:\16路测试\板卡a\AC\线组1\2\不放电",
            r"Z:\16路测试\板卡a\AC\线组1\2\放电",
            r"Z:\16路测试\板卡b\AB1-AB2-CB1-CB2\线组1\1\不放电",
        ]
        
        for path in z_paths:
            try:
                if os.path.exists(path):
                    files = [f for f in os.listdir(path) if f.endswith('.tdms')]
                    if files:
                        tdms_files.append(os.path.join(path, files[0]))
                        log(f"  找到: {os.path.basename(files[0])}")
            except Exception as e:
                log(f"  路径错误: {path} - {e}")
        
        if len(tdms_files) < 9:
            log(f"警告: 仅找到 {len(tdms_files)} 个文件，复制补齐")
            while len(tdms_files) < 9:
                tdms_files.append(tdms_files[-1])
        
        log(f"共找到 {len(tdms_files)} 个TDMS文件")
        
        # 4. 创建实验状态
        log("步骤4: 创建实验状态")
        alpha_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        for i, alpha in enumerate(alpha_values):
            STATE_REGISTRY.add_state({
                'name': f"α{i+1}={alpha}",
                'type': 'TC12',
                'params': {'α或K': alpha, 'r': 1.0}
            })
        log("9种实验状态创建成功")
        
        # 5. 创建BatchCompareTab
        log("步骤5: 创建批量处理Tab")
        tab = BatchCompareTab()
        
        # 6. 添加数据组
        log("步骤6: 添加9组数据")
        for i, filepath in enumerate(tdms_files[:9]):
            data_array, fs, meta = load_data(filepath)
            
            start_idx = 0
            end_idx = min(int(0.5 * fs), len(data_array))
            proc_data = data_array[start_idx:end_idx]
            
            from scipy import signal
            if len(proc_data) > 10000:
                proc_data = signal.resample(proc_data, 10000)
            
            tab.groups.append({
                'label': f"α{i+1}",
                'filepath': filepath,
                'data': data_array,
                'meta': meta,
                'fs': fs,
                'proc_data': proc_data,
                'proc_meta': {
                    'fs': fs,
                    'channel_map': meta.get('channel_map', {})
                }
            })
            tab.group_list.addItem(f"α{i+1}: {os.path.basename(filepath)}")
            log(f"  添加数据组 α{i+1}: {len(proc_data)} 点, fs={fs}")
        
        tab.update_channel_combo()
        tab.compute_btn.setEnabled(True)
        log(f"共添加 {len(tab.groups)} 组数据")
        
        # 7. 选择算法（完整测试）
        log("步骤7: 选择算法")
        tab.calc_type_combo.setCurrentText("时域+频域")
        
        time_methods = ['互相关系数', '互相关峰值', '协方差', '皮尔逊相关系数']
        freq_methods = ['频谱余弦相似度', '频谱皮尔逊相关', '频谱欧几里得距离', '频谱相干性']
        
        for j in range(tab.time_method_list.count()):
            item = tab.time_method_list.item(j)
            item.setSelected(item.text() in time_methods)
        
        for j in range(tab.freq_method_list.count()):
            item = tab.freq_method_list.item(j)
            item.setSelected(item.text() in freq_methods)
        
        log(f"选中时域算法: {time_methods}")
        log(f"选中频域算法: {freq_methods}")
        
        # 8. 构建计算任务
        log("步骤8: 构建计算任务")
        
        def compute_task(progress_cb):
            all_results = []
            heatmap_results = {}
            
            for method in time_methods:
                heatmap_results[f"{method}（时域）"] = np.zeros((len(tab.groups), len(tab.groups)))
            for method in freq_methods:
                heatmap_results[f"{method}（频域）"] = np.zeros((len(tab.groups), len(tab.groups)))
            
            all_methods = time_methods + freq_methods
            total = len(all_methods) * len(tab.groups) * len(tab.groups)
            done = 0
            
            log(f"开始计算 {len(tab.groups)}×{len(tab.groups)} 两两相似性")
            log(f"总任务数: {total}")
            
            for i, group_i in enumerate(tab.groups):
                for j, group_j in enumerate(tab.groups):
                    data_i = tab.get_channel_data(group_i, 'CH1')
                    data_j = tab.get_channel_data(group_j, 'CH1')
                    
                    if data_i is None or data_j is None:
                        done += len(all_methods)
                        continue
                    
                    for method in time_methods:
                        try:
                            result = compute_time_similarity_batch(data_i, data_j, [method], fs=group_i['fs'])
                            
                            if result and len(result) > 0 and result[0].get('ok', False):
                                value = result[0]['value']
                                
                                all_results.append({
                                    'method': method,
                                    'value': value,
                                    'group_a': group_i['label'],
                                    'group_b': group_j['label'],
                                    'channel': 'CH1',
                                    'domain': '时域'
                                })
                                
                                heatmap_results[f"{method}（时域）"][i, j] = value
                        except Exception as e:
                            log(f"  [ERROR] 时域 {method}({group_i['label']},{group_j['label']}): {e}")
                        
                        done += 1
                        if progress_cb and done % 50 == 0:
                            progress_cb(done, total, method, f"时域-{group_i['label']}-{group_j['label']}")
                    
                    for method in freq_methods:
                        try:
                            result = compute_freq_similarity_batch(data_i, data_j, [method], fs=group_i['fs'])
                            
                            if result and len(result) > 0 and result[0].get('ok', False):
                                value = result[0]['value']
                                
                                all_results.append({
                                    'method': method,
                                    'value': value,
                                    'group_a': group_i['label'],
                                    'group_b': group_j['label'],
                                    'channel': 'CH1',
                                    'domain': '频域'
                                })
                                
                                heatmap_results[f"{method}（频域）"][i, j] = value
                        except Exception as e:
                            log(f"  [ERROR] 频域 {method}({group_i['label']},{group_j['label']}): {e}")
                        
                        done += 1
                        if progress_cb and done % 50 == 0:
                            progress_cb(done, total, method, f"频域-{group_i['label']}-{group_j['label']}")
            
            log(f"计算完成，共 {len(all_results)} 个结果")
            return all_results, heatmap_results, ['CH1'], "时域+频域"
        
        worker = ComputeWorker(compute_task)
        
        # 9. 处理计算结果
        def on_finished(result):
            log("步骤9: 处理计算结果")
            
            if result is None:
                log("计算结果为空")
                app.quit()
                return
            
            if len(result) == 4:
                all_results, heatmap_results, channels, calc_type = result
            else:
                all_results, heatmap_results, channels = result
                calc_type = "时域"
            
            tab.result_data = all_results
            tab.heatmap_results = heatmap_results
            tab._channels = channels
            tab._calc_type = calc_type
            
            log(f"计算结果数量: {len(all_results)}")
            log(f"热力图结果: {list(heatmap_results.keys())}")
            
            # 10. 生成完整报告
            log("步骤10: 生成完整报告")
            try:
                from experiment_state import ReportBlock
                
                labels = [g['label'] for g in tab.groups]
                md_content = f"# 批量参数对比报告\n\n"
                md_content += f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                
                md_content += "## 实验状态列表\n\n"
                md_content += "| 编号 | 标签 | α值 | KW值 | 电压 | 数据文件 |\n"
                md_content += "|------|------|-----|------|------|----------|\n"
                for i, group in enumerate(tab.groups):
                    alpha = 0.1 * (i + 1)
                    kw = 100 + i * 20
                    voltage = 20 + i * 2
                    filename = os.path.basename(group['filepath'])
                    md_content += f"| {i+1} | {group['label']} | {alpha:.1f} | {kw} | {voltage}V | {filename} |\n"
                md_content += "\n"
                
                md_content += "## 实验信息\n\n"
                md_content += f"| 参数 | 值 |\n"
                md_content += f"|------|----|\n"
                md_content += f"| 数据组数 | {len(labels)} |\n"
                md_content += f"| 参数标签 | {', '.join(labels)} |\n"
                md_content += f"| 采样频率 | {tab.groups[0]['fs']:.0f} Hz |\n"
                md_content += f"| 计算类型 | {calc_type} |\n"
                md_content += f"| 时域算法 | {', '.join(time_methods)} |\n"
                md_content += f"| 频域算法 | {', '.join(freq_methods)} |\n"
                md_content += f"| 频域变换算法 | Welch功率谱密度估计（使用FFT计算） |\n"
                md_content += "\n"
                
                # 时域波形堆叠图
                log("  生成时域波形图...")
                num_groups = len(tab.groups)
                fig_height = num_groups * 1.2
                fig, axes = plt.subplots(num_groups, 1, figsize=(10, fig_height), sharex=True)
                if num_groups == 1:
                    axes = [axes]
                
                for idx, (group, ax) in enumerate(zip(tab.groups, axes)):
                    data = tab.get_channel_data(group, 'CH1')
                    if data is not None:
                        t = np.arange(len(data)) / group['fs']
                        ax.plot(t, data, linewidth=0.6, color=f'C{idx}')
                    ax.set_ylabel(group['label'], fontsize=8)
                    ax.tick_params(axis='both', labelsize=6)
                
                axes[-1].set_xlabel('时间 (s)')
                fig.suptitle('9组数据时域波形对比（通道CH1）', y=0.98)
                plt.tight_layout()
                plt.subplots_adjust(top=0.95)
                
                waveform_path = os.path.join(report_dir, "batch_waveform_CH1.png")
                fig.savefig(waveform_path, dpi=100, bbox_inches='tight')
                plt.close(fig)
                md_content += "## 第一章：时域分析\n\n"
                md_content += "### 1.1 时域波形堆叠图\n\n"
                md_content += f"![时域波形](batch_waveform_CH1.png)\n\n"
                
                # 时域相似性表格
                time_results = [r for r in all_results if r.get('domain') == '时域']
                if time_results:
                    md_content += "### 1.2 时域相似性计算结果\n\n"
                    md_content += "| 算法 | 组A | 组B | 值 |\n"
                    md_content += "|------|-----|-----|----|\n"
                    for r in time_results[:30]:
                        val = r.get('value', 0)
                        if isinstance(val, (int, float)):
                            md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                        else:
                            md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                    md_content += "\n"
                
                # 时域9×9矩阵表格
                md_content += "### 1.3 时域相似度矩阵（9×9）\n\n"
                for method in time_methods:
                    key = f"{method}（时域）"
                    if key in heatmap_results:
                        md_content += f"#### {method}\n\n"
                        md_content += "| | " + " | ".join(labels) + " |\n"
                        md_content += "|-" + "|-".join(["-"*3 for _ in labels]) + "|\n"
                        for i, label_i in enumerate(labels):
                            row = [f"{heatmap_results[key][i,j]:.4f}" for j in range(len(labels))]
                            md_content += f"| {label_i} | " + " | ".join(row) + " |\n"
                        md_content += "\n"
                
                # 频域波形堆叠图
                log("  生成频域波形图...")
                from scipy import signal as sp_signal
                fig, axes = plt.subplots(num_groups, 1, figsize=(10, fig_height), sharex=True)
                if num_groups == 1:
                    axes = [axes]
                
                for idx, (group, ax) in enumerate(zip(tab.groups, axes)):
                    data = tab.get_channel_data(group, 'CH1')
                    if data is not None:
                        f, Pxx = sp_signal.welch(data, fs=group['fs'], nperseg=min(len(data), 1024))
                        ax.semilogy(f, Pxx, linewidth=0.6, color=f'C{idx}')
                    ax.set_ylabel(group['label'], fontsize=8)
                    ax.tick_params(axis='both', labelsize=6)
                
                axes[-1].set_xlabel('频率 (Hz)')
                fig.suptitle('9组数据频域波形对比（通道CH1）', y=0.98)
                plt.tight_layout()
                plt.subplots_adjust(top=0.95)
                
                freq_path = os.path.join(report_dir, "batch_freq_CH1.png")
                fig.savefig(freq_path, dpi=100, bbox_inches='tight')
                plt.close(fig)
                md_content += "## 第二章：频域分析\n\n"
                md_content += "### 2.1 频域波形堆叠图\n\n"
                md_content += f"![频域波形](batch_freq_CH1.png)\n\n"
                
                # 频域相似性表格
                freq_results = [r for r in all_results if r.get('domain') == '频域']
                if freq_results:
                    md_content += "### 2.2 频域相似性计算结果\n\n"
                    md_content += "| 算法 | 组A | 组B | 值 |\n"
                    md_content += "|------|-----|-----|----|\n"
                    for r in freq_results[:30]:
                        val = r.get('value', 0)
                        if isinstance(val, (int, float)):
                            md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                        else:
                            md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                    md_content += "\n"
                
                # 频域9×9矩阵表格
                md_content += "### 2.3 频域相似度矩阵（9×9）\n\n"
                for method in freq_methods:
                    key = f"{method}（频域）"
                    if key in heatmap_results:
                        md_content += f"#### {method}\n\n"
                        md_content += "| | " + " | ".join(labels) + " |\n"
                        md_content += "|-" + "|-".join(["-"*3 for _ in labels]) + "|\n"
                        for i, label_i in enumerate(labels):
                            row = [f"{heatmap_results[key][i,j]:.4f}" for j in range(len(labels))]
                            md_content += f"| {label_i} | " + " | ".join(row) + " |\n"
                        md_content += "\n"
                
                # 热力图
                md_content += "## 第三章：热力图可视化\n\n"
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
                    
                    md_content += f"### {alg_name}热力图\n\n"
                    md_content += f"![{alg_name}热力图](batch_heatmap_{alg_name}.png)\n\n"
                
                # 创建报告块
                block = ReportBlock(
                    source_tab='批量参数对比',
                    title=f"批量对比-{', '.join(labels)}",
                    content_md=md_content
                )
                REPORT_MANAGER.add_block(block)
                log("报告BLOCK添加成功")
                
                # 保存完整报告
                md_content_full = REPORT_MANAGER.to_full_markdown()
                report_path = os.path.join(report_dir, 'test_gui_report.md')
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(md_content_full)
                log(f"完整报告已保存: {report_path}")
                
                # 11. 检查输出文件
                log("步骤11: 检查输出文件")
                files = os.listdir(report_dir)
                png_files = [f for f in files if f.endswith('.png')]
                md_files = [f for f in files if f.endswith('.md')]
                
                log(f"PNG图片数量: {len(png_files)}")
                log(f"MD文件数量: {len(md_files)}")
                
                for png in png_files:
                    png_path = os.path.join(report_dir, png)
                    if os.path.exists(png_path):
                        size = os.path.getsize(png_path)
                        log(f"  {png}: {size/1024:.2f} KB")
                
                log("=" * 80)
                log("全面GUI功能检查程序结束")
                log("=" * 80)
                
                app.quit()
                
            except Exception as e:
                log(f"报告生成失败: {e}")
                import traceback
                log(f"堆栈跟踪: {traceback.format_exc()}")
                app.quit()
        
        def on_error(err):
            log(f"计算错误: {err}")
            app.quit()
        
        worker.finished_ok.connect(on_finished)
        worker.error.connect(on_error)
        
        worker.start()
        
        app.exec_()
        
    except Exception as e:
        log(f"测试失败: {e}")
        import traceback
        log(f"堆栈跟踪: {traceback.format_exc()}")

if __name__ == '__main__':
    main()
