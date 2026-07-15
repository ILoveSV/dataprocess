from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


MAX_PSD_PLOT_POINTS = 10000
PSD_PLOT_RANGES = (
    ('full_0_200k', 0.0, 200000.0, 'Welch PSD 0-200 kHz'),
    ('zoom_0_100Hz', 0.0, 100.0, 'Welch PSD 0-100 Hz'),
    ('zoom_0_1kHz', 0.0, 1000.0, 'Welch PSD 0-1 kHz'),
    ('zoom_0_10kHz', 0.0, 10000.0, 'Welch PSD 0-10 kHz'),
)
PSD_REVIEW_PLOT_RANGES = (
    ('full_0_200k', 0.0, 200000.0, 'Welch PSD 0-200 kHz'),
    *(
        (
            f'window_{start // 1000:03d}_{(start + 20_000) // 1000:03d}k',
            float(start),
            float(start + 20_000),
            f'Welch PSD {start // 1000}-{(start + 20_000) // 1000} kHz',
        )
        for start in range(0, 200_000, 20_000)
    ),
)
LOW_FREQ_PSD_PLOT_RANGES = (
    ('low_freq_0_100Hz', 0.0, 100.0, 'Low-frequency PSD 0-100 Hz'),
    ('low_freq_0_20Hz', 0.0, 20.0, 'Low-frequency PSD 0-20 Hz'),
    ('low_freq_0_5Hz', 0.0, 5.0, 'Low-frequency PSD 0-5 Hz'),
)


def plot_group_psd_ranges(plot_data, metrics, output_dir, title_prefix=None, group=None, channel=None):
    output_dir = Path(output_dir)
    paths = []
    file_prefix = _file_prefix(group, channel)
    for suffix, low, high, subtitle in PSD_PLOT_RANGES:
        path = output_dir / f'{file_prefix}_{suffix}.png'
        plot_group_psd(
            plot_data,
            metrics,
            path,
            title=f"{title_prefix} | {subtitle}" if title_prefix else subtitle,
            min_frequency=low,
            max_frequency=high,
            file_count=metrics.get('file_count'),
        )
        paths.append(path)
    low_data = plot_data.get('low_frequency') or {}
    for suffix, low, high, subtitle in LOW_FREQ_PSD_PLOT_RANGES:
        path = output_dir / f'{file_prefix}_{suffix}.png'
        plotted = plot_group_psd(
            low_data,
            metrics,
            path,
            title=f"{title_prefix} | {subtitle} | low_freq_df={_fmt(metrics.get('psd_low_freq_df'))} Hz" if title_prefix else f"{subtitle} | low_freq_df={_fmt(metrics.get('psd_low_freq_df'))} Hz",
            min_frequency=low,
            max_frequency=high,
            file_count=metrics.get('file_count'),
            low_frequency_plot=True,
        )
        if plotted is not None:
            paths.append(path)
    return paths


def plot_group_psd_review_ranges(plot_data, metrics, output_dir, title_prefix=None, group=None, channel=None):
    """Plot 0-200 kHz plus fixed 20 kHz PSD review windows."""
    output_dir = Path(output_dir)
    paths = []
    file_prefix = _file_prefix(group, channel)
    for suffix, low, high, subtitle in PSD_REVIEW_PLOT_RANGES:
        path = output_dir / f'{file_prefix}_{suffix}.png'
        plot_group_psd(
            plot_data,
            metrics,
            path,
            title=f"{title_prefix} | {subtitle}" if title_prefix else subtitle,
            min_frequency=low,
            max_frequency=high,
            file_count=metrics.get('file_count'),
        )
        paths.append(path)
    return paths


