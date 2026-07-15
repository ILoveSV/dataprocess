import argparse
import json
import logging
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.core.config_loader import load_config
from src.features.nist_diagnostics import compute_group_nist_diagnostics
from src.features.nist_psd import DEFAULT_BANDS, compute_group_welch_psd
from src.io.time_csv_io import collect_csv_groups, read_csv_data
from src.plots.nist_4plot import plot_nist_4plot
from src.plots.nist_psd_plot import plot_group_psd_review_ranges
from src.pipelines.time_quality_pipeline import process_files as compute_time_metric_rows
from src.reports.excel_export import export_data_completeness_excel, export_group_summary_excel, export_to_excel
from src.summaries.time_group_summary import GROUP_SUMMARY_COLUMNS, summarize_data_completeness, summarize_group_metrics


logger = logging.getLogger("data_process")
EPS = 1e-30


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="first-test-pipeline: quick 4-plot, PSD, and median bandpower gain dB figures."
    )
    parser.add_argument("--input", "-i", default=None, help="Input process/time CSV root, group folder, or CSV file.")
    parser.add_argument("--output", "-o", default="analysis_out/first_test_pipeline")
    parser.add_argument("--max-files", type=int, default=3, help="Max CSV files per group for quick screening; use 0 for all.")
    parser.add_argument("--max-channels", type=int, default=0, help="Max channels per group; use 0 for all.")
    parser.add_argument("--welch-nperseg", type=int, default=None)
    parser.add_argument("--low-freq-nperseg", type=int, default=None)
    parser.add_argument("--psd-exclude-low-hz", type=float, default=None)
    parser.add_argument("--background-groups", default=None, help="Comma-separated background groups. Optional.")
    parser.add_argument("--active-groups", default=None, help="Comma-separated active groups. Optional.")
    parser.add_argument("--skip-4plot", action="store_true", help="Skip NIST 4-plot figures.")
    parser.add_argument("--skip-psd", action="store_true", help="Skip PSD figures and PSD-derived data.")
    parser.add_argument("--skip-bandpower-gain", action="store_true", help="Skip median bandpower gain dB tables/figures.")
    parser.add_argument("--skip-time-stats", action="store_true", help="Skip time-domain file/group statistics.")
    parser.add_argument("--export-time-stats-excel", action="store_true", help="Also export per-group time-stat Excel workbooks.")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    args = parser.parse_args(argv)

    config = load_config()
    input_root = Path(args.input or config["tdms_reader_time_output_dir"])
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    params = {
        "welch_nperseg": args.welch_nperseg,
        "low_freq_nperseg": args.low_freq_nperseg,
        "psd_exclude_low_hz": args.psd_exclude_low_hz,
    }
    max_files = None if args.max_files == 0 else args.max_files
    max_channels = None if args.max_channels == 0 else args.max_channels

    summaries = run_first_test(
        input_root=input_root,
        output_root=output_root,
        params=params,
        max_files=max_files,
        max_channels=max_channels,
        background_groups=_split_arg(args.background_groups),
        active_groups=_split_arg(args.active_groups),
        enable_4plot=not args.skip_4plot,
        enable_psd=not args.skip_psd,
        enable_bandpower_gain=not args.skip_bandpower_gain,
        enable_time_stats=not args.skip_time_stats,
        export_time_stats_excel=args.export_time_stats_excel,
        skip_existing=args.skip_existing,
    )

    manifest_path = output_root / "first_test_manifest.json"
    manifest_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("first-test-pipeline complete: %s", manifest_path)
    return summaries


