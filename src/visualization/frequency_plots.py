#====================================================================
# File Name: fft_analysis.py
# Project Name: dataprocess
# Description: FFT Data Analysis Module
# Functions:
# 1. Amplitude Spectrum Comparison: 16-channel spectrum amplitude distribution
# 2. Phase Spectrum Analysis: Phase relationships between channels, identifying time delay characteristics
# 3. Dominant Frequency Identification: Finding significant frequency components
# 4. Frequency Component Stability: Repeatability of multiple measurements under same conditions
# 5. Feature Frequency Extraction: Specific frequency components related to targets
#====================================================================

import numpy as np
import pandas as pd
import os
from pathlib import Path
import yaml
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import signal
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Set plotting style
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

# 设置matplotlib不显示图形窗口
plt.switch_backend('Agg')

logger = logging.getLogger('data_process')

def load_config():
    """加载配置文件"""
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config

def read_fft_data(csv_file_path):
    """读取FFT CSV文件数据"""
    try:
        logger.info(f"正在读取FFT CSV文件: {csv_file_path}")
        
        df = pd.read_csv(csv_file_path)
        
        # 检查数据列
        if 'frequency' not in df.columns:
            raise ValueError(f"CSV文件中缺少frequency列，可用列: {list(df.columns)}")
        
        # 提取通道信息
        channel_info = extract_channel_info(df.columns)
        
        logger.info(f"成功读取FFT数据: {len(df)} 行, {len(channel_info['amplitude_channels'])} 个幅度通道, {len(channel_info['phase_channels'])} 个相位通道")
        return df, channel_info
    
    except Exception as e:
        logger.error(f"读取FFT CSV文件失败 {csv_file_path}: {str(e)}")
        raise

def extract_channel_info(columns):
    """从列名中提取通道信息"""
    channel_info = {
        'amplitude_channels': [],
        'phase_channels': [],
        'channel_numbers': []
    }
    
    for col in columns:
        if col == 'frequency':
            continue
        if col.startswith('amplitude'):
            channel_info['amplitude_channels'].append(col)
            # 提取通道号
            channel_num = col.replace('amplitude', '')
            if channel_num not in channel_info['channel_numbers']:
                channel_info['channel_numbers'].append(channel_num)
        elif col.startswith('phase'):
            channel_info['phase_channels'].append(col)
    
    logger.info(f"识别到 {len(channel_info['channel_numbers'])} 个通道")
    return channel_info

def calculate_fft_statistics(df, channel_info):
    """计算FFT统计量"""
    stats_results = {}
    amplitude_channels = channel_info['amplitude_channels']
    
    for channel in amplitude_channels:
        amplitude = df[channel]
        frequency = df['frequency']
        
        # 寻找主要峰值
        peaks, properties = signal.find_peaks(amplitude, height=amplitude.max()*0.05, distance=10)
        
        dominant_frequencies = []
        dominant_amplitudes = []
        
        if len(peaks) > 0:
            # 按峰值高度排序
            sorted_peaks = peaks[np.argsort(amplitude.iloc[peaks])[::-1]]
            top_peaks = sorted_peaks[:20]  # 前5个峰值
            
            dominant_frequencies = frequency.iloc[top_peaks].tolist()
            dominant_amplitudes = amplitude.iloc[top_peaks].tolist()
        
        stats_results[channel] = {
            'dominant_frequencies': dominant_frequencies,
            'dominant_amplitudes': dominant_amplitudes,
            'total_energy': float(np.trapz(amplitude, frequency)),
            'peak_count': len(peaks),
            'max_amplitude': float(amplitude.max()),
            'mean_amplitude': float(amplitude.mean()),
            'std_amplitude': float(amplitude.std()),
            'frequency_range': [float(frequency.min()), float(frequency.max())]
        }
    
    return stats_results

