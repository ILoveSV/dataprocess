from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


MAX_PLOT_POINTS = 5000


def _as_array(values):
    return np.asarray(values if values is not None else [], dtype=float)


def _downsample_xy(x, y, max_points=MAX_PLOT_POINTS):
    x = _as_array(x)
    y = _as_array(y)
    if len(x) != len(y):
        n = min(len(x), len(y))
        x = x[:n]
        y = y[:n]
    if len(x) <= max_points:
        return x, y
    step = int(np.ceil(len(x) / max_points))
    return x[::step], y[::step]


def _fmt(value, precision=6):
    try:
        if value is None or not np.isfinite(value):
            return "nan"
        return f"{float(value):.{precision}g}"
    except (TypeError, ValueError):
        return "nan"


def plot_run_sequence(ax, plot_data, metrics, title=None):
    t, x = _downsample_xy(plot_data.get('time_or_index'), plot_data.get('x_for_plot'))
    scale = float(plot_data.get('y_scale') or 1.0)
    center = plot_data.get('center_value')
    if center is not None and np.isfinite(center):
        x = (x - float(center)) * scale
    else:
        x = x * scale
    ax.plot(t, x, color='#2b6cb0', linewidth=0.7, alpha=0.75)

    boundaries = _as_array(plot_data.get('file_boundaries'))
    for boundary in boundaries:
        if np.isfinite(boundary):
            ax.axvline(boundary, color='#718096', linestyle=':', linewidth=0.7, alpha=0.45)

    rolling = _as_array(plot_data.get('rolling_mean_for_plot'))
    rolling_t = _as_array(plot_data.get('rolling_time_for_plot'))
    if len(rolling) and len(rolling_t):
        rt, rm = _downsample_xy(rolling_t, rolling)
        if center is not None and np.isfinite(center):
            rm = (rm - float(center)) * scale
        else:
            rm = rm * scale
        ax.plot(rt, rm, color='#c53030', linewidth=1.2, label='rolling mean')
        ax.legend(loc='best', fontsize=8)

    ax.set_title(title or 'Run Sequence')
    xlabel = plot_data.get('x_axis_label') or 'Elapsed time across group (s)'
    ax.set_xlabel(xlabel)
    ax.set_ylabel(plot_data.get('y_axis_label') or 'Value')
    ax.grid(True, alpha=0.3)
    ax.text(
        0.02,
        0.98,
        f"drift_span={_fmt(metrics.get('run_drift_span'))}\n"
        f"drift_ratio_ac={_fmt(metrics.get('run_drift_ratio_ac'))}\n"
        f"roll_mean_range={_fmt(metrics.get('run_rolling_mean_range'))}",
        transform=ax.transAxes,
        va='top',
        fontsize=8,
        bbox={'facecolor': 'white', 'alpha': 0.75, 'edgecolor': 'none'},
    )


def plot_lag(ax, plot_data, metrics, title=None):
    lag_x, lag_y = _downsample_xy(plot_data.get('lag_x'), plot_data.get('lag_y'))
    ax.scatter(lag_x, lag_y, s=4, alpha=0.35, color='#2f855a', edgecolors='none')
    ax.set_title(title or 'Lag Plot')
    ax.set_xlabel('x[i]')
    ax.set_ylabel('x[i+1]')
    ax.grid(True, alpha=0.3)
    ax.text(
        0.02,
        0.98,
        f"lag_1_corr={_fmt(metrics.get('lag_1_corr'))}",
        transform=ax.transAxes,
        va='top',
        fontsize=8,
        bbox={'facecolor': 'white', 'alpha': 0.75, 'edgecolor': 'none'},
    )


def plot_histogram(ax, plot_data, metrics, title=None):
    counts = _as_array(plot_data.get('hist_counts'))
    bins = _as_array(plot_data.get('hist_bins'))
    if len(counts) and len(bins) == len(counts) + 1:
        widths = np.diff(bins)
        total = np.sum(counts)
        heights = counts / total * 100.0 if total > 0 else counts
        ax.bar(bins[:-1], heights, width=widths, align='edge', color='#805ad5', alpha=0.7)

    for key, color, label in [
        ('mean', '#c53030', 'mean'),
        ('median', '#2f855a', 'median'),
        ('q05', '#718096', 'q05'),
        ('q95', '#718096', 'q95'),
    ]:
        value = plot_data.get(key)
        if value is not None and np.isfinite(value):
            ax.axvline(value, color=color, linestyle='--', linewidth=1, label=label)

    ax.set_title(title or 'Histogram')
    ax.set_xlabel('Value')
    ax.set_ylabel('Percentage (%)')
    ax.grid(True, alpha=0.25)
    ax.legend(loc='best', fontsize=8)
    ax.text(
        0.02,
        0.98,
        f"mean={_fmt(plot_data.get('mean'))}\n"
        f"median={_fmt(plot_data.get('median'))}\n"
        f"q05={_fmt(plot_data.get('q05'))}\n"
        f"q95={_fmt(plot_data.get('q95'))}",
        transform=ax.transAxes,
        va='top',
        fontsize=8,
        bbox={'facecolor': 'white', 'alpha': 0.75, 'edgecolor': 'none'},
    )


def plot_normal_probability(ax, plot_data, metrics, title=None):
    q = _as_array(plot_data.get('qq_theoretical_quantiles'))
    ordered = _as_array(plot_data.get('qq_ordered_values'))
    fit = _as_array(plot_data.get('qq_fit_line'))
    q_plot, ordered_plot = _downsample_xy(q, ordered)
    ax.scatter(q_plot, ordered_plot, s=5, alpha=0.45, color='#dd6b20', edgecolors='none')
    if len(q) and len(fit) == len(q):
        q_fit, fit_plot = _downsample_xy(q, fit)
        ax.plot(q_fit, fit_plot, color='#2d3748', linewidth=1.1)

    ax.set_title(title or 'Normal Probability / QQ')
    ax.set_xlabel('Theoretical normal quantile')
    ax.set_ylabel('Ordered values')
    ax.grid(True, alpha=0.3)
    ax.text(
        0.02,
        0.98,
        f"qq_corr={_fmt(metrics.get('qq_normal_prob_corr'))}\n"
        f"tail_dev={_fmt(metrics.get('qq_tail_deviation'))}",
        transform=ax.transAxes,
        va='top',
        fontsize=8,
        bbox={'facecolor': 'white', 'alpha': 0.75, 'edgecolor': 'none'},
    )


def plot_nist_4plot(plot_data, metrics, output_path, title=None):
    """Create a NIST 4-plot PNG from precomputed plot data and metrics."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    plot_run_sequence(axes[0, 0], plot_data.get('run_sequence', {}), metrics)
    plot_lag(axes[0, 1], plot_data.get('lag', {}), metrics)
    plot_histogram(axes[1, 0], plot_data.get('histogram', {}), metrics)
    plot_normal_probability(axes[1, 1], plot_data.get('normal_probability', {}), metrics)

    if title:
        fig.suptitle(f"{title} | diagnostic only, not period inference", fontsize=14, fontweight='bold')
        fig.tight_layout(rect=[0, 0, 1, 0.96])
    else:
        fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches='tight')
    plt.close(fig)
    return output_path
