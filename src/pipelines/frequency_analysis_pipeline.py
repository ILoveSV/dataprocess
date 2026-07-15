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
import argparse
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

from src.utils.perf_timing import add_counter, record_file_size, timed_step
from src.utils.cache_utils import build_cache_metadata, is_cache_hit, write_cache_metadata

# Set plotting style
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

# 设置matplotlib不显示图形窗口
plt.switch_backend('Agg')

logger = logging.getLogger('data_process')

PLOT_MODES = ('none', 'minimal', 'full')


def _downsample_indices(length, max_points=None):
    if max_points is None or max_points <= 0 or length <= max_points:
        return slice(None)
    step = max(1, int(np.ceil(length / max_points)))
    return slice(None, None, step)


def _save_figure(fig, output_path, dpi=150):
    output_path = Path(output_path)
    with timed_step('freqplots.savefig', file=output_path.name, dpi=dpi):
        fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
    add_counter('freqplots.png_files', 1)
    record_file_size(output_path, 'freqplots.png_bytes')
    record_file_size(output_path, f'freqplots.png_bytes.{output_path.name}')
    logger.info("Figure saved: %s", output_path)

def _robust_ylim(values, default=(0.0, 1.0), low_q=1.0, high_q=99.5, pad_ratio=0.15):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return list(default)

    lo = np.percentile(arr, low_q)
    hi = np.percentile(arr, high_q)
    if not np.isfinite(lo) or not np.isfinite(hi):
        return list(default)
    if hi <= lo:
        hi = lo + 1.0

    pad = (hi - lo) * pad_ratio
    y0 = max(0.0, lo - pad)
    y1 = hi + pad
    if y1 <= y0:
        y1 = y0 + 1.0
    return [float(y0), float(y1)]


def _safe_positive(values, eps=1e-12):
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, np.nan)
    return np.maximum(arr, eps)


def _collect_channel_matrix(group_data, channel_name):
    matrices = []
    frequency = None
    expected_length = None
    for file_data in group_data:
        df = file_data['df']
        if channel_name not in df.columns:
            continue
        current_frequency = df['frequency'].to_numpy(dtype=float)
        current_values = df[channel_name].to_numpy(dtype=float)

        if frequency is None:
            frequency = current_frequency
            expected_length = len(current_values)
            matrices.append(current_values)
            continue

        if len(current_values) != expected_length or len(current_frequency) != len(frequency):
            logger.warning(
                f"Skipping {Path(file_data['file_path']).name} for {channel_name}: "
                f"inconsistent spectrum length ({len(current_values)} vs {expected_length})"
            )
            continue

        if not np.allclose(current_frequency, frequency):
            logger.warning(
                f"Skipping {Path(file_data['file_path']).name} for {channel_name}: inconsistent frequency axis"
            )
            continue

        matrices.append(current_values)

    if not matrices or frequency is None:
        return None, None
    return frequency, np.vstack(matrices)