def analyze_phase_relationships(df, channel_info):
    """分析相位关系"""
    phase_analysis = {}
    phase_channels = channel_info['phase_channels']
    frequency = df['frequency']
    
    if len(phase_channels) < 2:
        return phase_analysis
    
    reference_channel = phase_channels[0]
    
    for channel in phase_channels[1:]:
        phase_diff = df[channel] - df[reference_channel]
        phase_diff_unwrapped = np.unwrap(phase_diff)
        
        # 计算时延（基于相位斜率）
        valid_freq_mask = (frequency > 10) & (frequency < 500)  # 选择有效频率范围
        if valid_freq_mask.sum() > 10:  # 确保有足够的数据点
            valid_freq = frequency[valid_freq_mask]
            valid_phase = phase_diff_unwrapped[valid_freq_mask]
            
            # 线性拟合计算时延
            if len(valid_freq) > 1:
                slope, intercept = np.polyfit(valid_freq, valid_phase, 1)
                time_delay = -slope / (2 * np.pi)  # 时延 = -斜率 / (2π)
            else:
                time_delay = np.nan
        else:
            time_delay = np.nan
        
        phase_analysis[f'{channel}_vs_{reference_channel}'] = {
            'mean_phase_diff': float(np.mean(phase_diff_unwrapped)),
            'std_phase_diff': float(np.std(phase_diff_unwrapped)),
            'estimated_time_delay_ms': float(time_delay * 1000) if not np.isnan(time_delay) else np.nan,
            'phase_coherence': float(np.abs(np.mean(np.exp(1j * phase_diff_unwrapped))))
        }
    
    return phase_analysis