def run_first_test(
    input_root,
    output_root,
    params=None,
    max_files=3,
    max_channels=None,
    background_groups=None,
    active_groups=None,
    enable_4plot=True,
    enable_psd=True,
    enable_bandpower_gain=True,
    enable_time_stats=True,
    export_time_stats_excel=False,
    skip_existing=True,
):
    params = params or {}
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_groups = collect_csv_groups(input_root)
    if not csv_groups:
        logger.warning("No CSV groups found: %s", input_root)
        return {"input_root": str(input_root), "groups": [], "bandpower_gain_rows": 0}

    group_results = {}
    figure_rows = []
    time_file_rows = []
    time_group_rows = []
    time_completeness_rows = []
    for group_dir, csv_files in csv_groups:
        group_name = _group_name(input_root, group_dir)
        selected_files = csv_files[:max_files] if max_files is not None else csv_files
        progress = f"{len(group_results) + 1}/{len(csv_groups)}"
        logger.info("First-test processing group=%s progress=%s files=%s", group_name, progress, len(selected_files))
        cached = load_group_manifest(
            output_root=output_root,
            group_name=group_name,
            selected_files=selected_files,
            params=params,
            max_channels=max_channels,
            enable_4plot=enable_4plot,
            enable_psd=enable_psd,
            enable_time_stats=enable_time_stats,
            export_time_stats_excel=export_time_stats_excel,
        ) if skip_existing else None
        if cached is not None:
            logger.info("RESUME first-test skip existing group=%s progress=%s", group_name, progress)
            group_results[group_name] = cached["group_result"]
            figure_rows.extend(cached.get("figures", []))
            time_file_rows.extend(cached.get("time_file_rows", []))
            time_group_rows.extend(cached.get("time_group_rows", []))
            time_completeness_rows.extend(cached.get("time_completeness_rows", []))
            continue

        group_results[group_name] = process_group(
            group_name=group_name,
            group_dir=Path(group_dir),
            csv_files=selected_files,
            output_root=Path(output_root),
            params=params,
            max_channels=max_channels,
            enable_4plot=enable_4plot,
            enable_psd=enable_psd,
        )
        figure_rows.extend(group_results[group_name]["figures"])
        if enable_time_stats:
            file_rows, summary_rows, completeness_rows = process_time_stats_group(
                group_name=group_name,
                group_dir=Path(group_dir),
                csv_files=selected_files,
                output_root=Path(output_root),
                max_channels=max_channels,
                export_excel=export_time_stats_excel,
            )
            time_file_rows.extend(file_rows)
            time_group_rows.extend(summary_rows)
            time_completeness_rows.extend(completeness_rows)
        write_group_manifest(
            output_root=output_root,
            group_name=group_name,
            selected_files=selected_files,
            params=params,
            max_channels=max_channels,
            enable_4plot=enable_4plot,
            enable_psd=enable_psd,
            enable_time_stats=enable_time_stats,
            export_time_stats_excel=export_time_stats_excel,
            group_result=group_results[group_name],
            figures=group_results[group_name]["figures"],
            time_file_rows=file_rows if enable_time_stats else [],
            time_group_rows=summary_rows if enable_time_stats else [],
            time_completeness_rows=completeness_rows if enable_time_stats else [],
        )

    bandpower = (
        build_bandpower_gain_table(
            group_results,
            background_groups=background_groups,
            active_groups=active_groups,
        )
        if enable_bandpower_gain and enable_psd
        else pd.DataFrame()
    )
    bandpower_path = Path(output_root) / "median_bandpower_gain_db.csv"
    bandpower.to_csv(bandpower_path, index=False, encoding="utf-8-sig")
    gain_figures = plot_bandpower_gain_figures(bandpower, Path(output_root) / "figures" / "median_bandpower_gain_db") if enable_bandpower_gain and enable_psd else []

    figure_index = pd.DataFrame(figure_rows + gain_figures)
    figure_index_path = Path(output_root) / "figure_index.csv"
    figure_index.to_csv(figure_index_path, index=False, encoding="utf-8-sig")
    time_file_path = Path(output_root) / "time_file_features.csv"
    time_group_path = Path(output_root) / "time_group_summary.csv"
    time_completeness_path = Path(output_root) / "time_data_completeness_summary.csv"
    if enable_time_stats:
        pd.DataFrame(time_file_rows).to_csv(time_file_path, index=False, encoding="utf-8-sig")
        pd.DataFrame(time_group_rows, columns=GROUP_SUMMARY_COLUMNS).to_csv(time_group_path, index=False, encoding="utf-8-sig")
        pd.DataFrame(time_completeness_rows).to_csv(time_completeness_path, index=False, encoding="utf-8-sig")

    return {
        "pipeline": "first-test-pipeline",
        "input_root": str(input_root),
        "output_root": str(output_root),
        "group_count": len(group_results),
        "groups": sorted(group_results),
        "max_files_per_group": max_files,
        "max_channels_per_group": max_channels,
        "enabled_steps": {
            "4plot": bool(enable_4plot),
            "psd": bool(enable_psd),
            "median_bandpower_gain_db": bool(enable_bandpower_gain and enable_psd),
            "time_stats": bool(enable_time_stats),
            "time_stats_excel": bool(export_time_stats_excel),
        },
        "resume": {"skip_existing": bool(skip_existing), "group_manifest_dir": str(output_root / ".first_test_group_manifests")},
        "bandpower_gain_rows": int(len(bandpower)),
        "bandpower_gain_csv": str(bandpower_path),
        "time_file_features_csv": str(time_file_path) if enable_time_stats else None,
        "time_group_summary_csv": str(time_group_path) if enable_time_stats else None,
        "time_data_completeness_csv": str(time_completeness_path) if enable_time_stats else None,
        "time_file_feature_rows": int(len(time_file_rows)),
        "time_group_summary_rows": int(len(time_group_rows)),
        "figure_index_csv": str(figure_index_path),
        "figure_count": int(len(figure_index)),
    }


