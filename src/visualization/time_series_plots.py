#====================================================================
# File Name: time_series_analysis.py
# Project Name: dataprocess
# Description:
# 1、按组进行综合分析：GROUP1、GROUP2等文件夹内的文件集合分析
# 2、原始信号质量评估：各通道电压时序图、稳定性分析、通道一致性对比
# 3、生成组级别的综合分析报告和图表
#====================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import os
import yaml
import logging
from scipy import stats
import json
from datetime import datetime


plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

logger = logging.getLogger('data_process')

def load_config():
    """加载配置文件"""
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config

def read_csv_data(csv_file_path):
    """读取CSV文件数据"""
    try:
        logger.info(f"正在读取CSV文件: {csv_file_path}")
        
        try:
            df = pd.read_csv(csv_file_path)
        except Exception as e:
            logger.warning(f"快速读取失败，尝试使用python引擎: {str(e)}")
            df = pd.read_csv(csv_file_path, engine='python')

        time_column = 'time'
        channel_columns = [col for col in df.columns if col.startswith('channel')]
        
        if time_column not in df.columns:
          raise ValueError("CSV文件中缺少'time'列")
        if channel_columns not in df.colunms:
          raise ValueError("CSV文件中缺少以'channel'开头的列")

        logger.info(f"成功读取数据: {len(df)} 行, {len(channel_columns)} 个通道")
        return df, time_column, channel_columns
    
    except Exception as e:
        logger.error(f"读取CSV文件失败 {csv_file_path}: {str(e)}")
        raise

def calculate_basic_statistics(df, channel_columns):
    """计算基础统计量"""
    stats_results = {}
    
    for channel in channel_columns:
        data = df[channel].dropna()
        
        stats_results[channel] = {
            'mean': float(np.mean(data)),
            'std': float(np.std(data)),
            'rms': float(np.sqrt(np.mean(data**2))),  # RMS值
            'max': float(np.max(data)),
            'min': float(np.min(data)),
            'peak_to_peak': float(np.max(data) - np.min(data)),
            'variance': float(np.var(data)),
            'skewness': float(stats.skew(data)),
            'kurtosis': float(stats.kurtosis(data)),
            'signal_to_noise_ratio': float(np.abs(np.mean(data)) / np.std(data)) if np.std(data) > 0 else 0.0
        }
    
    return stats_results