def plot_group_psd(plot_data, metrics, output_path, title=None, min_frequency=0.0, max_frequency=None, file_count=None, low_frequency_plot=False):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    freqs = np.asarray(plot_data.get('frequency', []), dtype=float)
    mean_power = np.asarray(plot_data.get('mean_power', []), dtype=float)
    median_power = np.asarray(plot_data.get('median_power', []), dtype=float)
    p10_power = np.asarray(plot_data.get('p10_power', []), dtype=float)
    p90_power = np.asarray(plot_data.get('p90_power', []), dtype=float)
    original_df = _frequency_resolution(freqs)

    if low_frequency_plot and max_frequency is not None and np.isfinite(original_df) and float(max_frequency) < 2 * original_df:
        print(f"Skipping {output_path}: requested freq_max={max_frequency} Hz is less than 2*df={original_df:.6g} Hz")
        return None
    unreliable_low_freq = low_frequency_plot and max_frequency is not None and np.isfinite(original_df) and float(max_frequency) < 5 * original_df

    mask = freqs >= float(min_frequency)
    if max_frequency is not None:
        mask &= freqs <= float(max_frequency)
    freqs = freqs[mask]
    mean_power = mean_power[mask]
    median_power = median_power[mask]
    p10_power = p10_power[mask]
    p90_power = p90_power[mask]
    freqs, mean_power, median_power, p10_power, p90_power = _downsample(freqs, mean_power, median_power, p10_power, p90_power)

    fig, ax = plt.subplots(figsize=(10, 5))
    if len(freqs):
        if file_count is not None and int(file_count) <= 1:
            ax.semilogy(freqs, mean_power, color='#805ad5', linewidth=1.0, label='PSD')
            ax.text(0.98, 0.98, 'single file only', transform=ax.transAxes, ha='right', va='top', fontsize=8)
        else:
            ax.fill_between(freqs, p10_power, p90_power, color='#b794f4', alpha=0.25, label='p10-p90')
            ax.semilogy(freqs, mean_power, color='#805ad5', linewidth=1.0, label='mean PSD')
            ax.semilogy(freqs, median_power, color='#2b6cb0', linewidth=1.0, alpha=0.9, label='median PSD')
    ax.set_title(title or 'Group Welch PSD')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('PSD')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=8)
    ax.text(
        0.02,
        0.98,
        f"dom_all={_fmt(metrics.get('psd_dom_all_freq_hz'))} Hz\n"
        f"dom_excl_low={_fmt(metrics.get('psd_dom_excl_low_freq_hz'))} Hz\n"
        f"df={_fmt(metrics.get('psd_df'))} Hz",
        transform=ax.transAxes,
        va='top',
        fontsize=8,
        bbox={'facecolor': 'white', 'alpha': 0.75, 'edgecolor': 'none'},
    )
    if unreliable_low_freq:
        ax.text(
            0.5,
            0.02,
            'only few bins, not reliable for low-frequency inference',
            transform=ax.transAxes,
            ha='center',
            va='bottom',
            fontsize=8,
            bbox={'facecolor': 'white', 'alpha': 0.75, 'edgecolor': 'none'},
        )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches='tight')
    plt.close(fig)
    return output_path


def _downsample(*arrays):
    if not arrays:
        return arrays
    n = min(len(array) for array in arrays)
    trimmed = [np.asarray(array)[:n] for array in arrays]
    if n <= MAX_PSD_PLOT_POINTS:
        return trimmed
    step = int(np.ceil(n / MAX_PSD_PLOT_POINTS))
    return [array[::step] for array in trimmed]


def _fmt(value):
    try:
        if value is None or not np.isfinite(value):
            return 'nan'
        return f'{float(value):.6g}'
    except (TypeError, ValueError):
        return 'nan'


def _frequency_resolution(freqs):
    freqs = np.asarray(freqs, dtype=float)
    if len(freqs) < 2:
        return np.nan
    diffs = np.diff(freqs)
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    return float(np.median(diffs)) if diffs.size else np.nan


def _file_prefix(group, channel):
    group = _safe_name(group or 'group')
    channel = _safe_name(channel or 'channel')
    return f'psd_group_{group}_{channel}'


def _safe_name(value):
    text = str(value)
    return ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in text)