def _plot_spectrum_band(group_data, output_path, band, title_suffix, dpi=150, max_plot_points=5000):
    fig, axes = plt.subplots(4, 4, figsize=(22, 18))
    axes = axes.flatten()

    sample_file = group_data[0]
    amplitude_channels = sample_file['channel_info']['amplitude_channels']
    group_name = Path(group_data[0]['file_path']).parent.name
    freq_min, freq_max = band

    for i, channel in enumerate(amplitude_channels):
        if i >= len(axes):
            break

        ax = axes[i]
        frequency, amplitude_matrix = _collect_channel_matrix(group_data, channel)
        if frequency is None or amplitude_matrix is None:
            ax.set_visible(False)
            continue

        mask = (frequency >= freq_min) & (frequency <= freq_max)
        if not np.any(mask):
            ax.set_visible(False)
            continue

        freq_slice = frequency[mask]
        amp_slice = amplitude_matrix[:, mask]
        plot_idx = _downsample_indices(len(freq_slice), max_plot_points)
        freq_plot = freq_slice[plot_idx]
        amp_plot = amp_slice[:, plot_idx]
        mean_spectrum = np.mean(amp_plot, axis=0)
        std_spectrum = np.std(amp_plot, axis=0)
        lower = np.maximum(mean_spectrum - std_spectrum, 1e-12)
        upper = np.maximum(mean_spectrum + std_spectrum, lower * 1.001)

        ax.fill_between(freq_plot, lower, upper, color='#9ecae1', alpha=0.45, label='Mean +/- 1 Std')
        ax.plot(freq_plot, _safe_positive(mean_spectrum), color='#08519c', linewidth=1.8, label='Mean Spectrum')
        ax.set_yscale('log')
        ax.set_title(channel.upper(), fontsize=12, fontweight='bold')
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('Amplitude (log)')
        ax.set_xlim(freq_plot.min(), freq_plot.max())
        ax.grid(True, alpha=0.3, which='both')

        if i == 0:
            ax.legend(loc='upper right', fontsize=8)

    for i in range(len(amplitude_channels), len(axes)):
        axes[i].set_visible(False)

    plt.suptitle(f'Group {group_name} - {title_suffix}', fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    _save_figure(fig, output_path, dpi=dpi)
    plt.close(fig)
    logger.info(f"Amplitude band figure saved: {output_path}")


def _plot_channel_peak_windows(group_data, output_path, dpi=150, max_plot_points=5000):
    fig, axes = plt.subplots(4, 4, figsize=(22, 18))
    axes = axes.flatten()

    sample_file = group_data[0]
    amplitude_channels = sample_file['channel_info']['amplitude_channels']
    group_name = Path(group_data[0]['file_path']).parent.name

    for i, channel in enumerate(amplitude_channels):
        if i >= len(axes):
            break

        ax = axes[i]
        frequency, amplitude_matrix = _collect_channel_matrix(group_data, channel)
        if frequency is None or amplitude_matrix is None:
            ax.set_visible(False)
            continue

        mean_spectrum = np.mean(amplitude_matrix, axis=0)
        valid_mask = (frequency >= 1000) & (frequency <= 50000)
        if not np.any(valid_mask):
            ax.set_visible(False)
            continue

        valid_indices = np.where(valid_mask)[0]
        peak_rel_idx = np.argmax(mean_spectrum[valid_mask])
        peak_idx = valid_indices[peak_rel_idx]
        peak_frequency = frequency[peak_idx]
        window_half_width = max(500.0, peak_frequency * 0.1)
        mask = (frequency >= peak_frequency - window_half_width) & (frequency <= peak_frequency + window_half_width)

        freq_slice = frequency[mask]
        amp_slice = amplitude_matrix[:, mask]
        plot_idx = _downsample_indices(len(freq_slice), max_plot_points)
        freq_plot = freq_slice[plot_idx]
        amp_plot = amp_slice[:, plot_idx]
        mean_slice = np.mean(amp_plot, axis=0)
        std_slice = np.std(amp_plot, axis=0)
        lower = np.maximum(mean_slice - std_slice, 1e-12)
        upper = np.maximum(mean_slice + std_slice, lower * 1.001)

        ax.fill_between(freq_plot, lower, upper, color='#fdd0a2', alpha=0.45)
        ax.plot(freq_plot, _safe_positive(mean_slice), color='#d94801', linewidth=1.8)
        ax.axvline(peak_frequency, color='#7f2704', linestyle='--', linewidth=1)
        ax.set_yscale('log')
        ax.set_title(f"{channel.upper()} @ {peak_frequency:.1f} Hz", fontsize=11, fontweight='bold')
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('Amplitude (log)')
        ax.set_xlim(freq_plot.min(), freq_plot.max())
        ax.grid(True, alpha=0.3, which='both')

    for i in range(len(amplitude_channels), len(axes)):
        axes[i].set_visible(False)

    plt.suptitle(f'Group {group_name} - Channel Peak Windows', fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    _save_figure(fig, output_path, dpi=dpi)
    plt.close(fig)
    logger.info(f"Channel peak window figure saved: {output_path}")


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
        
        with timed_step('freqplots.csv_read', file=Path(csv_file_path).name):
            df = pd.read_csv(csv_file_path)
        add_counter('freqplots.input_files', 1)
        add_counter('freqplots.input_rows', len(df))
        
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
        with timed_step('freqplots.statistics', channel=channel):
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


def calculate_fft_statistics(df, channel_info):
    """Calculate FFT statistics with per-channel timing."""
    stats_results = {}
    amplitude_channels = channel_info['amplitude_channels']

    for channel in amplitude_channels:
        with timed_step('freqplots.statistics', channel=channel):
            amplitude = df[channel]
            frequency = df['frequency']
            peaks, properties = signal.find_peaks(amplitude, height=amplitude.max() * 0.05, distance=10)

            dominant_frequencies = []
            dominant_amplitudes = []

            if len(peaks) > 0:
                sorted_peaks = peaks[np.argsort(amplitude.iloc[peaks])[::-1]]
                top_peaks = sorted_peaks[:20]
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
                'frequency_range': [float(frequency.min()), float(frequency.max())],
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

def plot_group_amplitude_spectrum(group_data, output_path, dpi=150, max_plot_points=5000):
    """Plot grouped amplitude spectra using log-scale information bands."""
    try:
        logger.info("Generating log-scale spectrum bands")
        output_path_1 = str(output_path).replace('.png', '_1.png')
        _plot_spectrum_band(group_data, output_path_1, (0, 200), 'Low-Frequency Background (0-200 Hz, log scale)', dpi=dpi, max_plot_points=max_plot_points)
        output_path_2 = str(output_path).replace('.png', '_2.png')
        _plot_spectrum_band(group_data, output_path_2, (1000, 10000), 'Primary Feature Band (1-10 kHz, log scale)', dpi=dpi, max_plot_points=max_plot_points)
        output_path_3 = str(output_path).replace('.png', '_3.png')
        _plot_spectrum_band(group_data, output_path_3, (10000, 50000), 'High-Frequency Harmonics (10-50 kHz, log scale)', dpi=dpi, max_plot_points=max_plot_points)
        peak_windows_output = str(output_path).replace('.png', '_peak_windows.png')
        _plot_channel_peak_windows(group_data, peak_windows_output, dpi=dpi, max_plot_points=max_plot_points)

    except Exception as e:
        logger.error(f"Failed to plot amplitude spectra: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def plot_group_phase_analysis(group_data, output_path, dpi=150, max_plot_points=5000):
    """????????"""
    try:
        logger.info("??????????")

        if not group_data:
            logger.warning("???????")
            return

        sample_data = group_data[0]
        df = sample_data['df']
        channel_info = sample_data['channel_info']
        phase_channels = channel_info['phase_channels']

        if len(phase_channels) < 2:
            logger.warning("?????????????????")
            return

        fig, axes = plt.subplots(2, 1, figsize=(15, 12))

        max_freq = min(1000, df['frequency'].max())
        phase_mask = df['frequency'] <= max_freq
        phase_freq = df.loc[phase_mask, 'frequency']
        step = max(1, int(np.ceil(len(phase_freq) / max_plot_points))) if max_plot_points else max(1, len(phase_freq) // 3000)
        phase_freq = phase_freq.iloc[::step]

        ax1 = axes[0]
        for channel in phase_channels:
            phase = df.loc[phase_mask, channel].iloc[::step]
            ax1.plot(phase_freq, phase, label=channel, alpha=0.65, linewidth=0.9)

        ax1.set_title('Phase Spectrum of All Channels', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Phase (rad)')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, max_freq)
        ax1.set_ylim(-np.pi, np.pi)

        ax2 = axes[1]
        reference_channel = phase_channels[0]
        all_phase_diffs = []

        for channel in phase_channels[1:]:
            phase_diff = df.loc[phase_mask, channel] - df.loc[phase_mask, reference_channel]
            phase_diff_unwrapped = np.unwrap(phase_diff)
            phase_diff_centered = phase_diff_unwrapped - np.mean(phase_diff_unwrapped)
            all_phase_diffs.extend(phase_diff_centered[::step])
            ax2.plot(phase_freq, phase_diff_centered[::step],
                     label=f'{channel} - {reference_channel}', alpha=0.7)

        ax2.set_title('Phase Difference Relative to Reference Channel (Centered)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Phase Difference (rad)')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, max_freq)
        ax2.set_ylim(_robust_ylim(all_phase_diffs, default=(-10.0, 10.0), low_q=2.0, high_q=98.0, pad_ratio=0.2))

        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Phase Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        fig = plt.gcf()
        _save_figure(fig, output_path, dpi=dpi)
        plt.close(fig)

        logger.info(f"?????????: {output_path}")

    except Exception as e:
        logger.error(f"??????????: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def _collect_dominant_frequency_rows(group_stats):
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
    return all_dominant_freqs


def plot_group_dominant_frequencies(group_stats, output_path, dominant_results=None, dpi=150):
    """??????????"""
    try:
        logger.info("????????????")

        if not group_stats:
            logger.warning("?????????")
            return

        all_dominant_freqs = _collect_dominant_frequency_rows(group_stats)

        if not all_dominant_freqs:
            logger.warning("????????")
            return

        df_dominant = dominant_results if dominant_results is not None else pd.DataFrame(all_dominant_freqs)

        plt.figure(figsize=(15, 10))
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
        max_freq = float(df_dominant['frequency'].max())
        plt.xlim(0, max_freq * 1.05 if max_freq > 0 else 1)

        if len(df_dominant) > 0:
            freq_counts = df_dominant['frequency'].value_counts().head(5)
            y_top = plt.ylim()[1]
            for freq, count in freq_counts.items():
                plt.axvline(x=freq, color='red', linestyle='--', alpha=0.5)
                plt.text(freq, y_top * 0.9, f'{freq:.1f}Hz\\n({count} times)',
                         ha='center', fontsize=8, color='red')

        group_name = Path(group_stats[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Dominant Frequency Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        fig = plt.gcf()
        _save_figure(fig, output_path, dpi=dpi)
        plt.close(fig)

        logger.info(f"???????????: {output_path}")

        return df_dominant

    except Exception as e:
        logger.error(f"????????????: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def compute_group_stability_analysis(group_data):
    """Compute stability metrics from already loaded FFT data."""
    if len(group_data) < 2:
        logger.warning("Need at least 2 files for stability analysis")
        return None

    first_file_data = group_data[0]['df']
    first_channel_info = group_data[0]['channel_info']
    frequency = first_file_data['frequency']
    amplitude_channels = first_channel_info['amplitude_channels']

    if not amplitude_channels:
        logger.warning("No amplitude channels for stability analysis")
        return None

    reference_channel = amplitude_channels[0]
    expected_length = len(first_file_data[reference_channel])
    all_amplitudes = []

    for file_data in group_data:
        df = file_data['df']
        if reference_channel not in df.columns:
            logger.warning("Skipping %s: missing %s", file_data['file_path'], reference_channel)
            continue
        current_amplitude = df[reference_channel].values
        current_length = len(current_amplitude)
        if current_length != expected_length:
            logger.warning(
                "Skipping %s: spectrum length mismatch (%s vs %s)",
                Path(file_data['file_path']).name,
                current_length,
                expected_length,
            )
            continue
        all_amplitudes.append(current_amplitude)

    if len(all_amplitudes) < 2:
        logger.warning("Not enough consistent files for stability analysis")
        return None

    all_amplitudes = np.array(all_amplitudes)
    mean_amplitude = np.mean(all_amplitudes, axis=0)
    std_amplitude = np.std(all_amplitudes, axis=0)
    cv_amplitude = std_amplitude / (mean_amplitude + 1e-8)

    return {
        'frequency': frequency,
        'mean_amplitude_array': mean_amplitude,
        'std_amplitude_array': std_amplitude,
        'cv_amplitude_array': cv_amplitude,
        'mean_amplitude': mean_amplitude.tolist(),
        'std_amplitude': std_amplitude.tolist(),
        'cv_amplitude': cv_amplitude.tolist(),
        'overall_cv': float(np.mean(cv_amplitude[frequency < 500])),
        'file_count': len(all_amplitudes),
        'reference_channel': reference_channel,
    }


def plot_group_stability_analysis(group_data, output_path, stability_analysis=None, dpi=150, max_plot_points=5000):
    """???????????"""
    try:
        logger.info("?????????????")
        if len(group_data) < 2:
            logger.warning("????2??????????")
            return

        stability_analysis = stability_analysis or compute_group_stability_analysis(group_data)
        if not stability_analysis:
            logger.warning("??????????????")
            return

        frequency = np.asarray(stability_analysis['frequency'])
        mean_amplitude = np.asarray(stability_analysis['mean_amplitude_array'])
        std_amplitude = np.asarray(stability_analysis['std_amplitude_array'])
        cv_amplitude = np.asarray(stability_analysis['cv_amplitude_array'])
        reference_channel = stability_analysis['reference_channel']
        plot_idx = _downsample_indices(len(frequency), max_plot_points)
        frequency_plot = frequency[plot_idx]
        mean_plot = mean_amplitude[plot_idx]
        std_plot = std_amplitude[plot_idx]
        cv_plot = cv_amplitude[plot_idx]

        fig, axes = plt.subplots(2, 1, figsize=(15, 10))

        ax1 = axes[0]
        ax1.plot(frequency_plot, mean_plot, 'b-', label='Mean', linewidth=2)
        ax1.fill_between(frequency_plot, mean_plot - std_plot,
                         mean_plot + std_plot, alpha=0.3, label='+/- 1 Std Dev')
        ax1.set_title('Mean Amplitude with Std Envelope', fontsize=13, fontweight='bold')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Amplitude')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, min(1000, frequency.max()))

        ax2 = axes[1]
        ax2.plot(frequency_plot, cv_plot, 'r-', linewidth=2)
        ax2.set_title('Amplitude Coefficient of Variation (CV)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Coefficient of Variation')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, min(1000, frequency.max()))

        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Frequency Stability Analysis (Channel {reference_channel})',
                     fontsize=15, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        _save_figure(fig, output_path, dpi=dpi)
        plt.close(fig)

        logger.info(f"????????????: {output_path}")

        return stability_analysis

    except Exception as e:
        logger.error(f"?????????????: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def compute_feature_frequency_results(group_data, target_frequencies):
    if not group_data:
        return None
    sample_data = group_data[0]
    df = sample_data['df']
    channel_info = sample_data['channel_info']
    amplitude_channels = channel_info['amplitude_channels']
    frequency = df['frequency']

    if target_frequencies is None:
        target_frequencies = auto_detect_feature_frequencies(df, channel_info)

    if not target_frequencies:
        return None

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


def plot_group_feature_frequencies(group_data, target_frequencies, output_path, feature_results=None, dpi=150, max_plot_points=5000):
    """??????????"""
    try:
        logger.info("????????????")

        if not group_data:
            logger.warning("???????")
            return

        sample_data = group_data[0]
        df = sample_data['df']
        channel_info = sample_data['channel_info']
        amplitude_channels = channel_info['amplitude_channels']
        frequency = df['frequency']

        if target_frequencies is None:
            target_frequencies = auto_detect_feature_frequencies(df, channel_info)

        if not target_frequencies:
            logger.warning("????????")
            return

        fig = plt.figure(figsize=(15, 8))
        ax = plt.gca()
        plot_idx = _downsample_indices(len(frequency), max_plot_points)

        for channel in amplitude_channels[:4]:
            amplitude = df[channel]
            plt.plot(frequency.iloc[plot_idx], amplitude.iloc[plot_idx], label=channel, alpha=0.7)

        max_freq = min(1000, frequency.max())
        y_values = []
        y_mask = (frequency >= 20) & (frequency <= max_freq)
        for channel in amplitude_channels[:4]:
            y_values.extend(df.loc[y_mask, channel].values)

        plt.title('Feature Frequency Extraction', fontsize=16, fontweight='bold')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xlim(0, max_freq)
        plt.ylim(_robust_ylim(y_values))

        y_top = plt.ylim()[1]
        for target_freq in target_frequencies:
            ax.axvline(target_freq, color='red', linestyle='--', alpha=0.55, linewidth=1)
            ax.text(target_freq + 3, y_top * 0.92, f'{target_freq}Hz',
                    fontsize=8, color='red', rotation=90, va='top')

        group_name = Path(group_data[0]['file_path']).parent.name
        plt.suptitle(f'Group {group_name} - Feature Frequency Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        _save_figure(fig, output_path, dpi=dpi)
        plt.close(fig)

        logger.info(f"???????????: {output_path}")

        return feature_results or compute_feature_frequency_results(group_data, target_frequencies)

    except Exception as e:
        logger.error(f"????????????: {str(e)}")
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

def plot_group_mean_amplitude_summary(group_data, output_path, dpi=150, max_plot_points=5000):
    """Plot a compact group-level mean amplitude summary for minimal mode."""
    try:
        if not group_data:
            return None

        sample_data = group_data[0]
        amplitude_channels = sample_data['channel_info']['amplitude_channels']
        group_name = Path(sample_data['file_path']).parent.name
        fig, ax = plt.subplots(figsize=(14, 8))

        plotted = 0
        for channel in amplitude_channels[:4]:
            frequency, amplitude_matrix = _collect_channel_matrix(group_data, channel)
            if frequency is None or amplitude_matrix is None:
                continue
            mask = frequency <= min(5000, frequency.max())
            if not np.any(mask):
                continue
            freq_slice = frequency[mask]
            mean_spectrum = np.mean(amplitude_matrix[:, mask], axis=0)
            plot_idx = _downsample_indices(len(freq_slice), max_plot_points)
            ax.plot(
                freq_slice[plot_idx],
                _safe_positive(mean_spectrum[plot_idx]),
                linewidth=1.4,
                label=channel,
                alpha=0.85,
            )
            plotted += 1

        if plotted == 0:
            plt.close(fig)
            return None

        ax.set_yscale('log')
        ax.set_title('Mean Amplitude Spectrum Summary', fontsize=15, fontweight='bold')
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('Amplitude (log)')
        ax.grid(True, alpha=0.3, which='both')
        ax.legend()
        plt.suptitle(f'Group {group_name}', fontsize=16, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        _save_figure(fig, output_path, dpi=dpi)
        plt.close(fig)
        return output_path

    except Exception as e:
        logger.error("Failed to plot minimal amplitude summary: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return None


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
    
def compute_freqplot_metrics(group_files, group_output_dir, target_frequencies=None):
    """Read FFT CSV files once and compute all non-PNG freqplot metrics."""
    logger.info("Computing freqplot metrics for %s files", len(group_files))
    Path(group_output_dir).mkdir(parents=True, exist_ok=True)

    group_data = []
    group_stats = []
    for file_path in group_files:
        try:
            df, channel_info = read_fft_data(file_path)
            fft_stats = calculate_fft_statistics(df, channel_info)
            phase_analysis = analyze_phase_relationships(df, channel_info)

            group_data.append({
                'file_path': str(file_path),
                'df': df,
                'channel_info': channel_info,
            })
            group_stats.append({
                'file_path': str(file_path),
                'fft_stats': fft_stats,
                'phase_analysis': phase_analysis,
            })
        except Exception as e:
            logger.error("Failed to process FFT file %s: %s", file_path, e)
            continue

    if not group_data:
        logger.warning("No FFT data was loaded for group")
        return None

    group_name = Path(group_files[0]).parent.name
    dominant_results = pd.DataFrame(_collect_dominant_frequency_rows(group_stats))
    stability_results = compute_group_stability_analysis(group_data)
    feature_results = compute_feature_frequency_results(group_data, target_frequencies)

    report_path = Path(group_output_dir) / 'frequency_plots_report.json'
    with timed_step('freqplots.json_write', group=group_name):
        report = generate_group_analysis_report(group_stats, group_name, report_path)
    if report_path.exists():
        add_counter('freqplots.output_files', 1)
        record_file_size(report_path, 'freqplots.output_bytes')

    dominant_csv = Path(group_output_dir) / 'dominant_frequencies.csv'
    if not dominant_results.empty:
        with timed_step('freqplots.csv_write', file=dominant_csv.name, rows=len(dominant_results)):
            dominant_results.to_csv(dominant_csv, index=False, encoding='utf-8-sig')
        add_counter('freqplots.output_files', 1)
        record_file_size(dominant_csv, 'freqplots.output_bytes')

    return {
        'group_name': str(group_name),
        'output_dir': str(group_output_dir),
        'file_count': len(group_files),
        'successful_files': len(group_data),
        'group_data': group_data,
        'group_stats': group_stats,
        'dominant_frequencies': dominant_results,
        'stability_analysis': stability_results,
        'feature_frequencies': feature_results,
        'target_frequencies': target_frequencies,
        'report': report,
    }


def _json_ready_result(result):
    return {
        key: value for key, value in result.items()
        if key not in {'group_data', 'group_stats'}
    }


def render_freqplot_figures(metrics, plots='minimal', dpi=150, max_plot_points=5000):
    """Render selected freqplot figures from cached metric data."""
    if metrics is None or plots == 'none':
        return metrics

    group_data = metrics['group_data']
    group_stats = metrics['group_stats']
    group_name = metrics['group_name']
    output_dir = Path(metrics['output_dir'])
    rendered = []

    if plots == 'minimal':
        with timed_step('freqplots.plotting', group=group_name, plot='mean_amplitude_summary'):
            path = output_dir / 'group_mean_amplitude_summary.png'
            if plot_group_mean_amplitude_summary(group_data, path, dpi=dpi, max_plot_points=max_plot_points):
                rendered.append(str(path))
        with timed_step('freqplots.plotting', group=group_name, plot='dominant_frequencies'):
            path = output_dir / 'group_dominant_frequencies.png'
            plot_group_dominant_frequencies(
                group_stats,
                path,
                dominant_results=metrics.get('dominant_frequencies'),
                dpi=dpi,
            )
            if path.exists():
                rendered.append(str(path))

    elif plots == 'full':
        with timed_step('freqplots.plotting', group=group_name, plot='amplitude_spectrum'):
            plot_group_amplitude_spectrum(
                group_data,
                output_dir / 'group_amplitude_spectrum.png',
                dpi=dpi,
                max_plot_points=max_plot_points,
            )
        with timed_step('freqplots.plotting', group=group_name, plot='phase_analysis'):
            plot_group_phase_analysis(
                group_data,
                output_dir / 'group_phase_analysis.png',
                dpi=dpi,
                max_plot_points=max_plot_points,
            )
        with timed_step('freqplots.plotting', group=group_name, plot='dominant_frequencies'):
            plot_group_dominant_frequencies(
                group_stats,
                output_dir / 'group_dominant_frequencies.png',
                dominant_results=metrics.get('dominant_frequencies'),
                dpi=dpi,
            )
        with timed_step('freqplots.plotting', group=group_name, plot='stability_analysis'):
            plot_group_stability_analysis(
                group_data,
                output_dir / 'group_stability_analysis.png',
                stability_analysis=metrics.get('stability_analysis'),
                dpi=dpi,
                max_plot_points=max_plot_points,
            )
        with timed_step('freqplots.plotting', group=group_name, plot='feature_frequencies'):
            plot_group_feature_frequencies(
                group_data,
                metrics.get('target_frequencies') or [50, 100, 150, 200, 250],
                output_dir / 'group_feature_frequencies.png',
                feature_results=metrics.get('feature_frequencies'),
                dpi=dpi,
                max_plot_points=max_plot_points,
            )
        rendered.extend(str(path) for path in output_dir.glob('*.png'))
    else:
        raise ValueError(f"Unsupported plots mode: {plots}")

    metrics['rendered_figures'] = sorted(set(rendered))
    return metrics


def expected_freqplot_outputs(groups, output_dir, plots):
    output_dir = Path(output_dir)
    outputs = [output_dir / 'fft_analysis_summary.json']
    for group_name in sorted(groups):
        group_output_dir = output_dir / group_name
        outputs.extend([
            group_output_dir / 'frequency_plots_report.json',
            group_output_dir / 'dominant_frequencies.csv',
        ])
        if plots == 'minimal':
            outputs.extend([
                group_output_dir / 'group_mean_amplitude_summary.png',
                group_output_dir / 'group_dominant_frequencies.png',
            ])
        elif plots == 'full':
            outputs.extend([
                group_output_dir / 'group_amplitude_spectrum_1.png',
                group_output_dir / 'group_amplitude_spectrum_2.png',
                group_output_dir / 'group_amplitude_spectrum_3.png',
                group_output_dir / 'group_amplitude_spectrum_peak_windows.png',
                group_output_dir / 'group_phase_analysis.png',
                group_output_dir / 'group_dominant_frequencies.png',
                group_output_dir / 'group_stability_analysis.png',
                group_output_dir / 'group_feature_frequencies.png',
            ])
    return outputs


def analyze_group(group_files, group_output_dir, target_frequencies=None, plots='minimal', dpi=150, max_plot_points=5000):
    """Analyze one FFT group with separate metric computation and optional rendering."""
    try:
        metrics = compute_freqplot_metrics(group_files, group_output_dir, target_frequencies)
        if metrics is None:
            return None
        render_freqplot_figures(metrics, plots=plots, dpi=dpi, max_plot_points=max_plot_points)
        logger.info("FFT group analysis complete: %s", metrics['group_name'])
        return _json_ready_result(metrics)
    except Exception as e:
        logger.error("FFT group analysis failed: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return None


def _legacy_analyze_group(group_files, group_output_dir, target_frequencies=None):
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
        with timed_step('freqplots.plotting', group=group_name, plot='amplitude_spectrum'):
            plot_group_amplitude_spectrum(group_data, Path(group_output_dir) / 'group_amplitude_spectrum.png')
        with timed_step('freqplots.plotting', group=group_name, plot='phase_analysis'):
            plot_group_phase_analysis(group_data, Path(group_output_dir) / 'group_phase_analysis.png')
        with timed_step('freqplots.plotting', group=group_name, plot='dominant_frequencies'):
            dominant_results = plot_group_dominant_frequencies(group_stats, Path(group_output_dir) / 'group_dominant_frequencies.png')
        with timed_step('freqplots.plotting', group=group_name, plot='stability_analysis'):
            stability_results = plot_group_stability_analysis(group_stats, Path(group_output_dir) / 'group_stability_analysis.png')
        with timed_step('freqplots.plotting', group=group_name, plot='feature_frequencies'):
            feature_results = plot_group_feature_frequencies(group_data, target_frequencies, Path(group_output_dir) / 'group_feature_frequencies.png')

        report_path = Path(group_output_dir) / 'frequency_plots_report.json'
        with timed_step('freqplots.json_write', group=group_name):
            report = generate_group_analysis_report(group_stats, group_name, report_path)
        if report_path.exists():
            add_counter('freqplots.output_files', 1)
            record_file_size(report_path, 'freqplots.output_bytes')

        for output_file in Path(group_output_dir).glob('*.png'):
            add_counter('freqplots.output_files', 1)
            record_file_size(output_file, 'freqplots.output_bytes')
        
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

def main(argv=None):
    parser = argparse.ArgumentParser(description='Run frequency-domain metrics and optional plots')
    parser.add_argument('--input', '-i', default=None, help='Input FFT CSV file or folder')
    parser.add_argument('--output', '-o', default=None, help='Output folder')
    parser.add_argument('--plots', choices=PLOT_MODES, default='minimal')
    parser.add_argument('--dpi', type=int, default=150)
    parser.add_argument('--max-plot-points', type=int, default=5000)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', default=True)
    parser.add_argument('--no-skip-existing', dest='skip_existing', action='store_false')
    args = parser.parse_args(argv)

    with timed_step('freqplots.module_total'):
        config = load_config()
        input_dir = args.input or config["tdms_reader_frequency_output_dir"]
        output_dir = args.output or config["frequency_results_dir"]

        logger.info("resolved input dir: %s", Path(input_dir).resolve())
        logger.info("resolved output dir: %s", Path(output_dir).resolve())
        logger.info("plots mode: %s", args.plots)
        logger.info("plot options: dpi=%s, max_plot_points=%s", args.dpi, args.max_plot_points)

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        input_path = Path(input_dir)
        with timed_step('freqplots.file_scan', folder=input_dir):
            if input_path.is_file():
                csv_files = [input_path]
            else:
                csv_files = list(input_path.glob('**/*.csv'))
        add_counter('freqplots.discovered_files', len(csv_files))
        if not csv_files:
            logger.warning("No FFT CSV files found in %s", input_dir)
            return []

        groups = {}
        for csv_file in csv_files:
            group_name = csv_file.parent.name
            groups.setdefault(group_name, []).append(csv_file)

        target_frequencies = [50, 100, 150, 200, 250]
        params = {
            'stage': 'freqplots',
            'plots': args.plots,
            'dpi': args.dpi,
            'max_plot_points': args.max_plot_points,
            'target_frequencies': target_frequencies,
            'output_schema': 'frequency_plots_report+dominant_csv+optional_pngs',
        }
        expected_outputs = expected_freqplot_outputs(groups, output_dir, args.plots)
        metadata_path = Path(output_dir) / '.cache' / 'freqplots_cache.json'
        hit, reason = is_cache_hit(
            'freqplots',
            csv_files,
            expected_outputs,
            params,
            metadata_path,
            force=args.force,
            skip_existing=args.skip_existing,
        )
        if hit:
            return []

        results = []
        for group_name, group_files in groups.items():
            group_output_dir = Path(output_dir) / group_name
            result = analyze_group(
                group_files,
                group_output_dir,
                target_frequencies,
                plots=args.plots,
                dpi=args.dpi,
                max_plot_points=args.max_plot_points,
            )
            if result:
                results.append(result)

        summary = {
            'analysis_time': datetime.now().isoformat(),
            'total_groups': len(groups),
            'analyzed_groups': len(results),
            'total_files': len(csv_files),
            'target_frequencies': target_frequencies,
            'plot_mode': args.plots,
            'dpi': args.dpi,
            'max_plot_points': args.max_plot_points,
            'group_results': [
                {
                    'group_name': str(result['group_name']),
                    'file_count': result['file_count'],
                    'successful_files': result['successful_files'],
                    'output_dir': str(result['output_dir']),
                }
                for result in results
            ],
        }

        summary_path = Path(output_dir) / 'fft_analysis_summary.json'
        with timed_step('freqplots.json_write', file=summary_path.name):
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        add_counter('freqplots.output_files', 1)
        record_file_size(summary_path, 'freqplots.output_bytes')
        write_cache_metadata(
            metadata_path,
            build_cache_metadata('freqplots', csv_files, expected_outputs, params, input_dir=input_dir, output_dir=output_dir),
        )
        return results


def _legacy_main():
    module_timer = timed_step('freqplots.module_total')
    module_timer.__enter__()
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
        with timed_step('freqplots.file_scan', folder=input_dir):
            csv_files = list(Path(input_dir).glob('**/*.csv'))
        add_counter('freqplots.discovered_files', len(csv_files))
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
        with timed_step('freqplots.json_write', file=summary_path.name):
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        add_counter('freqplots.output_files', 1)
        record_file_size(summary_path, 'freqplots.output_bytes')
        
        logger.info(f"FFT分析完成! 成功分析 {len(results)} 个组")
        logger.info(f"总体报告: {summary_path}")
        
    except Exception as e:
        logger.error(f"FFT分析主程序失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

    finally:
        module_timer.__exit__(None, None, None)

if __name__ == "__main__":
    main()