def plot_group_amplitude_spectrum(group_data, output_path):
    """绘制组内所有文件的幅度谱对比图"""
    try:
        logger.info("开始绘制组幅度谱对比图")
        
        # 创建4x4的子图布局
        fig, axes = plt.subplots(4, 4, figsize=(20, 16))
        axes = axes.flatten()
        
        # 获取所有幅度通道名称（假设所有文件通道相同）
        sample_file = group_data[0]
        amplitude_channels = sample_file['channel_info']['amplitude_channels']
        
        # 设置统一的y轴范围
        all_data = []
        for file_data in group_data:
            for channel in amplitude_channels:
                all_data.extend(file_data['df'][channel].values)
        
        if all_data:
            y_min = 0
            y_max = np.percentile(all_data, 99.9)
            y_range = y_max - y_min
            y_lim = [y_min, y_max + 0.1 * y_range]  # 从0开始，上方留10%空白
        else:
            y_lim = [0, 1]  # 默认范围
        
        # 为每个通道绘制所有文件的幅度谱
        for i, channel in enumerate(amplitude_channels):
            if i < len(axes):
                ax = axes[i]
                
                # 为每个文件绘制一条线（使用不同颜色）
                colors = plt.cm.tab10(np.linspace(0, 1, len(group_data)))
                for j, file_data in enumerate(group_data):
                    df = file_data['df']
                    frequency = df['frequency']
                    amplitude = df[channel]
                    
                    ax.plot(frequency, amplitude, color=colors[j], alpha=0.7, linewidth=1,
                           label=f"File {j+1}")
                
                ax.set_title(f'{channel.upper()}', fontsize=12, fontweight='bold')
                ax.set_xlabel('Frequency (Hz)')
                ax.set_ylabel('Amplitude')
                ax.set_ylim(y_lim)
                ax.set_xlim(0, min(1000, frequency.max()))  # 限制频率范围
                ax.grid(True, alpha=0.3)
                
                # 只在第一个子图显示图例
                if i == 0 and len(group_data) <= 10:  # 避免图例太多
                    ax.legend(loc='upper right', fontsize=6)
        
        # 隐藏多余的子图
        for i in range(len(amplitude_channels), len(axes)):
            axes[i].set_visible(False)
        
        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Amplitude Spectrum Comparison (0-1000Hz)', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        
        # 保存第一个图（0-1000Hz）
        output_path_1 = str(output_path).replace('.png', '_1.png')
        plt.savefig(output_path_1, dpi=300, bbox_inches='tight')
        logger.info(f"组幅度谱对比图1已保存: {output_path_1}")
        
        # 生成第二个图（0-6000Hz）
        for i, channel in enumerate(amplitude_channels):
            if i < len(axes):
                ax = axes[i]
                ax.set_xlim(0, min(6000, frequency.max()))  # 修改横坐标范围为0-6000Hz
        
        plt.suptitle(f'Group {group_name} - Amplitude Spectrum Comparison (0-6000Hz)', fontsize=16, fontweight='bold')
        
        # 保存第二个图

        output_path_2 = str(output_path).replace('.png', '_2.png')
        plt.savefig(output_path_2, dpi=300, bbox_inches='tight')
        logger.info(f"组幅度谱对比图2已保存: {output_path_2}")
        
        # 生成第二个图（0-50000Hz）
        for i, channel in enumerate(amplitude_channels):
            if i < len(axes):
                ax = axes[i]
                ax.set_xlim(0, min(50000, frequency.max()))  # 修改横坐标范围为0-50000Hz
        
        plt.suptitle(f'Group {group_name} - Amplitude Spectrum Comparison (0-50000Hz)', fontsize=16, fontweight='bold')
        
        # 保存第三个图

        output_path_3 = str(output_path).replace('.png', '_3.png')
        plt.savefig(output_path_3, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组幅度谱对比图3已保存: {output_path_3}")

    except Exception as e:
        logger.error(f"绘制组幅度谱对比图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def plot_group_phase_analysis(group_data, output_path):
    """绘制组相位分析图"""
    try:
        logger.info("开始绘制组相位分析图")
        
        if not group_data:
            logger.warning("没有可用的数据")
            return
        
        # 使用第一个文件的数据
        sample_data = group_data[0]
        df = sample_data['df']
        channel_info = sample_data['channel_info']
        phase_channels = channel_info['phase_channels']
        
        if len(phase_channels) < 2:
            logger.warning("相位通道数量不足，无法进行相位分析")
            return
        
        # 创建子图
        fig, axes = plt.subplots(2, 1, figsize=(15, 12))
        
        # 1. 相位谱图
        ax1 = axes[0]
        for channel in phase_channels:
            frequency = df['frequency']
            phase = df[channel]
            ax1.plot(frequency, phase, label=channel, alpha=0.7, linewidth=1)
        
        ax1.set_title('Phase Spectrum of All Channels', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Phase (rad)')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, min(1000, frequency.max()))
        
        # 2. 相位差分析
        ax2 = axes[1]
        reference_channel = phase_channels[0]
        
        for i, channel in enumerate(phase_channels[1:], 1):
            phase_diff = df[channel] - df[reference_channel]
            phase_diff_unwrapped = np.unwrap(phase_diff)
            ax2.plot(frequency, phase_diff_unwrapped, 
                    label=f'{channel} - {reference_channel}', alpha=0.7)
        
        ax2.set_title('Phase Difference Relative to Reference Channel (Unwrapped)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Phase Difference (rad)')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, min(1000, frequency.max()))
        
        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Phase Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组相位分析图已保存: {output_path}")
        
    except Exception as e:
        logger.error(f"绘制组相位分析图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def plot_group_dominant_frequencies(group_stats, output_path):
    """绘制组主导频率分布图"""
    try:
        logger.info("开始绘制组主导频率分布图")
        
        if not group_stats:
            logger.warning("没有可用的统计数据")
            return
            
        # 收集所有主导频率
        all_dominant_freqs = []
        for file_stats in group_stats:
            for channel, stats in file_stats['fft_stats'].items():
                for freq, amp in zip(stats['dominant_frequencies'], stats['dominant_amplitudes']):
                    all_dominant_freqs.append({
                        'channel': channel,
                        'frequency': freq,
                        'amplitude': amp,
                        'file': Path(file_stats['file_path']).name
                    })
        
        if not all_dominant_freqs:
            logger.warning("没有找到主导频率")
            return
        
        # 创建DataFrame
        df_dominant = pd.DataFrame(all_dominant_freqs)
        
        # 绘制主导频率分布
        plt.figure(figsize=(15, 10))
        
        # 按通道绘制
        channels = df_dominant['channel'].unique()
        colors = plt.cm.tab10(np.linspace(0, 1, len(channels)))
        
        for i, channel in enumerate(channels):
            channel_data = df_dominant[df_dominant['channel'] == channel]
            plt.scatter(channel_data['frequency'], channel_data['amplitude'], 
                       label=channel, color=colors[i], s=50, alpha=0.7)
        
        plt.title('Dominant Frequency Distribution by Channel', fontsize=16, fontweight='bold')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # 标记最常见的频率
        if len(df_dominant) > 0:
            freq_counts = df_dominant['frequency'].value_counts().head(5)
            for freq, count in freq_counts.items():
                plt.axvline(x=freq, color='red', linestyle='--', alpha=0.5)
                plt.text(freq, plt.ylim()[1]*0.9, f'{freq:.1f}Hz\n({count} times)', 
                        ha='center', fontsize=8, color='red')
        
        group_name = Path(group_stats[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Dominant Frequency Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组主导频率分布图已保存: {output_path}")
        
        return df_dominant
        
    except Exception as e:
        logger.error(f"绘制组主导频率分布图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def plot_group_stability_analysis(group_stats, output_path):
    """绘制组频率稳定性分析图"""
    try:
        logger.info("开始绘制组频率稳定性分析图")
        all_amplitudes = []
        if len(group_stats) < 2:
            logger.warning("需要至少2个文件进行稳定性分析")
            return
        
        # 获取第一个文件的频率数据和通道
        first_file_stats = group_stats[0]
        first_file_data, first_channel_info = read_fft_data(first_file_stats['file_path'])
        frequency = first_file_data['frequency']
        amplitude_channels = first_channel_info['amplitude_channels']
        
        if not amplitude_channels:
            logger.warning("没有幅度通道数据")
            return
        
        # 使用第一个幅度通道进行稳定性分析
        reference_channel = amplitude_channels[0]
        expected_length = len(first_file_data[reference_channel])  # 获取第一个文件的长度作为基准

        for file_stats in group_stats:
            try:
                df, _ = read_fft_data(file_stats['file_path'])
                current_amplitude = df[reference_channel].values
                current_length = len(current_amplitude)
                
                # 检查数据长度是否一致
                if current_length != expected_length:
                    logger.warning(f"跳过文件 {Path(file_stats['file_path']).name}: 数据长度不一致 ({current_length} vs {expected_length})")
                    continue
                    
                all_amplitudes.append(current_amplitude)
            except Exception as e:
                logger.warning(f"读取文件 {file_stats['file_path']} 失败: {str(e)}")
                continue
        
        if len(all_amplitudes) < 2:
            logger.warning("没有足够的数据进行稳定性分析")
            return
        
        # 计算统计量
        all_amplitudes = np.array(all_amplitudes)
        mean_amplitude = np.mean(all_amplitudes, axis=0)
        std_amplitude = np.std(all_amplitudes, axis=0)
        cv_amplitude = std_amplitude / (mean_amplitude + 1e-8)  # 变异系数
        
        # 绘制稳定性分析图
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # 1. 幅度平均值和标准差
        ax1 = axes[0]
        ax1.plot(frequency, mean_amplitude, 'b-', label='Mean', linewidth=2)
        ax1.fill_between(frequency, mean_amplitude - std_amplitude, 
                        mean_amplitude + std_amplitude, alpha=0.3, label='±1 Std Dev')
        ax1.set_title('Amplitude Spectrum Stability Analysis', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Amplitude')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, min(1000, frequency.max()))
        
        # 2. 变异系数
        ax2 = axes[1]
        ax2.plot(frequency, cv_amplitude, 'r-', linewidth=2)
        ax2.set_title('Amplitude Coefficient of Variation (CV)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Coefficient of Variation')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, min(1000, frequency.max()))
        
        group_name = Path(group_stats[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Frequency Stability Analysis (Channel {reference_channel})', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组频率稳定性分析图已保存: {output_path}")
        
        stability_analysis = {
            'mean_amplitude': mean_amplitude.tolist(),
            'std_amplitude': std_amplitude.tolist(),
            'cv_amplitude': cv_amplitude.tolist(),
            'overall_cv': float(np.mean(cv_amplitude[frequency < 500])),  # 500Hz以下的平均CV
            'file_count': len(all_amplitudes),
            'reference_channel': reference_channel
        }
        
        return stability_analysis
        
    except Exception as e:
        logger.error(f"绘制组频率稳定性分析图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def plot_group_feature_frequencies(group_data, target_frequencies, output_path):
    """绘制组特征频率提取图"""
    try:
        logger.info("开始绘制组特征频率提取图")
        
        if not group_data:
            logger.warning("没有可用的数据")
            return
        
        # 使用第一个文件的数据
        sample_data = group_data[0]
        df = sample_data['df']
        channel_info = sample_data['channel_info']
        amplitude_channels = channel_info['amplitude_channels']
        frequency = df['frequency']
        
        # 如果没有指定目标频率，自动检测
        if target_frequencies is None:
            target_frequencies = auto_detect_feature_frequencies(df, channel_info)
        
        if not target_frequencies:
            logger.warning("没有找到特征频率")
            return
        
        # 绘制特征频率图
        plt.figure(figsize=(15, 8))
        
        # 只显示前4个通道避免过于拥挤
        for channel in amplitude_channels[:4]:
            amplitude = df[channel]
            plt.plot(frequency, amplitude, label=channel, alpha=0.7)
            
            # 标记特征频率
            for target_freq in target_frequencies:
                idx = np.argmin(np.abs(frequency - target_freq))
                plt.plot(frequency.iloc[idx], amplitude.iloc[idx], 'ro', markersize=6)
                plt.annotate(f'{target_freq}Hz', 
                           (frequency.iloc[idx], amplitude.iloc[idx]),
                           xytext=(10, 10), textcoords='offset points',
                           fontsize=8, color='red')
        
        plt.title('Feature Frequency Extraction', fontsize=16, fontweight='bold')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xlim(0, min(1000, frequency.max()))
        
        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Feature Frequency Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"组特征频率提取图已保存: {output_path}")
        
        # 计算特征频率结果
        feature_results = {}
        for channel in amplitude_channels:
            amplitude = df[channel]
            channel_features = {}
            
            for target_freq in target_frequencies:
                idx = np.argmin(np.abs(frequency - target_freq))
                actual_freq = frequency.iloc[idx]
                amp_value = amplitude.iloc[idx]
                
                channel_features[target_freq] = {
                    'actual_frequency': float(actual_freq),
                    'amplitude': float(amp_value),
                    'frequency_error': float(abs(actual_freq - target_freq))
                }
            
            feature_results[channel] = channel_features
        
        return feature_results
        
    except Exception as e:
        logger.error(f"绘制组特征频率提取图失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def auto_detect_feature_frequencies(df, channel_info, n_peaks=10):
    """自动检测特征频率"""
    amplitude_channels = channel_info['amplitude_channels']
    frequency = df['frequency']
    
    all_peaks = []
    
    for channel in amplitude_channels:
        amplitude = df[channel]
        peaks, properties = signal.find_peaks(amplitude, height=amplitude.max()*0.05, distance=10)
        
        if len(peaks) > 0:
            # 获取显著的峰值
            significant_peaks = peaks[np.argsort(amplitude.iloc[peaks])[-n_peaks:]]
            peak_freqs = frequency.iloc[significant_peaks].tolist()
            all_peaks.extend(peak_freqs)
    
    # 统计频率出现次数
    if all_peaks:
        freq_counts = pd.Series(all_peaks).value_counts()
        # 选择出现次数最多的频率作为特征频率
        feature_frequencies = freq_counts.head(5).index.tolist()
        logger.info(f"自动检测到的特征频率: {feature_frequencies}")
        return feature_frequencies
    else:
        logger.warning("未能自动检测到特征频率")
        return []

def generate_group_analysis_report(group_stats, group_name, output_path):
    """生成组分析报告"""
    try:
        logger.info("开始生成组分析报告")
        
        if not group_stats:
            logger.warning("没有可用的统计数据")
            return None
        
        channels = list(group_stats[0]['fft_stats'].keys())
        
        report = {
            'analysis_time': datetime.now().isoformat(),
            'group_name': str(group_name),
            'file_count': len(group_stats),
            'channel_count': len(channels),
            'files_analyzed': [str(Path(stats['file_path']).name) for stats in group_stats],
            'summary_statistics': {},
            'channel_performance': {},
            'dominant_frequencies_summary': {},
            'frequency_clusters': {}, 
            'quality_assessment': {}
        }
        
        # 汇总统计（跨所有文件）
        all_max_amplitudes = []
        all_total_energy = []
        all_peak_counts = []
        
        for file_stats in group_stats:
            for channel, stats in file_stats['fft_stats'].items():
                all_max_amplitudes.append(stats['max_amplitude'])
                all_total_energy.append(stats['total_energy'])
                all_peak_counts.append(stats['peak_count'])
        
        if all_max_amplitudes:
            report['summary_statistics'] = {
                'max_amplitude': {
                    'average': float(np.mean(all_max_amplitudes)),
                    'std': float(np.std(all_max_amplitudes)),
                    'min': float(np.min(all_max_amplitudes)),
                    'max': float(np.max(all_max_amplitudes))
                },
                'total_energy': {
                    'average': float(np.mean(all_total_energy)),
                    'std': float(np.std(all_total_energy)),
                    'min': float(np.min(all_total_energy)),
                    'max': float(np.max(all_total_energy))
                },
                'peak_count': {
                    'average': float(np.mean(all_peak_counts)),
                    'std': float(np.std(all_peak_counts)),
                    'min': float(np.min(all_peak_counts)),
                    'max': float(np.max(all_peak_counts))
                }
            }
        
        # 通道性能评估
        for channel in channels:
            channel_max_amps = [file_stats['fft_stats'][channel]['max_amplitude'] for file_stats in group_stats]
            channel_energies = [file_stats['fft_stats'][channel]['total_energy'] for file_stats in group_stats]
            
            # 收集主导频率
            dominant_freqs_all = []
            for file_stats in group_stats:
                dominant_freqs_all.extend(file_stats['fft_stats'][channel]['dominant_frequencies'])
            
            if channel_max_amps:
                mean_max_amp = float(np.mean(channel_max_amps))
                std_max_amp = float(np.std(channel_max_amps))
                
                report['channel_performance'][channel] = {
                    'amplitude_consistency': {
                        'mean': mean_max_amp,
                        'std': std_max_amp,
                        'cv': float(std_max_amp / mean_max_amp) if mean_max_amp != 0 else 0.0
                    },
                    'energy_consistency': {
                        'mean': float(np.mean(channel_energies)),
                        'std': float(np.std(channel_energies)),
                        'cv': float(np.std(channel_energies) / np.mean(channel_energies)) if np.mean(channel_energies) != 0 else 0.0
                    }
                }
            
            # 主导频率统计
            if dominant_freqs_all:
                freq_counts = pd.Series(dominant_freqs_all).value_counts()
                top_freqs = freq_counts.head(3).index.tolist()
                report['dominant_frequencies_summary'][channel] = {
                    'most_common_frequencies': [float(f) for f in top_freqs],
                    'frequency_counts': {float(freq): int(count) for freq, count in freq_counts.head(5).items()}
                }

        # 新增：频率集群分析
        report['frequency_clusters'] = analyze_frequency_clusters(group_stats, channels)

        # 质量评估
        amplitude_cv_threshold = 0.2  # 20%的幅度变异系数
        energy_cv_threshold = 0.3    # 30%的能量变异系数
        
        good_channels = []
        problematic_channels = []
        
        for channel in channels:
            if channel in report['channel_performance']:
                perf = report['channel_performance'][channel]
                amp_cv = perf['amplitude_consistency']['cv']
                energy_cv = perf['energy_consistency']['cv']
                
                if (amp_cv < amplitude_cv_threshold and 
                    energy_cv < energy_cv_threshold):
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
        
        # 保存报告
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"组分析报告已保存: {output_path}")
        
        return report
        
    except Exception as e:
        logger.error(f"生成组分析报告失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    

def analyze_frequency_clusters(group_stats, channels):
    """分析频率集群特征"""
    try:
        frequency_clusters = {}
        
        for channel in channels:
            # 收集该通道在所有文件中的所有主导频率
            all_channel_freqs = []
            for file_stats in group_stats:
                if channel in file_stats['fft_stats']:
                    all_channel_freqs.extend(file_stats['fft_stats'][channel]['dominant_frequencies'])
            
            if not all_channel_freqs:
                continue
                
            # 将频率分类到不同的集群中
            clusters = categorize_frequencies_to_clusters(all_channel_freqs)
            frequency_clusters[channel] = clusters
            
        return frequency_clusters
        
    except Exception as e:
        logger.error(f"分析频率集群失败: {str(e)}")
        return {}

def categorize_frequencies_to_clusters(frequencies, cluster_tolerance=50):
    """将频率分类到不同的集群中"""
    if not frequencies:
        return []
    
    # 按频率排序
    sorted_freqs = sorted(frequencies)
    clusters = []
    current_cluster = [sorted_freqs[0]]
    
    for freq in sorted_freqs[1:]:
        # 如果频率与当前集群的中心接近，则加入当前集群
        cluster_center = np.mean(current_cluster)
        if abs(freq - cluster_center) <= cluster_tolerance:
            current_cluster.append(freq)
        else:
            # 开始新的集群
            if len(current_cluster) >= 1:  # 至少有一个频率
                clusters.append(round(np.mean(current_cluster), 2))
            current_cluster = [freq]
    
    # 添加最后一个集群
    if current_cluster:
        clusters.append(round(np.mean(current_cluster), 2))
    
    # 返回前3个最显著的集群（按出现频率或集群大小排序）
    return sorted(clusters[:3])
    
def analyze_group(group_files, group_output_dir, target_frequencies=None):
    """分析一个组的所有FFT文件"""
    try:
        logger.info(f"开始分析FFT组，包含 {len(group_files)} 个文件")
        
        # 创建组输出目录
        Path(group_output_dir).mkdir(parents=True, exist_ok=True)
        
        group_data = []
        group_stats = []
        
        # 读取所有文件数据并计算统计量
        for file_path in group_files:
            try:
                df, channel_info = read_fft_data(file_path)
                
                # 计算统计量
                fft_stats = calculate_fft_statistics(df, channel_info)
                phase_analysis = analyze_phase_relationships(df, channel_info)
                
                group_data.append({
                    'file_path': str(file_path),
                    'df': df,
                    'channel_info': channel_info
                })
                
                group_stats.append({
                    'file_path': str(file_path),
                    'fft_stats': fft_stats,
                    'phase_analysis': phase_analysis
                })
                
            except Exception as e:
                logger.error(f"处理FFT文件 {file_path} 时出错: {str(e)}")
                continue
        
        if not group_data:
            logger.warning("组内没有成功处理的文件")
            return None
        
        group_name = Path(group_files[0]).parent.name
        
        # 生成组分析图表和报告
        plot_group_amplitude_spectrum(group_data, Path(group_output_dir) / 'group_amplitude_spectrum.png')
        plot_group_phase_analysis(group_data, Path(group_output_dir) / 'group_phase_analysis.png')
        dominant_results = plot_group_dominant_frequencies(group_stats, Path(group_output_dir) / 'group_dominant_frequencies.png')
        stability_results = plot_group_stability_analysis(group_stats, Path(group_output_dir) / 'group_stability_analysis.png')
        feature_results = plot_group_feature_frequencies(group_data, target_frequencies, Path(group_output_dir) / 'group_feature_frequencies.png')
        
        report = generate_group_analysis_report(group_stats, group_name, Path(group_output_dir) / 'frequency_plots_report.json')
        
        logger.info(f"FFT组分析完成: {group_name}")
        
        return {
            'group_name': str(group_name),
            'output_dir': str(group_output_dir),
            'file_count': len(group_files),
            'successful_files': len(group_data),
            'dominant_frequencies': dominant_results,
            'stability_analysis': stability_results,
            'feature_frequencies': feature_results,
            'report': report
        }
        
    except Exception as e:
        logger.error(f"分析FFT组失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def main():
    """主函数"""
    try:
        # 加载配置
        config = load_config()
        
        # 输入输出路径 - 使用频率相关路径
        input_dir = config["tdms_reader_frequency_output_dir"]
        output_dir = config["frequency_results_dir"]
        
        logger.info(f"FFT输入目录: {input_dir}")
        logger.info(f"FFT输出目录: {output_dir}")
        
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 按组查找所有平均FFT CSV文件
#        csv_files = list(Path(input_dir).glob('**/average_fft_*.csv'))
        csv_files = list(Path(input_dir).glob('**/*.csv'))       
        if not csv_files:
            logger.warning(f"在 {input_dir} 中未找到平均FFT CSV文件")
            return
        
        logger.info(f"找到 {len(csv_files)} 个平均FFT CSV文件")
        
        # 按组分组文件
        groups = {}
        for csv_file in csv_files:
            group_name = csv_file.parent.name
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(csv_file)
        
        logger.info(f"找到 {len(groups)} 个FFT组: {list(groups.keys())}")
        
        # 定义目标特征频率（根据实际需求修改）
        target_frequencies = [50, 100, 150, 200, 250]  # 示例频率
        
        # 分析每个组
        results = []
        for group_name, group_files in groups.items():
            logger.info(f"分析FFT组 {group_name}, 包含 {len(group_files)} 个文件")
            
            group_output_dir = Path(output_dir) / group_name
            result = analyze_group(group_files, group_output_dir, target_frequencies)
            
            if result:
                results.append(result)
        
        # 生成总体报告
        summary = {
            'analysis_time': datetime.now().isoformat(),
            'total_groups': len(groups),
            'analyzed_groups': len(results),
            'total_files': len(csv_files),
            'target_frequencies': target_frequencies,
            'group_results': []
        }
        
        for result in results:
            summary['group_results'].append({
                'group_name': str(result['group_name']),
                'file_count': result['file_count'],
                'successful_files': result['successful_files'],
                'output_dir': str(result['output_dir'])
            })
        
        summary_path = Path(output_dir) / 'fft_analysis_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"FFT分析完成! 成功分析 {len(results)} 个组")
        logger.info(f"总体报告: {summary_path}")
        
    except Exception as e:
        logger.error(f"FFT分析主程序失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()