def process_group(group_name, group_dir, csv_files, output_root, params, max_channels=None, enable_4plot=True, enable_psd=True):
    series_by_channel = {}
    time_by_channel = {}
    selected_channels = None

    for csv_file in csv_files:
        try:
            df, time_column, channel_columns = read_csv_data(csv_file)
        except Exception as exc:
            logger.warning("Skipping unreadable CSV %s: %s", csv_file, exc)
            continue

        if selected_channels is None:
            selected_channels = channel_columns[:max_channels] if max_channels is not None else channel_columns
        time_values = df[time_column].to_numpy()
        for channel in selected_channels:
            if channel not in df.columns:
                continue
            series_by_channel.setdefault(channel, []).append(df[channel].to_numpy())
            time_by_channel.setdefault(channel, []).append(time_values)

    figures = []
    channels = sorted(series_by_channel, key=_channel_sort_key)
    group_out = Path(output_root) / "figures"
    psd_store = {}
    for channel in channels:
        series_list = series_by_channel[channel]
        time_list = time_by_channel.get(channel)
        if not series_list:
            continue

        if enable_4plot:
            nist = compute_group_nist_diagnostics(series_list, time_list=time_list, params=params)
            four_plot_path = group_out / "4plot" / _safe_name(group_name) / f"{_safe_name(channel)}_4plot.png"
            plot_nist_4plot(
                nist["plot_data"],
                nist["metrics"],
                four_plot_path,
                title=f"First Test 4-Plot | group={group_name} | channel={channel} | files={len(series_list)}",
            )
            figures.append(_figure_row(group_name, channel, "4plot", four_plot_path))

        if enable_psd:
            psd = compute_group_welch_psd(series_list, time_list=time_list, params=params)
            psd_paths = plot_group_psd_review_ranges(
                psd["plot_data"],
                {"file_count": len(series_list), **psd["metrics"]},
                group_out / "psd" / _safe_name(group_name) / _safe_name(channel),
                title_prefix=f"First Test PSD | group={group_name} | channel={channel} | files={len(series_list)}",
                group=group_name,
                channel=channel,
            )
            figures.extend(_figure_row(group_name, channel, "psd", path) for path in psd_paths)

            psd_store[channel] = {
                "plot_data": psd["plot_data"],
                "metrics": psd["metrics"],
                "file_count": len(series_list),
            }

    return {
        "group_dir": str(group_dir),
        "file_count_used": len(csv_files),
        "channels": channels,
        "psd": psd_store,
        "figures": figures,
    }