def analyze_signal_stability(df, channel_columns, time_column):
    """分析信号稳定性"""
    stability_results = {}
    
    # 将时间转换为数值（秒）
    time_seconds = pd.to_numeric(df[time_column], errors='coerce')
    valid_indices = ~time_seconds.isna()
    time_seconds = time_seconds[valid_indices]
    
    total_duration = time_seconds.iloc[-1] - time_seconds.iloc[0] if len(time_seconds) > 1 else 0
    
    for channel in channel_columns:
        data = df[channel].dropna()
        if len(data) > len(time_seconds):
            data = data.iloc[:len(time_seconds)]
        elif len(time_seconds) > len(data):
            time_seconds_adj = time_seconds.iloc[:len(data)]
        else:
            time_seconds_adj = time_seconds
        
        # 1. 线性漂移分析
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(time_seconds_adj, data)
        except:
            # 如果线性回归失败，使用默认值
            slope, r_value = 0.0, 0.0
        
        # 2. 分段稳定性分析（将数据分为4段）
        segment_length = len(data) // 4
        segment_means = []
        segment_stds = []
        
        for i in range(4):
            start_idx = i * segment_length
            end_idx = start_idx + segment_length if i < 3 else len(data)
            if start_idx < len(data):
                segment_data = data.iloc[start_idx:end_idx]
                segment_means.append(float(np.mean(segment_data)))
                segment_stds.append(float(np.std(segment_data)))
        
        # 3. 移动平均分析趋势
        window_size = min(1000, len(data) // 10)  # 自适应窗口大小
        if window_size > 0:
            moving_avg = data.rolling(window=window_size, center=True).mean()
            if len(moving_avg.dropna()) > 1:
                total_drift = float(moving_avg.dropna().iloc[-1] - moving_avg.dropna().iloc[0])
            else:
                total_drift = 0.0
        else:
            total_drift = 0.0
        
        stability_results[channel] = {
            'linear_drift_slope': float(slope),
            'linear_drift_r_squared': float(r_value**2),
            'segment_means': segment_means,
            'segment_stds': segment_stds,
            'mean_variation': float(np.std(segment_means) / np.mean(segment_means)) if len(segment_means) > 0 and np.mean(segment_means) != 0 else 0.0,
            'std_variation': float(np.std(segment_stds) / np.mean(segment_stds)) if len(segment_stds) > 0 and np.mean(segment_stds) != 0 else 0.0,
            'total_drift': total_drift
        }
    
    return stability_results, float(total_duration)

def plot_group_time_series(group_data, output_path, max_points_per_file=5000):
    """绘制组内所有文件的通道时序图（抽样显示）"""
    try:
        logger.info("开始绘制组时序图")
        
        # 创建4x4的子图布局
        fig, axes = plt.subplots(4, 4, figsize=(20, 16))
        axes = axes.flatten()
        
        # 获取所有通道名称（假设所有文件通道相同）
        sample_file = group_data[0]
        channel_columns = [col for col in sample_file['df'].columns if col.startswith('channel')]
        
        # 设置统一的y轴范围
        all_data = []
        for file_data in group_data:
            for channel in channel_columns:
                step = max(1, len(file_data['df']) // max_points_per_file)
                sampled_data = file_data['df'][channel].iloc[::step]
                all_data.extend(sampled_data.values)
        
        if all_data:
            y_min, y_max = np.percentile(all_data, [1, 99])
            y_range = y_max - y_min
            y_lim = [y_min - 0.1 * y_range, y_max + 0.1 * y_range]
        else:
            y_lim = [-1, 1]  # 默认范围
        
        # 为每个通道绘制所有文件的时序图
        for i, channel in enumerate(channel_columns):
            if i < len(axes):
                ax = axes[i]
                
                # 为每个文件绘制一条线（使用不同颜色）
                colors = plt.cm.tab10(np.linspace(0, 1, len(group_data)))
                for j, file_data in enumerate(group_data):
                    df = file_data['df']
                    time_seconds = pd.to_numeric(df['time'], errors='coerce')
                    if time_seconds.isna().all():
                        time_seconds = pd.Series(np.arange(len(df)))
                    
                    # 抽样数据点
                    step = max(1, len(df) // max_points_per_file)
                    plot_time = time_seconds.iloc[::step]
                    plot_data = df[channel].iloc[::step]
                    
                    # 确保数据长度一致
                    min_len = min(len(plot_time), len(plot_data))
                    if min_len > 0:
                        ax.plot(plot_time.iloc[:min_len], plot_data.iloc[:min_len], 
                               color=colors[j], alpha=0.7, linewidth=0.5,
                               label=f"File {j+1}")
                
                ax.set_title(f'{channel.upper()}', fontsize=12, fontweight='bold')
                ax.set_xlabel('Time (s)')
                ax.set_ylabel('Voltage (V)')
                ax.set_ylim(y_lim)
                ax.grid(True, alpha=0.3)
                
                # 只在第一个子图显示图例
                if i == 0 and len(group_data) <= 10:  # 避免图例太多
                    ax.legend(loc='upper right', fontsize=6)
        
        # 隐藏多余的子图
        for i in range(len(channel_columns), len(axes)):
            axes[i].set_visible(False)
        
        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - All Files Channel Time Series', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        
        # 保存图片
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组时序图已保存: {output_path}")
        
    except Exception as e:
        logger.error(f"绘制组时序图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def plot_group_statistics_comparison(group_stats, output_path):
    """绘制组内统计量对比图"""
    try:
        logger.info("开始绘制组统计量对比图")
        
        if not group_stats:
            logger.warning("没有可用的统计数据")
            return
            
        channels = list(group_stats[0]['basic_stats'].keys())
        num_files = len(group_stats)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 准备数据
        means_data = {ch: [] for ch in channels}
        stds_data = {ch: [] for ch in channels}
        snr_data = {ch: [] for ch in channels}
        drift_data = {ch: [] for ch in channels}
        
        for file_stats in group_stats:
            for channel in channels:
                means_data[channel].append(file_stats['basic_stats'][channel]['mean'])
                stds_data[channel].append(file_stats['basic_stats'][channel]['std'])
                snr_data[channel].append(file_stats['basic_stats'][channel]['signal_to_noise_ratio'])
                drift_data[channel].append(file_stats['stability_results'][channel]['linear_drift_slope'])
        
        # 1. 均值对比（箱线图）
        if means_data:
            means_df = pd.DataFrame(means_data)
            means_df.boxplot(ax=ax1, rot=45)
            ax1.set_title('Channel Mean Distribution (All Files in Group)', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Mean Voltage (V)')
            ax1.grid(True, alpha=0.3)
        
        # 2. 标准差对比（箱线图）
        if stds_data:
            stds_df = pd.DataFrame(stds_data)
            stds_df.boxplot(ax=ax2, rot=45)
            ax2.set_title('Channel Noise Level Distribution (Standard Deviation)', fontsize=14, fontweight='bold')
            ax2.set_ylabel('Noise Level (V)')
            ax2.grid(True, alpha=0.3)
        
        # 3. 信噪比对比
        x = np.arange(len(channels))
        width = 0.8 / num_files if num_files > 0 else 0.8
        
        for i in range(num_files):
            snr_values = [snr_data[ch][i] for ch in channels]
            ax3.bar(x + i * width - width * (num_files - 1) / 2, 
                   snr_values, width, label=f'File {i+1}', alpha=0.7)
        
        ax3.set_title('Channel Signal-to-Noise Ratio Comparison', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Channel')
        ax3.set_ylabel('Signal-to-Noise Ratio')
        ax3.set_xticks(x)
        ax3.set_xticklabels([f'Ch{i+1}' for i in range(len(channels))])
        if num_files <= 10:  # 避免图例太多
            ax3.legend(fontsize=8)
        ax3.grid(True, alpha=0.3)
        
        # 4. 漂移斜率对比
        for i in range(num_files):
            drift_values = [drift_data[ch][i] for ch in channels]
            ax4.bar(x + i * width - width * (num_files - 1) / 2, 
                   drift_values, width, label=f'File {i+1}', alpha=0.7)
        
        ax4.set_title('Channel Linear Drift Slope Comparison', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Channel')
        ax4.set_ylabel('Drift Slope (V/s)')
        ax4.set_xticks(x)
        ax4.set_xticklabels([f'Ch{i+1}' for i in range(len(channels))])
        if num_files <= 10:  # 避免图例太多
            ax4.legend(fontsize=8)
        ax4.grid(True, alpha=0.3)
        
        group_name = Path(group_stats[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Statistical Comparison Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.subplots_adjust(top=0.93)
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组统计量对比图已保存: {output_path}")
        
    except Exception as e:
        logger.error(f"绘制组统计量对比图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def plot_group_stability_analysis(group_stats, output_path):
    """绘制组稳定性分析图"""
    try:
        logger.info("开始绘制组稳定性分析图")
        
        if not group_stats:
            logger.warning("没有可用的统计数据")
            return
            
        channels = list(group_stats[0]['basic_stats'].keys())
        num_files = len(group_stats)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 准备数据
        drift_slopes = {ch: [] for ch in channels}
        r_squared = {ch: [] for ch in channels}
        mean_variations = {ch: [] for ch in channels}
        total_drifts = {ch: [] for ch in channels}
        
        for file_stats in group_stats:
            for channel in channels:
                stability = file_stats['stability_results'][channel]
                drift_slopes[channel].append(stability['linear_drift_slope'])
                r_squared[channel].append(stability['linear_drift_r_squared'])
                mean_variations[channel].append(stability['mean_variation'])
                total_drifts[channel].append(stability['total_drift'])
        
        x = np.arange(len(channels))
        width = 0.8 / num_files if num_files > 0 else 0.8
        
        # 1. 线性漂移斜率
        for i in range(num_files):
            values = [drift_slopes[ch][i] for ch in channels]
            ax1.bar(x + i * width - width * (num_files - 1) / 2, 
                   values, width, label=f'File {i+1}', alpha=0.7)
        
        ax1.set_title('Linear Drift Slope Comparison', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Channel')
        ax1.set_ylabel('Drift Slope (V/s)')
        ax1.set_xticks(x)
        ax1.set_xticklabels([f'Ch{i+1}' for i in range(len(channels))])
        if num_files <= 10:  # 避免图例太多
            ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)
        
        # 2. 线性拟合优度 (R²)
        for i in range(num_files):
            values = [r_squared[ch][i] for ch in channels]
            ax2.bar(x + i * width - width * (num_files - 1) / 2, 
                   values, width, label=f'File {i+1}', alpha=0.7)
        
        ax2.set_title('Linear Fit Goodness (R²) Comparison', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Channel')
        ax2.set_ylabel('R²')
        ax2.set_xticks(x)
        ax2.set_xticklabels([f'Ch{i+1}' for i in range(len(channels))])
        if num_files <= 10:  # 避免图例太多
            ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)
        
        # 3. 均值变化系数
        for i in range(num_files):
            values = [mean_variations[ch][i] for ch in channels]
            ax3.bar(x + i * width - width * (num_files - 1) / 2, 
                   values, width, label=f'File {i+1}', alpha=0.7)
        
        ax3.set_title('Segment Mean Variation Coefficient Comparison', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Channel')
        ax3.set_ylabel('Coefficient of Variation')
        ax3.set_xticks(x)
        ax3.set_xticklabels([f'Ch{i+1}' for i in range(len(channels))])
        if num_files <= 10:  # 避免图例太多
            ax3.legend(fontsize=8)
        ax3.grid(True, alpha=0.3)
        
        # 4. 总漂移量
        for i in range(num_files):
            values = [total_drifts[ch][i] for ch in channels]
            ax4.bar(x + i * width - width * (num_files - 1) / 2, 
                   values, width, label=f'File {i+1}', alpha=0.7)
        
        ax4.set_title('Total Drift Comparison', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Channel')
        ax4.set_ylabel('Total Drift (V)')
        ax4.set_xticks(x)
        ax4.set_xticklabels([f'Ch{i+1}' for i in range(len(channels))])
        if num_files <= 10:  # 避免图例太多
            ax4.legend(fontsize=8)
        ax4.grid(True, alpha=0.3)
        
        group_name = Path(group_stats[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Stability Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.subplots_adjust(top=0.93)
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组稳定性分析图已保存: {output_path}")
        
    except Exception as e:
        logger.error(f"绘制组稳定性分析图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def generate_group_analysis_report(group_stats, output_path):
    """生成组分析报告 - 修复JSON序列化问题"""
    try:
        logger.info("开始生成组分析报告")
        
        if not group_stats:
            logger.warning("没有可用的统计数据")
            return None
            
        channels = list(group_stats[0]['basic_stats'].keys())
        group_name = Path(group_stats[0]['file_path']).parent.name
        
        report = {
            'analysis_time': datetime.now().isoformat(),
            'group_name': str(group_name),  # 确保字符串
            'file_count': len(group_stats),
            'channel_count': len(channels),
            'files_analyzed': [str(Path(stats['file_path']).name) for stats in group_stats],  # 确保字符串
            'summary_statistics': {},
            'channel_performance': {},
            'quality_assessment': {}
        }
        
        # 汇总统计（跨所有文件）
        all_means = []
        all_stds = []
        all_snr = []
        
        for file_stats in group_stats:
            for channel in channels:
                stats = file_stats['basic_stats'][channel]
                all_means.append(stats['mean'])
                all_stds.append(stats['std'])
                all_snr.append(stats['signal_to_noise_ratio'])
        
        if all_means:
            report['summary_statistics'] = {
                'mean_voltage': {
                    'average': float(np.mean(all_means)),
                    'std': float(np.std(all_means)),
                    'min': float(np.min(all_means)),
                    'max': float(np.max(all_means))
                },
                'noise_level': {
                    'average': float(np.mean(all_stds)),
                    'std': float(np.std(all_stds)),
                    'min': float(np.min(all_stds)),
                    'max': float(np.max(all_stds))
                },
                'signal_to_noise_ratio': {
                    'average': float(np.mean(all_snr)),
                    'std': float(np.std(all_snr)),
                    'min': float(np.min(all_snr)),
                    'max': float(np.max(all_snr))
                }
            }
        
        # 通道性能评估
        for channel in channels:
            channel_means = [file_stats['basic_stats'][channel]['mean'] for file_stats in group_stats]
            channel_stds = [file_stats['basic_stats'][channel]['std'] for file_stats in group_stats]
            channel_drifts = [file_stats['stability_results'][channel]['linear_drift_slope'] for file_stats in group_stats]
            
            if channel_means:
                mean_val = float(np.mean(channel_means))
                std_val = float(np.std(channel_means))
                report['channel_performance'][channel] = {
                    'mean_consistency': {
                        'mean': mean_val,
                        'std': std_val,
                        'cv': float(std_val / mean_val) if mean_val != 0 else 0.0
                    },
                    'noise_consistency': {
                        'mean': float(np.mean(channel_stds)),
                        'std': float(np.std(channel_stds)),
                        'cv': float(np.std(channel_stds) / np.mean(channel_stds)) if np.mean(channel_stds) != 0 else 0.0
                    },
                    'drift_characteristics': {
                        'mean_drift': float(np.mean(channel_drifts)),
                        'std_drift': float(np.std(channel_drifts)),
                        'max_drift': float(np.max(np.abs(channel_drifts)))
                    }
                }
        
        # 质量评估
        mean_cv_threshold = 0.1  # 10%的变异系数
        noise_cv_threshold = 0.2  # 20%的噪声变异
        max_drift_threshold = 0.05  # 0.05V/秒的最大漂移
        
        good_channels = []
        problematic_channels = []
        
        for channel in channels:
            if channel in report['channel_performance']:
                perf = report['channel_performance'][channel]
                mean_cv = perf['mean_consistency']['cv']
                noise_cv = perf['noise_consistency']['cv']
                max_drift = perf['drift_characteristics']['max_drift']
                
                if (mean_cv < mean_cv_threshold and 
                    noise_cv < noise_cv_threshold and 
                    max_drift < max_drift_threshold):
                    good_channels.append(channel)
                else:
                    problematic_channels.append(channel)
        
        report['quality_assessment'] = {
            'good_channels': good_channels,
            'problematic_channels': problematic_channels,
            'good_channel_count': len(good_channels),
            'problematic_channel_count': len(problematic_channels),
            'overall_quality': 'Excellent' if len(problematic_channels) == 0 else 
                              'Good' if len(problematic_channels) <= 2 else 
                              'Needs Check'
        }
        
        # 保存报告 - 确保所有数据都可序列化
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"组分析报告已保存: {output_path}")
        
        return report
        
    except Exception as e:
        logger.error(f"生成组分析报告失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def analyze_group(group_files, group_output_dir):
    """分析一个组的所有文件"""
    try:
        logger.info(f"开始分析组，包含 {len(group_files)} 个文件")
        
        # 创建组输出目录
        Path(group_output_dir).mkdir(parents=True, exist_ok=True)
        
        group_data = []
        group_stats = []
        
        # 读取所有文件数据并计算统计量
        for file_path in group_files:
            try:
                df, time_column, channel_columns = read_csv_data(file_path)
                
                # 计算统计量
                basic_stats = calculate_basic_statistics(df, channel_columns)
                stability_results, total_duration = analyze_signal_stability(df, channel_columns, time_column)
                
                group_data.append({
                    'file_path': str(file_path),  # 转换为字符串
                    'df': df,
                    'time_column': time_column,
                    'channel_columns': channel_columns
                })
                
                group_stats.append({
                    'file_path': str(file_path),  # 转换为字符串
                    'basic_stats': basic_stats,
                    'stability_results': stability_results,
                    'total_duration': total_duration
                })
                
            except Exception as e:
                logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
                continue
        
        if not group_data:
            logger.warning("组内没有成功处理的文件")
            return None
        
        group_name = Path(group_files[0]).parent.name
        
        # 生成组分析图表和报告
        plot_group_time_series(group_data, Path(group_output_dir) / 'group_time_series.png')
        plot_group_statistics_comparison(group_stats, Path(group_output_dir) / 'group_statistics_comparison.png')
        plot_group_stability_analysis(group_stats, Path(group_output_dir) / 'group_stability_analysis.png')
        
        report = generate_group_analysis_report(group_stats, Path(group_output_dir) / 'time_series_plots_report.json')
        
        logger.info(f"组分析完成: {group_name}")
        
        return {
            'group_name': str(group_name),  # 转换为字符串
            'output_dir': str(group_output_dir),  # 转换为字符串
            'file_count': len(group_files),
            'successful_files': len(group_data),
            'report': report
        }
        
    except Exception as e:
        logger.error(f"分析组失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def main():
    """主函数"""
    try:
        # 加载配置
        config = load_config()
        
        # 输入输出路径
        input_dir = config["tdms_reader_time_output_dir"]
        output_dir = config["time_series_results_dir"]
        
        logger.info(f"输入目录: {input_dir}")
        logger.info(f"输出目录: {output_dir}")
        
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 按组查找所有CSV文件
        csv_files = list(Path(input_dir).glob('**/*.csv'))
        
        if not csv_files:
            logger.warning(f"在 {input_dir} 中未找到CSV文件")
            return
        
        logger.info(f"找到 {len(csv_files)} 个CSV文件")
        
        # 按组分组文件
        groups = {}
        for csv_file in csv_files:
            group_name = csv_file.parent.name
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(csv_file)
        
        logger.info(f"找到 {len(groups)} 个组: {list(groups.keys())}")
        
        # 分析每个组
        results = []
        for group_name, group_files in groups.items():
            logger.info(f"分析组 {group_name}, 包含 {len(group_files)} 个文件")
            
            group_output_dir = Path(output_dir) / group_name
            result = analyze_group(group_files, group_output_dir)
            
            if result:
                results.append(result)
        
        # 生成总体报告 - 修复JSON序列化问题
        summary = {
            'analysis_time': datetime.now().isoformat(),
            'total_groups': len(groups),
            'analyzed_groups': len(results),
            'total_files': len(csv_files),
            'group_results': []
        }
        
        for result in results:
            summary['group_results'].append({
                'group_name': str(result['group_name']),  # 转换为字符串
                'file_count': result['file_count'],
                'successful_files': result['successful_files'],
                'output_dir': str(result['output_dir'])  # 转换为字符串
            })
        
        summary_path = Path(output_dir) / 'analysis_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"时域分析完成! 成功分析 {len(results)} 个组")
        logger.info(f"总体报告: {summary_path}")
        
    except Exception as e:
        logger.error(f"时域分析主程序失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()