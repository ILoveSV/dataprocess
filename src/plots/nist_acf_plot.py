from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


ACF_PLOT_RANGES = (
    ('acf_zoom_0_0p5ms.png', 0.0005, 'ACF 0-0.5 ms'),
    ('acf_zoom_0_10ms.png', 0.010, 'ACF 0-10 ms'),
    ('acf_zoom_0_100ms.png', 0.100, 'ACF 0-100 ms'),
    ('acf_zoom_0_200ms.png', 0.200, 'ACF 0-200 ms'),
)
MAX_ACF_PLOT_POINTS = 10000


def plot_group_acf_ranges(plot_data, metrics, output_dir, title_prefix=None, max_psd_period_refs=1):
    output_dir = Path(output_dir)
    paths = []
    for filename, max_seconds, subtitle in ACF_PLOT_RANGES:
        path = output_dir / filename
        plot_group_acf(
            plot_data,
            metrics,
            path,
            title=f"{title_prefix} | {subtitle}" if title_prefix else subtitle,
            max_seconds=max_seconds,
            max_psd_period_refs=max_psd_period_refs,
        )
        paths.append(path)
    return paths


def plot_group_acf(plot_data, metrics, output_path, title=None, max_seconds=None, max_psd_period_refs=1):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seconds = np.asarray(plot_data.get('acf_lag_seconds', []), dtype=float)
    mean_acf = np.asarray(plot_data.get('acf_mean', []), dtype=float)
    median_acf = np.asarray(plot_data.get('acf_median', []), dtype=float)
    p10 = np.asarray(plot_data.get('acf_p10', []), dtype=float)
    p90 = np.asarray(plot_data.get('acf_p90', []), dtype=float)
    file_count = int(plot_data.get('acf_file_count') or metrics.get('file_count') or 0)

    if max_seconds is not None:
        mask = seconds <= float(max_seconds)
        seconds = seconds[mask]
        mean_acf = mean_acf[mask]
        median_acf = median_acf[mask]
        p10 = p10[mask]
        p90 = p90[mask]
    seconds, mean_acf, median_acf, p10, p90 = _downsample(seconds, mean_acf, median_acf, p10, p90)
    actual_xlim = float(seconds[-1]) if len(seconds) else np.nan
    requested_xlim = max_seconds

    fig, ax = plt.subplots(figsize=(10, 5))
    if len(seconds):
        if file_count <= 1:
            ax.plot(seconds, mean_acf, color='#2b6cb0', linewidth=1.0, label='ACF')
            ax.text(0.98, 0.98, 'single file only', transform=ax.transAxes, ha='right', va='top', fontsize=8)
        else:
            ax.fill_between(seconds, p10, p90, color='#90cdf4', alpha=0.25, label='p10-p90')
            ax.plot(seconds, mean_acf, color='#2b6cb0', linewidth=1.0, label='mean ACF')
            ax.plot(seconds, median_acf, color='#2f855a', linewidth=1.0, alpha=0.9, label='median ACF')
    threshold = plot_data.get('acf_peak_threshold')
    if threshold is not None and np.isfinite(threshold):
        ax.axhline(threshold, color='#718096', linestyle='--', linewidth=0.8, label='peak_threshold')
    _plot_psd_period_markers(ax, plot_data.get('psd_peak_periods_s') or [], max_seconds, max_psd_period_refs)
    ax.axhline(0.0, color='#2d3748', linewidth=0.8)
    ax.set_title(_title_with_xlim(title or 'Group ACF', requested_xlim, actual_xlim))
    ax.set_xlabel('Lag (s)')
    ax.set_ylabel('ACF')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=8)
    ax.text(
        0.02,
        0.98,
        f"zero_cross={_fmt_with_xlim(metrics.get('acf_zero_cross_s'), actual_xlim)}\n"
        f"first_strong={_fmt_with_xlim(metrics.get('acf_first_strong_peak_lag_s'), actual_xlim)}\n"
        f"global_max={_fmt_with_xlim(metrics.get('acf_global_max_peak_lag_s'), actual_xlim)}\n"
        f"spacing={_fmt_with_xlim(metrics.get('acf_peak_spacing_period_s'), actual_xlim)}\n"
        f"psd_T={_fmt_with_xlim(metrics.get('acf_psd_candidate_period_s'), actual_xlim)}",
        transform=ax.transAxes,
        va='top',
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
    if n <= MAX_ACF_PLOT_POINTS:
        return trimmed
    step = int(np.ceil(n / MAX_ACF_PLOT_POINTS))
    return [array[::step] for array in trimmed]


def _plot_psd_period_markers(ax, periods, max_seconds, max_refs):
    if max_seconds is not None and max_seconds > 0.0100001:
        return
    used_label = False
    for period in periods[:max(0, int(max_refs or 0))]:
        try:
            period = float(period)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(period) or period <= 0:
            continue
        limit = max_seconds if max_seconds is not None else ax.get_xlim()[1]
        multiple = 1
        while multiple * period <= limit:
            ax.axvline(
                multiple * period,
                color='#c53030',
                linestyle=':',
                linewidth=0.8,
                alpha=0.6,
                label='PSD peak periods' if not used_label else None,
            )
            used_label = True
            multiple += 1


def _fmt(value):
    try:
        if value is None or not np.isfinite(value):
            return 'nan'
        return f'{float(value):.6g}'
    except (TypeError, ValueError):
        return 'nan'


def _fmt_with_xlim(value, max_seconds):
    text = f'{_fmt(value)} s'
    try:
        if max_seconds is not None and np.isfinite(value) and float(value) > float(max_seconds):
            return f'{text} [outside xlim]'
    except (TypeError, ValueError):
        pass
    return text


def _title_with_xlim(title, requested, actual):
    if requested is None or not np.isfinite(actual):
        return title
    if actual + 1e-15 < float(requested):
        return f'{title} | requested={_fmt(requested)}s actual={_fmt(actual)}s'
    return title
