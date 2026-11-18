#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版全尺度测试脚本：验证批量处理和报告生成流程
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

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'full_test.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(f"[TEST] {msg}", flush=True)

def main():
    log("=" * 80)
    log("全尺度测试开始")
    log("=" * 80)
    
    try:
        # 1. 导入模块
        log("步骤1: 导入模块")
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from main import BatchCompareTab, ComputeWorker
        from experiment_state import REPORT_MANAGER, STATE_REGISTRY
        from file_reader import load_data
        log("模块导入成功")
        
        # 2. 设置报告目录
        log("步骤2: 设置报告目录")
        report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_report_output')
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
            except Exception:
                pass
        
        if len(tdms_files) < 9:
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
        log("实验状态创建成功")
        
        # 5. 创建BatchCompareTab
        log("步骤5: 创建批量处理Tab")
        tab = BatchCompareTab()
        
        # 6. 添加数据组（手动添加，不调用UI方法）
        log("步骤6: 添加数据组")
        for i, filepath in enumerate(tdms_files[:9]):
            data_array, fs, meta = load_data(filepath)
            
            # 直接截取数据，不使用UI预处理
            start_idx = 0
            end_idx = min(int(0.5 * fs), len(data_array))
            proc_data = data_array[start_idx:end_idx]
            
            # 降采样到10000点
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
            log(f"  添加数据组 {i+1}: {len(proc_data)} 点, fs={fs}")
        
        tab.update_channel_combo()
        tab.compute_btn.setEnabled(True)
        log(f"共添加 {len(tab.groups)} 组数据")
        
        # 7. 选择算法并计算
        log("步骤7: 选择算法并计算")
        
        # 设置计算类型为时域
        tab.calc_type_combo.setCurrentText("时域")
        
        # 只选择前3种算法
        for j in range(tab.time_method_list.count()):
            item = tab.time_method_list.item(j)
            item.setSelected(j < 3)
        
        # 获取选中的算法和通道（同时包含时域和频域）
        time_methods = ['互相关系数', '互相关峰值', '协方差']
        freq_methods = ['频谱余弦相似度', '频谱皮尔逊相关', '频谱相干性']
        channels = ['CH1']
        
        # 构建计算任务（同时计算时域和频域）
        def compute_task(progress_cb):
            all_results = []
            heatmap_results = {}
            
            for method in time_methods:
                heatmap_results[f"{method}（时域）"] = np.zeros((len(tab.groups), len(tab.groups)))
            for method in freq_methods:
                heatmap_results[f"{method}（频域）"] = np.zeros((len(tab.groups), len(tab.groups)))
            
            all_methods = time_methods + freq_methods
            total = len(channels) * len(all_methods) * len(tab.groups) * len(tab.groups)
            done = 0
            
            for ch in channels:
                for i, group_i in enumerate(tab.groups):
                    for j, group_j in enumerate(tab.groups):
                        data_i = tab.get_channel_data(group_i, ch)
                        data_j = tab.get_channel_data(group_j, ch)
                        
                        if data_i is None or data_j is None:
                            done += len(all_methods)
                            continue
                        
                        # 时域计算
                        for method in time_methods:
                            try:
                                from signal_processing import compute_time_similarity_batch
                                result = compute_time_similarity_batch(
                                    data_i, data_j, [method], fs=group_i['fs']
                                )
                                
                                if result and len(result) > 0 and result[0].get('ok', False):
                                    value = result[0]['value']
                                    indicators = result[0].get('indicators', {})
                                    
                                    all_results.append({
                                        'method': method,
                                        'value': value,
                                        'indicators': indicators,
                                        'group_a': group_i['label'],
                                        'group_b': group_j['label'],
                                        'channel': ch,
                                        'data_a': data_i,
                                        'data_b': data_j,
                                        'fs': group_i['fs'],
                                        'domain': '时域'
                                    })
                                    
                                    if ch == channels[0]:
                                        heatmap_results[f"{method}（时域）"][i, j] = value
                            except Exception as e:
                                log(f"[Batch] 时域计算 {ch}:{method}({group_i['label']}, {group_j['label']}) 失败: {e}")
                            
                            done += 1
                            if progress_cb:
                                progress_cb(done, total, method, f"时域-{group_i['label']}-{group_j['label']}")
                        
                        # 频域计算
                        for method in freq_methods:
                            try:
                                from signal_processing import compute_freq_similarity_batch
                                result = compute_freq_similarity_batch(
                                    data_i, data_j, [method], fs=group_i['fs']
                                )
                                
                                if result and len(result) > 0 and result[0].get('ok', False):
                                    value = result[0]['value']
                                    indicators = result[0].get('indicators', {})
                                    
                                    all_results.append({
                                        'method': method,
                                        'value': value,
                                        'indicators': indicators,
                                        'group_a': group_i['label'],
                                        'group_b': group_j['label'],
                                        'channel': ch,
                                        'data_a': data_i,
                                        'data_b': data_j,
                                        'fs': group_i['fs'],
                                        'domain': '频域'
                                    })
                                    
                                    if ch == channels[0]:
                                        heatmap_results[f"{method}（频域）"][i, j] = value
                            except Exception as e:
                                log(f"[Batch] 频域计算 {ch}:{method}({group_i['label']}, {group_j['label']}) 失败: {e}")
                            
                            done += 1
                            if progress_cb:
                                progress_cb(done, total, method, f"频域-{group_i['label']}-{group_j['label']}")
            
            return all_results, heatmap_results, channels, "时域+频域"
        
        worker = ComputeWorker(compute_task)
        
        def on_finished(result):
            if result is not None:
                log(f"计算结果长度: {len(result)}")
                if len(result) == 4:
                    all_results, heatmap_results, channels, calc_type = result
                else:
                    all_results, heatmap_results, channels = result
                    calc_type = "时域"
                
                tab.result_data = all_results
                tab.heatmap_results = heatmap_results
                tab._channels = channels
                tab._calc_type = calc_type
                log(f"计算完成，结果数量: {len(all_results)}")
                log(f"热力图结果: {list(heatmap_results.keys())}")
                
                # 8. 可视化
                log("步骤8: 可视化")
                try:
                    tab.waveform_mode_combo.setCurrentText("时域波形")
                    tab.visualize_waveforms()
                    log("时域波形可视化成功")
                    
                    tab.waveform_mode_combo.setCurrentText("频域波形")
                    tab.visualize_waveforms()
                    log("频域波形可视化成功")
                except Exception as e:
                    log(f"可视化失败: {e}")
                    import traceback
                    log(f"堆栈跟踪: {traceback.format_exc()}")
                
                # 9. 生成报告
                log("步骤9: 生成报告")
                try:
                    from experiment_state import ReportBlock, REPORT_MANAGER
                    
                    labels = [g['label'] for g in tab.groups]
                    md_content = f"## 批量参数对比报告\n\n"
                    md_content += f"**数据组数**: {len(labels)}\n\n"
                    md_content += f"**参数标签**: {', '.join(labels)}\n\n"
                    md_content += f"**计算类型**: {calc_type}\n\n"
                    md_content += f"**采样频率**: {tab.groups[0]['fs']:.0f} Hz\n\n"
                    md_content += f"**时域相似性算法**: 互相关系数、互相关峰值、协方差\n\n"
                    md_content += f"**频域变换算法**: Welch功率谱密度估计（使用FFT计算）\n\n"
                    
                    log("保存时域波形堆叠图...")
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
                        if idx < num_groups - 1:
                            ax.set_xlabel('')
                    
                    axes[-1].set_xlabel('时间 (s)')
                    fig.suptitle('9组数据时域波形对比（通道CH1，横纵比4:1）', y=0.98)
                    plt.tight_layout()
                    plt.subplots_adjust(top=0.95)
                    
                    waveform_path = os.path.join(report_dir, f"batch_waveform_CH1.png")
                    fig.savefig(waveform_path, dpi=100, bbox_inches='tight')
                    plt.close(fig)
                    log(f"时域波形图已保存: {waveform_path}")
                    md_content += f"### 时域波形堆叠图（通道: CH1）\n\n"
                    md_content += f"![时域波形](batch_waveform_CH1.png)\n\n"
                    
                    log("保存频域波形堆叠图...")
                    fig, axes = plt.subplots(num_groups, 1, figsize=(10, fig_height), sharex=True)
                    if num_groups == 1:
                        axes = [axes]
                    
                    for idx, (group, ax) in enumerate(zip(tab.groups, axes)):
                        data = tab.get_channel_data(group, 'CH1')
                        if data is not None:
                            from scipy import signal as sp_signal
                            f, Pxx = sp_signal.welch(data, fs=group['fs'], nperseg=min(len(data), 1024))
                            ax.semilogy(f, Pxx, linewidth=0.6, color=f'C{idx}')
                        ax.set_ylabel(group['label'], fontsize=8)
                        ax.tick_params(axis='both', labelsize=6)
                        if idx < num_groups - 1:
                            ax.set_xlabel('')
                    
                    axes[-1].set_xlabel('频率 (Hz)')
                    fig.suptitle('9组数据频域波形对比（通道CH1，横纵比4:1）', y=0.98)
                    plt.tight_layout()
                    plt.subplots_adjust(top=0.95)
                    
                    freq_path = os.path.join(report_dir, f"batch_freq_CH1.png")
                    fig.savefig(freq_path, dpi=100, bbox_inches='tight')
                    plt.close(fig)
                    log(f"频域波形图已保存: {freq_path}")
                    md_content += f"### 频域波形堆叠图（通道: CH1）\n\n"
                    md_content += f"![频域波形](batch_freq_CH1.png)\n\n"
                    
                    log("保存热力图...")
                    freq_transform_method = "Welch功率谱密度估计（FFT）"
                    
                    for alg_name, heatmap_data in heatmap_results.items():
                        fig, ax = plt.subplots(figsize=(8, 6))
                        im = ax.imshow(heatmap_data, cmap='viridis', vmin=np.min(heatmap_data), vmax=np.max(heatmap_data))
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
                        log(f"热力图已保存: {heatmap_path}")
                        
                        md_content += f"### {alg_name}相似度热力图\n\n"
                        md_content += f"![{alg_name}热力图](batch_heatmap_{alg_name}.png)\n\n"
                    
                    # 时域结果表格（前20条）
                    time_results = [r for r in all_results if r.get('domain') == '时域']
                    if time_results:
                        md_content += "### 时域相似性计算结果（部分示例）\n\n"
                        md_content += f"**数据域**: 时域原始信号\n\n"
                        md_content += "| 算法 | 组A | 组B | 值 |\n"
                        md_content += "|------|-----|-----|----|\n"
                        for r in time_results[:20]:
                            val = r.get('value', 0)
                            if isinstance(val, (int, float)):
                                md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                            else:
                                md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                        md_content += "\n"
                    
                    # 频域结果表格（前20条）
                    freq_results = [r for r in all_results if r.get('domain') == '频域']
                    if freq_results:
                        md_content += "### 频域相似性计算结果（部分示例）\n\n"
                        md_content += f"**数据域**: 频域（{freq_transform_method}）\n\n"
                        md_content += "| 算法 | 组A | 组B | 值 |\n"
                        md_content += "|------|-----|-----|----|\n"
                        for r in freq_results[:20]:
                            val = r.get('value', 0)
                            if isinstance(val, (int, float)):
                                md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                            else:
                                md_content += f"| {r.get('method', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                        md_content += "\n"
                    
                    # 相似度矩阵汇总表格（按时域/频域分组）
                    md_content += "### 相似度矩阵汇总\n\n"
                    
                    md_content += "#### 时域相似度矩阵\n\n"
                    md_content += f"**数据域**: 时域原始信号\n\n"
                    for alg_name, heatmap_data in heatmap_results.items():
                        if "时域" in alg_name:
                            md_content += f"##### {alg_name}\n\n"
                            md_content += "| | " + " | ".join(labels) + " |\n"
                            md_content += "|-" + "|-".join(["-"*3 for _ in labels]) + "|\n"
                            for i, label_i in enumerate(labels):
                                row = [f"{heatmap_data[i,j]:.4f}" for j in range(len(labels))]
                                md_content += f"| {label_i} | " + " | ".join(row) + " |\n"
                            md_content += "\n"
                    
                    md_content += "#### 频域相似度矩阵\n\n"
                    md_content += f"**数据域**: 频域（{freq_transform_method}）\n\n"
                    for alg_name, heatmap_data in heatmap_results.items():
                        if "频域" in alg_name:
                            md_content += f"##### {alg_name}\n\n"
                            md_content += "| | " + " | ".join(labels) + " |\n"
                            md_content += "|-" + "|-".join(["-"*3 for _ in labels]) + "|\n"
                            for i, label_i in enumerate(labels):
                                row = [f"{heatmap_data[i,j]:.4f}" for j in range(len(labels))]
                                md_content += f"| {label_i} | " + " | ".join(row) + " |\n"
                            md_content += "\n"
                    
                    # 创建报告块（不传递images参数，图片已在content_md中正确引用）
                    block = ReportBlock(
                        source_tab='批量参数对比',
                        title=f"批量对比-{', '.join(labels)}",
                        content_md=md_content
                    )
                    REPORT_MANAGER.add_block(block)
                    log("报告BLOCK添加成功")
                    
                    # 保存完整报告
                    md_content_full = REPORT_MANAGER.to_full_markdown()
                    report_path = os.path.join(report_dir, 'test_report.md')
                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(md_content_full)
                    log(f"完整报告已保存: {report_path}")
                    
                    # 检查报告内容
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
                    else:
                        log(f"  {png}: 文件不存在")
                
                log("=" * 80)
                log("全尺度测试结束")
                log("=" * 80)
                
                # 退出应用
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