def process_time_stats_group(group_name, group_dir, csv_files, output_root, max_channels=None, export_excel=False):
    if not csv_files:
        return [], [], []
    _, channel_columns = read_csv_data(csv_files[0])[1:]
    channel_columns = channel_columns[:max_channels] if max_channels is not None else channel_columns
    channel_rows = compute_time_metric_rows(csv_files, channel_columns)

    file_rows = []
    for channel, rows in channel_rows.items():
        for row in rows:
            file_rows.append({"group": group_name, "channel": channel, **row})

    summary = summarize_group_metrics(channel_rows, group_name)
    summary_rows = [{"channel": channel, **row, "group": group_name} for channel, row in summary.items()]

    completeness_rows = summarize_data_completeness(channel_rows, group_name)
    for row in completeness_rows:
        row["group"] = group_name

    if export_excel:
        excel_dir = Path(output_root) / "time_stats_excel" / _safe_name(group_name)
        export_to_excel(channel_rows, excel_dir / "time_series_metrics.xlsx")
        export_group_summary_excel(channel_rows, group_name, excel_dir / "time_series_group_summary.xlsx")
        export_data_completeness_excel(channel_rows, group_name, excel_dir / "data_completeness_summary.xlsx")

    return file_rows, summary_rows, completeness_rows


def group_manifest_path(output_root, group_name):
    return Path(output_root) / ".first_test_group_manifests" / f"{_safe_name(group_name)}.json"


def group_signature(selected_files, params, max_channels, enable_4plot, enable_psd, enable_time_stats, export_time_stats_excel):
    return {
        "input_files": [str(Path(path).resolve()) for path in selected_files],
        "input_mtime_ns": {str(Path(path).resolve()): Path(path).stat().st_mtime_ns for path in selected_files if Path(path).exists()},
        "params": params,
        "max_channels": max_channels,
        "enable_4plot": bool(enable_4plot),
        "enable_psd": bool(enable_psd),
        "enable_time_stats": bool(enable_time_stats),
        "export_time_stats_excel": bool(export_time_stats_excel),
    }


def load_group_manifest(
    output_root,
    group_name,
    selected_files,
    params,
    max_channels,
    enable_4plot,
    enable_psd,
    enable_time_stats,
    export_time_stats_excel,
):
    path = group_manifest_path(output_root, group_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expected = group_signature(selected_files, params, max_channels, enable_4plot, enable_psd, enable_time_stats, export_time_stats_excel)
    if data.get("signature") != expected:
        logger.info("RESUME first-test cache miss group=%s reason=signature changed", group_name)
        return None
    if not all(Path(row.get("path", "")).exists() for row in data.get("figures", [])):
        logger.info("RESUME first-test cache miss group=%s reason=missing figure", group_name)
        return None
    return data


def write_group_manifest(
    output_root,
    group_name,
    selected_files,
    params,
    max_channels,
    enable_4plot,
    enable_psd,
    enable_time_stats,
    export_time_stats_excel,
    group_result,
    figures,
    time_file_rows,
    time_group_rows,
    time_completeness_rows,
):
    path = group_manifest_path(output_root, group_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "group_name": group_name,
        "signature": group_signature(selected_files, params, max_channels, enable_4plot, enable_psd, enable_time_stats, export_time_stats_excel),
        "group_result": _manifest_group_result(group_result),
        "figures": figures,
        "time_file_rows": time_file_rows,
        "time_group_rows": time_group_rows,
        "time_completeness_rows": time_completeness_rows,
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)
    logger.info(
        "RESUME first-test wrote group manifest group=%s figures=%s time_file_rows=%s path=%s",
        group_name,
        len(figures),
        len(time_file_rows),
        path,
    )


def _manifest_group_result(group_result):
    compact_psd = {}
    for channel, record in group_result.get("psd", {}).items():
        plot_data = record.get("plot_data", {})
        compact_psd[channel] = {
            "plot_data": {
                "frequency": _json_array(plot_data.get("frequency")),
                "median_power": _json_array(plot_data.get("median_power")),
            },
            "metrics": {},
            "file_count": record.get("file_count"),
        }
    return {
        "group_dir": group_result.get("group_dir"),
        "file_count_used": group_result.get("file_count_used"),
        "channels": group_result.get("channels", []),
        "psd": compact_psd,
        "figures": group_result.get("figures", []),
    }


def _json_array(values):
    if values is None:
        return []
    array = np.asarray(values, dtype=float)
    return [float(value) if np.isfinite(value) else None for value in array]


def build_bandpower_gain_table(group_results, background_groups=None, active_groups=None):
    pairs = _resolve_pairs(group_results, background_groups, active_groups)
    rows = []
    for active_group, background_group in pairs:
        active = group_results.get(active_group, {}).get("psd", {})
        background = group_results.get(background_group, {}).get("psd", {})
        for channel in sorted(set(active) & set(background), key=_channel_sort_key):
            active_plot = active[channel]["plot_data"]
            background_plot = background[channel]["plot_data"]
            freqs = np.asarray(active_plot.get("frequency", []), dtype=float)
            bg_freqs = np.asarray(background_plot.get("frequency", []), dtype=float)
            active_power = np.asarray(active_plot.get("median_power", []), dtype=float)
            bg_power = np.asarray(background_plot.get("median_power", []), dtype=float)
            if len(freqs) == 0 or len(freqs) != len(bg_freqs) or not np.allclose(freqs, bg_freqs):
                continue
            for band_name, low, high in DEFAULT_BANDS:
                active_bp, bin_count, df_hz = _bandpower(freqs, active_power, low, high)
                bg_bp, bg_bin_count, bg_df_hz = _bandpower(bg_freqs, bg_power, low, high)
                if not np.isfinite(active_bp) or not np.isfinite(bg_bp):
                    continue
                rows.append({
                    "active_group": active_group,
                    "background_group": background_group,
                    "comparison": f"{active_group} minus {background_group}",
                    "channel": channel,
                    "band_name": band_name,
                    "band_low_hz": low,
                    "band_high_hz": high,
                    "active_median_bandpower": active_bp,
                    "background_median_bandpower": bg_bp,
                    "median_bandpower_gain_dB": 10.0 * math.log10((active_bp + EPS) / (bg_bp + EPS)),
                    "bin_count": int(min(bin_count, bg_bin_count)),
                    "df_hz": float(np.nanmedian([df_hz, bg_df_hz])),
                    "active_file_count": active[channel]["file_count"],
                    "background_file_count": background[channel]["file_count"],
                })
    return pd.DataFrame(rows)


def plot_bandpower_gain_figures(bandpower, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    if bandpower.empty:
        return rows

    for band_name in sorted(bandpower["band_name"].unique()):
        cur = bandpower[bandpower["band_name"] == band_name].copy()
        if cur.empty:
            continue
        pivot = cur.pivot_table(
            index="channel",
            columns="comparison",
            values="median_bandpower_gain_dB",
            aggfunc="median",
        )
        pivot = pivot.reindex(sorted(pivot.index, key=_channel_sort_key))
        path = output_dir / f"median_bandpower_gain_db_{_safe_name(band_name)}.png"
        _plot_gain_heatmap(pivot, band_name, path)
        rows.append({
            "group": "",
            "channel": "",
            "figure_type": "median_bandpower_gain_db",
            "path": str(path),
            "notes": f"band={band_name}",
        })
    return rows


def _plot_gain_heatmap(pivot, band_name, path):
    data = pivot.to_numpy(dtype=float)
    finite = data[np.isfinite(data)]
    vmax = max(3.0, float(np.nanmax(np.abs(finite))) if finite.size else 3.0)

    fig_width = max(8, min(18, 1.4 * max(1, len(pivot.columns)) + 3))
    fig_height = max(5, min(14, 0.36 * max(1, len(pivot.index)) + 2))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(data, cmap="coolwarm", aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_title(f"Median Bandpower Gain dB | {band_name}")
    ax.set_xlabel("Active minus background")
    ax.set_ylabel("Channel")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for row_idx in range(data.shape[0]):
        for col_idx in range(data.shape[1]):
            value = data[row_idx, col_idx]
            if np.isfinite(value):
                ax.text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, label="gain dB")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _resolve_pairs(group_results, background_groups=None, active_groups=None):
    groups = sorted(group_results)
    if background_groups:
        active_candidates = active_groups or [g for g in groups if g not in background_groups]
        return [(active, bg) for bg in background_groups for active in active_candidates if active in group_results and bg in group_results and active != bg]

    parsed = []
    for group in groups:
        info = _parse_distance_pump_group(group)
        if info:
            parsed.append({"group": group, **info})
    backgrounds = {row["distance_m"]: row["group"] for row in parsed if row["pump_freq_hz"] == 0}
    pairs = []
    for row in parsed:
        if row["pump_freq_hz"] == 0:
            continue
        background = backgrounds.get(row["distance_m"])
        if background:
            pairs.append((row["group"], background))
    if pairs:
        return pairs
    return _resolve_no_background_pairs(groups)


def _resolve_no_background_pairs(groups):
    pairs = []
    group_set = set(groups)
    for background in groups:
        parts = Path(background).as_posix().split("/")
        for idx, part in enumerate(parts):
            if part.lower() != "no":
                continue
            for active in groups:
                if active == background or active not in group_set:
                    continue
                active_parts = Path(active).as_posix().split("/")
                if len(active_parts) != len(parts):
                    continue
                if active_parts[:idx] == parts[:idx] and active_parts[idx + 1:] == parts[idx + 1:] and active_parts[idx].lower() != "no":
                    pairs.append((active, background))
    return sorted(set(pairs))


def _parse_distance_pump_group(group):
    match = re.search(r"(?P<distance>\d+(?:\.\d+)?)m(?P<pump>\d+(?:\.\d+)?)hz", str(group).lower())
    if not match:
        return None
    return {
        "distance_m": float(match.group("distance")),
        "pump_freq_hz": float(match.group("pump")),
    }


def _bandpower(freqs, power, low, high):
    mask = (freqs >= low) & (freqs < high) & np.isfinite(power)
    if not np.any(mask):
        return np.nan, 0, np.nan
    sub_freqs = freqs[mask]
    sub_power = power[mask]
    df_hz = float(np.median(np.diff(freqs))) if len(freqs) >= 2 else np.nan
    if len(sub_freqs) >= 2:
        value = float(np.trapezoid(sub_power, sub_freqs))
    elif np.isfinite(df_hz):
        value = float(sub_power[0] * df_hz)
    else:
        value = np.nan
    return value, int(len(sub_power)), df_hz


def _figure_row(group, channel, figure_type, path):
    return {
        "group": group,
        "channel": channel,
        "figure_type": figure_type,
        "path": str(path),
        "notes": "",
    }


def _split_arg(value):
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _group_name(input_root, group_dir):
    input_root = Path(input_root)
    group_dir = Path(group_dir)
    if input_root.is_file():
        return input_root.stem
    try:
        relative = group_dir.resolve().relative_to(input_root.resolve())
        return relative.as_posix()
    except (ValueError, OSError):
        return group_dir.name


def _safe_name(value):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value))


def _channel_sort_key(value):
    match = re.search(r"(\d+)$", str(value))
    return (str(value)[: match.start()] if match else str(value), int(match.group(1)) if match else 0)


if __name__ == "__main__":
    main()
