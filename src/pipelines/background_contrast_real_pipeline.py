import argparse
import json
import logging
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pandas as pd

from src.core.config_loader import load_config
from src.features.background_contrast import (
    REAL_CHANNELS,
    compute_acf_contrast,
    compute_bandpower_contrast,
    compute_peak_contrast,
    compute_psd_gain_curves,
    make_background_pairs,
)
from src.features.band_labels import (
    add_band_display_columns,
    build_band_mapping_debug,
    canonicalize_band_label,
    canonicalize_feature_column,
    display_label_for_band,
)
from src.features.nist_psd import compute_group_welch_psd
from src.io.time_csv_io import read_csv_header
from src.summaries.background_contrast_summary import (
    DEFAULT_BANDS,
    compute_cross_channel_support,
    compute_distance_decay_after_background,
    compute_pumpfreq_net_contrast,
    detect_qc_outlier_channels,
)
from src.utils.cache_utils import build_cache_metadata, is_cache_hit, write_cache_metadata
from src.utils.perf_timing import timed_step


logger = logging.getLogger('data_process')

GROUPS = ["2m0hz", "2m30hz", "2m50hz", "3m0hz", "3m30hz", "3m50hz", "5m0hz", "5m30hz", "5m50hz"]
PLOT_MODES = ("none", "full")
OUTPUT_FILES = [
    "background_psd_diff_curves.csv",
    "background_bandpower_contrast.xlsx",
    "background_peak_contrast.xlsx",
    "background_acf_contrast.xlsx",
    "cross_channel_background_contrast.xlsx",
    "pumpfreq_net_contrast.xlsx",
    "distance_decay_after_background.xlsx",
    "qc_outlier_channels.xlsx",
    "band_mapping_debug.csv",
    "active_channels.json",
    "outlier_channel_overview.csv",
    "contrast_summary_report.md",
    "contrast_run_log.txt",
]
FIGURE_FILES = [
    "figures/bandpower_gain_heatmap.png",
    "figures/cross_channel_support_heatmap.png",
    "figures/pumpfreq_net_contrast_heatmap.png",
    "figures/distance_decay_after_background.png",
    "figures/outlier_channel_overview.png",
]
SMOKE_COVERAGE_ITEMS = [
    "59.5kHz gain > 8dB",
    "50k-100k band gain ~= 10dB",
    "lowfreq df=24.414 unreliable",
    "lowfreq df=0.5 reliable",
    "new/enhanced/suppressed/shared peak classification",
    "ACF change flag",
    "8/12 strong, 6/12 medium, 3/12 weak, 1/12 none",
    "pumpfreq net contrast = 50 net - 30 net",
    "distance decay monotonic",
    "ALL channel excluded from formal support count",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Background Contrast v1 on real 26.5.12 group outputs")
    parser.add_argument("--time-root", default=None)
    parser.add_argument("--nist-root", default=None)
    parser.add_argument("--fft-root", default=None)
    parser.add_argument("--output", "-o", default=None)
    parser.add_argument("--stage", choices=["all", "tables", "figures"], default="all")
    parser.add_argument("--plots", choices=PLOT_MODES, default="full")
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--groups", nargs="+", default=None, help="Optional group subset, e.g. 2m0hz 2m30hz 2m50hz")
    parser.add_argument("--channel-batch-size", type=int, default=3)
    parser.add_argument("--expected-channel-count", type=int, default=None)
    parser.add_argument("--skip-fft-audit", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    args = parser.parse_args(argv)

    with timed_step("background_contrast.module_total"):
        config = load_config()
        time_root = Path(args.time_root or config["tdms_reader_time_output_dir"])
        fft_root = Path(args.fft_root or config["tdms_reader_frequency_output_dir"])
        results_root = Path(config["time_series_results_dir"]).parent
        nist_root = Path(args.nist_root or (results_root / "nist_diagnostics"))
        output_dir = Path(args.output or (results_root / "background_contrast_v1"))
        groups = args.groups or GROUPS
        validate_groups(groups)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not args.skip_fft_audit:
            run_fft_group_input_audit(fft_root, output_dir, groups)

        if args.stage in {"all", "tables"}:
            run_tables_stage(
                time_root,
                nist_root,
                output_dir,
                groups,
                channel_batch_size=args.channel_batch_size,
                expected_channel_count=args.expected_channel_count,
                plots=args.plots,
                force=args.force,
                skip_existing=args.skip_existing,
            )

        if args.stage in {"all", "figures"} and args.plots != "none":
            run_figures_stage(
                output_dir,
                dpi=args.dpi,
                force=args.force,
                skip_existing=args.skip_existing,
            )

        print(f"Background Contrast v1 real output: {output_dir}")
        return output_dir


def run_tables_stage(time_root, nist_root, output_dir, groups=None, channel_batch_size=3, expected_channel_count=None, plots="full", force=False, skip_existing=True):
    groups = groups or GROUPS
    table_inputs = collect_table_input_files(time_root, nist_root, groups)
    expected_outputs = [output_dir / name for name in OUTPUT_FILES]
    params = {
        "stage": "background_contrast_tables",
        "groups": groups,
        "channel_batch_size": channel_batch_size,
        "expected_channel_count": expected_channel_count,
        "bands": DEFAULT_BANDS,
        "output_schema": OUTPUT_FILES,
    }
    metadata_path = output_dir / ".cache" / "background_contrast_tables_cache.json"
    hit, _ = is_cache_hit(
        "background_contrast_tables",
        table_inputs,
        expected_outputs,
        params,
        metadata_path,
        force=force,
        skip_existing=skip_existing,
    )
    if hit:
        logger.info("Background contrast tables are up-to-date")
        return load_contrast_tables(output_dir)

    smoke_coverage = check_smoke_coverage()
    with timed_step("background_contrast.collect_run_info"):
        run_info = collect_run_info(time_root, nist_root, groups)
    with timed_step("background_contrast.psd_curve"):
        psd_curve_df = build_real_psd_curve_df(time_root, groups, channel_batch_size=channel_batch_size)
    with timed_step("background_contrast.psd_peaks"):
        psd_peaks_df = build_real_psd_peaks_df(nist_root, groups)
    with timed_step("background_contrast.acf_summary"):
        acf_summary_df = build_real_acf_summary_df(nist_root, groups)

    pairs = make_background_pairs(groups)
    with timed_step("background_contrast.compute_tables"):
        psd_gain = compute_psd_gain_curves(psd_curve_df, pairs)
        bandpower = compute_bandpower_contrast(psd_curve_df, pairs, DEFAULT_BANDS)
        active_peaks = psd_peaks_df[psd_peaks_df["pump_freq_hz"] != 0].copy()
        background_peaks = psd_peaks_df[psd_peaks_df["pump_freq_hz"] == 0].copy()
        peak = compute_peak_contrast(active_peaks, background_peaks, pairs)
        acf = compute_acf_contrast(acf_summary_df, pairs)
        contrast_tables = {"bandpower": bandpower, "peak": peak, "acf": acf}
        cross_channel = compute_cross_channel_support(contrast_tables)
        pumpfreq_net = compute_pumpfreq_net_contrast(contrast_tables)
        distance_decay = compute_distance_decay_after_background(contrast_tables)
        qc_outliers = detect_qc_outlier_channels(bandpower)

    psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers = normalize_contrast_table_labels(
        psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers
    )
    active_channels = detect_active_channels(bandpower, peak, acf)
    write_active_channels(output_dir, active_channels, expected_channel_count)
    write_band_mapping_debug(output_dir, bandpower, peak, cross_channel, pumpfreq_net, distance_decay, qc_outliers)
    write_outlier_overview_csv(output_dir, qc_outliers, bandpower, active_channels)

    with timed_step("background_contrast.write_tables"):
        write_outputs(output_dir, psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers)

    validation = validate_outputs(
        output_dir,
        pairs,
        bandpower,
        peak,
        acf,
        cross_channel,
        pumpfreq_net,
        distance_decay,
        run_info,
        require_figures=False,
        require_distance_decay=_has_distance_triplet(groups),
    )
    report = build_report(run_info, smoke_coverage, pairs, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers, validation, output_dir)
    run_log = build_run_log(run_info, smoke_coverage, validation, pairs, bandpower, acf, peak)
    (output_dir / "contrast_summary_report.md").write_text(report, encoding="utf-8")
    (output_dir / "contrast_run_log.txt").write_text(run_log, encoding="utf-8")
    write_cache_metadata(
        metadata_path,
        build_cache_metadata(
            "background_contrast_tables",
            table_inputs,
            expected_outputs,
            params,
            input_dir=f"time={time_root};nist={nist_root}",
            output_dir=output_dir,
        ),
    )
    print(f"validation_status={validation['status']}")
    return {
        "bandpower": bandpower,
        "cross_channel": cross_channel,
        "pumpfreq_net": pumpfreq_net,
        "distance_decay": distance_decay,
            "qc_outliers": qc_outliers,
            "active_channels": active_channels,
        }


def run_figures_stage(output_dir, dpi=160, force=False, skip_existing=True):
    output_dir = Path(output_dir)
    figure_inputs = expected_figure_input_tables(output_dir)
    expected_figures = expected_figure_outputs(output_dir)
    params = {
        "stage": "background_contrast_figures",
        "dpi": dpi,
        "figure_schema": FIGURE_FILES,
    }
    metadata_path = output_dir / ".cache" / "background_contrast_figures_cache.json"
    hit, _ = is_cache_hit(
        "background_contrast_figures",
        figure_inputs,
        expected_figures,
        params,
        metadata_path,
        force=force,
        skip_existing=skip_existing,
    )
    if hit:
        logger.info("Background contrast figures are up-to-date")
        return expected_figures

    with timed_step("background_contrast.figures"):
        write_figures_from_outputs(output_dir, dpi=dpi)
    write_cache_metadata(
        metadata_path,
        build_cache_metadata(
            "background_contrast_figures",
            figure_inputs,
            expected_figures,
            params,
            input_dir=output_dir,
            output_dir=output_dir / "figures",
        ),
    )
    return expected_figures


def run_fft_group_input_audit(fft_root, output_dir, groups):
    rows = []
    reference_by_group = {}
    for group in groups:
        group_dir = Path(fft_root) / group
        for csv_file in sorted(group_dir.glob("*.csv")):
            try:
                row = audit_fft_csv(csv_file, group)
            except Exception as exc:
                row = {
                    "group": group,
                    "file": csv_file.name,
                    "path": str(csv_file),
                    "status": "ERROR",
                    "warning": str(exc),
                }
            ref = reference_by_group.setdefault(group, row)
            warnings = audit_fft_row_warnings(row, ref)
            row["warning"] = "; ".join(filter(None, [row.get("warning", ""), *warnings]))
            row["status"] = "WARNING" if row["warning"] else row.get("status", "OK")
            if row["warning"]:
                logger.warning("FFT audit %s/%s: %s", group, csv_file.name, row["warning"])
            rows.append(row)

    audit_df = pd.DataFrame(rows)
    output_dir = Path(output_dir)
    audit_csv = output_dir / "fft_group_input_audit.csv"
    audit_json = output_dir / "fft_group_input_audit.json"
    audit_df.to_csv(audit_csv, index=False, encoding="utf-8-sig")
    payload = {
        "groups": list(groups),
        "file_count": int(len(audit_df)),
        "warning_count": int((audit_df.get("status") == "WARNING").sum()) if not audit_df.empty else 0,
        "nan_inf_check_scope": "frequency_column",
        "records": audit_df.to_dict("records"),
    }
    audit_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return audit_df


def audit_fft_csv(csv_file, group):
    header = pd.read_csv(csv_file, nrows=0)
    columns = list(header.columns)
    channel_columns = [col for col in columns if col != "frequency"]
    if "frequency" not in columns:
        return {
            "group": group,
            "file": csv_file.name,
            "path": str(csv_file),
            "status": "ERROR",
            "warning": "missing frequency column",
            "row_count": np.nan,
            "df_hz": np.nan,
            "max_frequency_hz": np.nan,
            "channel_columns": json.dumps(channel_columns, ensure_ascii=False),
            "nan_or_inf_count": np.nan,
        }
    freq = pd.read_csv(csv_file, usecols=["frequency"])["frequency"].astype(float)
    values = freq.to_numpy()
    finite = np.isfinite(values)
    diffs = np.diff(values[finite])
    df_hz = float(np.median(diffs)) if diffs.size else np.nan
    return {
        "group": group,
        "file": csv_file.name,
        "path": str(csv_file),
        "status": "OK",
        "warning": "",
        "row_count": int(len(freq)),
        "df_hz": df_hz,
        "max_frequency_hz": float(np.nanmax(values)) if len(values) else np.nan,
        "frequency_start_hz": float(values[0]) if len(values) else np.nan,
        "frequency_end_hz": float(values[-1]) if len(values) else np.nan,
        "frequency_hash": pd.util.hash_pandas_object(freq, index=False).sum(),
        "channel_columns": json.dumps(channel_columns, ensure_ascii=False),
        "channel_column_count": len(channel_columns),
        "nan_or_inf_count": int((~finite).sum()),
    }


def audit_fft_row_warnings(row, ref):
    warnings = []
    if row.get("status") == "ERROR" or ref.get("status") == "ERROR":
        return warnings
    for key in ("row_count", "df_hz", "max_frequency_hz", "frequency_hash", "channel_columns", "nan_or_inf_count"):
        current = row.get(key)
        expected = ref.get(key)
        if key in {"df_hz", "max_frequency_hz"}:
            if not _float_close(current, expected):
                warnings.append(f"{key} differs: {current} vs {expected}")
        elif key == "nan_or_inf_count":
            if current != 0:
                warnings.append(f"NaN/Inf in frequency column: {current}")
        elif current != expected:
            warnings.append(f"{key} differs: {current} vs {expected}")
    return warnings


def _float_close(a, b):
    if pd.isna(a) and pd.isna(b):
        return True
    try:
        return bool(np.isclose(float(a), float(b), rtol=1e-9, atol=1e-12))
    except Exception:
        return False


def expected_figure_outputs(output_dir):
    output_dir = Path(output_dir)
    outputs = [
        output_dir / "figures/bandpower_gain_heatmap.png",
        output_dir / "figures/cross_channel_support_heatmap.png",
        output_dir / "figures/pumpfreq_net_contrast_heatmap.png",
        output_dir / "figures/outlier_channel_overview.png",
        output_dir / "plot_status.json",
    ]
    try:
        pumpfreq_net = _read_excel_table(output_dir / "pumpfreq_net_contrast.xlsx")
        distance_decay = _read_excel_table(output_dir / "distance_decay_after_background.xlsx")
        if available_distance_count_from_outputs(output_dir, pumpfreq_net, distance_decay) >= 2:
            outputs.append(output_dir / "figures/distance_decay_after_background.png")
    except FileNotFoundError:
        outputs.append(output_dir / "figures/distance_decay_after_background.png")
    return outputs


def validate_groups(groups):
    bad = [group for group in groups if not re.fullmatch(r"\d+(?:\.\d+)?m\d+(?:\.\d+)?hz", group)]
    if bad:
        raise ValueError(f"Invalid group names: {bad}")
    pairs = make_background_pairs(groups)
    active = pairs[pairs["pump_freq_hz"] != 0]
    if active.empty:
        raise ValueError("At least one non-background group is required")
    if active["missing_background"].any():
        missing = active[active["missing_background"]]["background_group"].tolist()
        raise ValueError(f"Missing background group(s) in --groups: {missing}")


def _has_distance_triplet(groups):
    distances = {parse_group(group)[0] for group in groups}
    return {2.0, 3.0, 5.0}.issubset(distances)


def check_smoke_coverage():
    test_path = Path("tests/test_background_contrast_smoke.py")
    report_path = Path("analysis_out/contrast_v1_smoke/smoke_report.md")
    test_text = test_path.read_text(encoding="utf-8", errors="ignore") if test_path.exists() else ""
    report_text = report_path.read_text(encoding="utf-8", errors="ignore") if report_path.exists() else ""
    checks = {
        SMOKE_COVERAGE_ITEMS[0]: "59.5kHz" in test_text and "gain" in test_text,
        SMOKE_COVERAGE_ITEMS[1]: "50kHz-100kHz" in test_text and "10.0" in test_text,
        SMOKE_COVERAGE_ITEMS[2]: "24.414" in test_text and "low_frequency_resolution_unreliable" in test_text,
        SMOKE_COVERAGE_ITEMS[3]: "0.5" in test_text and "lowfreq_reliable_flag" in test_text,
        SMOKE_COVERAGE_ITEMS[4]: all(token in test_text for token in ["new_peak", "enhanced_peak", "suppressed_peak", "shared_peak"]),
        SMOKE_COVERAGE_ITEMS[5]: "acf_change_flag" in test_text,
        SMOKE_COVERAGE_ITEMS[6]: all(token in test_text for token in ["strong", "medium", "weak", "none"]),
        SMOKE_COVERAGE_ITEMS[7]: "delta_50_minus_30" in test_text,
        SMOKE_COVERAGE_ITEMS[8]: "monotonic_decay_flag" in test_text,
        SMOKE_COVERAGE_ITEMS[9]: "ALL" in test_text and "support_channel_count" in test_text,
    }
    status = "PASS" if all(checks.values()) and "PASS" in report_text else "PARTIAL" if any(checks.values()) else "FAIL"
    return {"status": status, "items": checks}


def collect_run_info(time_root, nist_root, groups=None):
    selected_groups = groups or GROUPS
    group_info = {}
    channel_all_present = False
    for group in selected_groups:
        group_dir = time_root / group
        files = sorted(group_dir.glob("*.csv"))
        channel_counts = {}
        channels = []
        if files:
            _, channels = read_csv_header(files[0])
            channel_all_present = channel_all_present or ("ALL" in channels)
            for channel in channels:
                if channel in REAL_CHANNELS:
                    channel_counts[channel] = len(files)
        group_info[group] = {
            "time_csv_count": len(files),
            "channels": [ch for ch in channels if ch in REAL_CHANNELS],
            "channel_count": len([ch for ch in channels if ch in REAL_CHANNELS]),
            "channel_file_counts": channel_counts,
            "nist_dir_exists": (nist_root / group).exists(),
        }
    return {"groups": group_info, "channel_all_present": channel_all_present, "channel_all_excluded": True}


def collect_table_input_files(time_root, nist_root, groups=None):
    groups = groups or GROUPS
    files = []
    for group in groups:
        files.extend(sorted((Path(time_root) / group).glob("*.csv")))
        group_nist = Path(nist_root) / group
        files.extend([
            group_nist / "psd_peaks_long.xlsx",
            group_nist / "psd_group_summary.xlsx",
            group_nist / "acf_group_summary.xlsx",
        ])
    return files


def expected_figure_input_tables(output_dir):
    output_dir = Path(output_dir)
    return [
        output_dir / "background_bandpower_contrast.xlsx",
        output_dir / "cross_channel_background_contrast.xlsx",
        output_dir / "pumpfreq_net_contrast.xlsx",
        output_dir / "distance_decay_after_background.xlsx",
        output_dir / "qc_outlier_channels.xlsx",
        output_dir / "active_channels.json",
    ]


def load_contrast_tables(output_dir):
    output_dir = Path(output_dir)
    return {
        "bandpower": _read_excel_table(output_dir / "background_bandpower_contrast.xlsx"),
        "peak": _read_excel_table(output_dir / "background_peak_contrast.xlsx"),
        "acf": _read_excel_table(output_dir / "background_acf_contrast.xlsx"),
        "cross_channel": _read_excel_table(output_dir / "cross_channel_background_contrast.xlsx"),
        "pumpfreq_net": _read_excel_table(output_dir / "pumpfreq_net_contrast.xlsx"),
        "distance_decay": _read_excel_table(output_dir / "distance_decay_after_background.xlsx"),
        "qc_outliers": _read_excel_table(output_dir / "qc_outlier_channels.xlsx"),
    }


def _read_excel_table(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Required background contrast output table not found: {path}")
    return pd.read_excel(path)


def normalize_contrast_table_labels(psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers):
    psd_gain = psd_gain.copy()
    bandpower = add_band_display_columns(bandpower, "band_name")
    peak = add_band_display_columns(peak, "band_name")
    acf = acf.copy()
    cross_channel = canonicalize_feature_column(cross_channel, "feature_name")
    cross_channel = add_feature_plot_label(cross_channel)
    pumpfreq_net = canonicalize_feature_column(pumpfreq_net, "feature_name")
    pumpfreq_net = add_feature_plot_label(pumpfreq_net)
    distance_decay = canonicalize_feature_column(distance_decay, "feature_name")
    distance_decay = add_feature_plot_label(distance_decay)
    qc_outliers = canonicalize_feature_column(qc_outliers, "feature_name")
    qc_outliers = add_feature_plot_label(qc_outliers)
    return psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers


def add_feature_plot_label(df):
    if df is None or df.empty or "feature_type" not in df.columns or "display_label" not in df.columns:
        return df
    out = df.copy()
    out["plot_label"] = out["feature_type"].astype(str) + ": " + out["display_label"].astype(str)
    return out


def write_band_mapping_debug(output_dir, *tables):
    debug = build_band_mapping_debug(*tables)
    debug.to_csv(Path(output_dir) / "band_mapping_debug.csv", index=False, encoding="utf-8-sig")
    return debug


def detect_active_channels(*tables):
    channels = set()
    for table in tables:
        if table is None or table.empty or "channel" not in table.columns:
            continue
        channels.update(
            channel for channel in table["channel"].dropna().astype(str)
            if re.fullmatch(r"channel\d+", channel)
        )
    return sorted(channels, key=channel_sort_key)


def write_active_channels(output_dir, active_channels, expected_channel_count=None):
    effective_expected = expected_channel_count if expected_channel_count is not None else len(REAL_CHANNELS)
    payload = {
        "active_channel_count": len(active_channels),
        "expected_channel_count": effective_expected,
        "expected_channel_count_source": "cli" if expected_channel_count is not None else "REAL_CHANNELS",
        "channels": active_channels,
    }
    if effective_expected != len(active_channels):
        payload["warning"] = "expected_channel_count differs from active_channel_count"
        logger.warning(
            "expected_channel_count=%s differs from active_channel_count=%s",
            effective_expected,
            len(active_channels),
        )
        print(f"WARNING: expected_channel_count={effective_expected} differs from active_channel_count={len(active_channels)}")
    path = Path(output_dir) / "active_channels.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_outlier_overview_csv(output_dir, qc_outliers, checked_table, active_channels):
    channels = active_channels or REAL_CHANNELS
    checked_counts = (
        checked_table[checked_table["channel"].isin(channels)].groupby("channel").size().to_dict()
        if checked_table is not None and not checked_table.empty and "channel" in checked_table.columns
        else {}
    )
    outlier_counts = (
        qc_outliers[qc_outliers["channel"].isin(channels)].groupby("channel").size().to_dict()
        if qc_outliers is not None and not qc_outliers.empty and "channel" in qc_outliers.columns
        else {}
    )
    rows = []
    for channel in sorted(channels, key=channel_sort_key):
        total = int(checked_counts.get(channel, 0))
        count = int(outlier_counts.get(channel, 0))
        rows.append({
            "channel": channel,
            "outlier_count": count,
            "total_checked_rows": total,
            "outlier_ratio": float(count / total) if total else np.nan,
        })
    path = Path(output_dir) / "outlier_channel_overview.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_real_psd_curve_df(time_root, groups=None, channel_batch_size=3):
    groups = groups or GROUPS
    rows = []
    channel_batch_size = max(1, int(channel_batch_size or 1))
    for group in groups:
        group_dir = time_root / group
        csv_files = sorted(group_dir.glob("*.csv"))
        distance, pump = parse_group(group)
        for channel_batch in _batches(REAL_CHANNELS, channel_batch_size):
            series_by_channel = {channel: [] for channel in channel_batch}
            time_by_channel = {channel: [] for channel in channel_batch}
            for csv_file in csv_files:
                columns = ["time", *channel_batch]
                with timed_step("background_contrast.csv_read", group=group, file=csv_file.name, channels=len(channel_batch)):
                    df = pd.read_csv(csv_file, usecols=columns)
                time_values = df["time"].values
                for channel in channel_batch:
                    if channel in df.columns:
                        series_by_channel[channel].append(df[channel].values)
                        time_by_channel[channel].append(time_values)
            for channel in channel_batch:
                result = compute_group_welch_psd(series_by_channel[channel], time_list=time_by_channel[channel], params={})
                freqs = np.asarray(result["plot_data"]["frequency"], dtype=float)
                median_power = np.asarray(result["plot_data"]["median_power"], dtype=float)
                df_hz = result["metrics"].get("psd_df_hz", np.nan)
                rows.extend({
                    "group": group,
                    "distance_m": distance,
                    "pump_freq_hz": pump,
                    "channel": channel,
                    "file_id": "group_median",
                    "freq_hz": float(freq),
                    "psd": float(psd),
                    "df_hz": float(df_hz),
                    "is_smoke_test": False,
                } for freq, psd in zip(freqs, median_power))
    return pd.DataFrame(rows)


def _batches(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def build_real_psd_peaks_df(nist_root, groups=None):
    groups = groups or GROUPS
    frames = []
    for group in groups:
        path = nist_root / group / "psd_peaks_long.xlsx"
        df = pd.read_excel(path)
        distance, pump = parse_group(group)
        out = pd.DataFrame({
            "group": df["group"],
            "distance_m": distance,
            "pump_freq_hz": pump,
            "channel": df["channel"],
            "file_id": df.get("file_id_or_file_name", "group_median"),
            "peak_rank": df["peak_rank"],
            "peak_freq_hz": df["peak_freq_hz"],
            "peak_psd": df["peak_psd"],
            "peak_snr_dB": np.nan,
            "df_hz": _psd_df_for_group(nist_root, group, df["channel"]),
            "band_name": df.get("band_name", "").map(canonicalize_band_label) if "band_name" in df.columns else "",
            "is_smoke_test": df.get("is_smoke_test", False),
        })
        frames.append(out)
    return pd.concat(frames, ignore_index=True)


def build_real_acf_summary_df(nist_root, groups=None):
    groups = groups or GROUPS
    frames = []
    for group in groups:
        path = nist_root / group / "acf_group_summary.xlsx"
        df = pd.read_excel(path)
        distance, pump = parse_group(group)
        out = pd.DataFrame({
            "group": df["group"],
            "distance_m": distance,
            "pump_freq_hz": pump,
            "channel": df["channel"],
            "file_id": "group_median",
            "first_strong_lag_s": df["first_strong_peak_lag_s"],
            "first_strong_acf": _first_acf_height(df),
            "global_max_lag_s": df["global_max_peak_lag_s"],
            "global_max_acf": _first_acf_height(df),
            "peak_spacing_s": df["peak_spacing_period_s"],
            "acf_decay_time_s": df["acf_decay_time_s"],
            "is_smoke_test": df.get("is_smoke_test", False),
        })
        frames.append(out)
    return pd.concat(frames, ignore_index=True)


def _psd_df_for_group(nist_root, group, channels):
    summary = pd.read_excel(nist_root / group / "psd_group_summary.xlsx")
    mapping = summary.set_index("channel")["df_hz"].to_dict()
    return channels.map(mapping)


def _first_acf_height(df):
    values = []
    for raw in df["acf_peak_height"]:
        values.append(_first_list_value(raw))
    return pd.Series(values)


def _first_list_value(raw):
    if pd.isna(raw):
        return np.nan
    text = str(raw).strip()
    if not text.startswith("["):
        try:
            return float(text)
        except ValueError:
            return np.nan
    try:
        import ast
        values = ast.literal_eval(text)
    except Exception:
        return np.nan
    return float(values[0]) if values else np.nan


def write_outputs(output_dir, psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers):
    psd_gain.to_csv(output_dir / "background_psd_diff_curves.csv", index=False)
    _excel(bandpower, output_dir / "background_bandpower_contrast.xlsx", "bandpower")
    _excel(peak, output_dir / "background_peak_contrast.xlsx", "peak_contrast")
    _excel(acf, output_dir / "background_acf_contrast.xlsx", "acf_contrast")
    _excel(cross_channel, output_dir / "cross_channel_background_contrast.xlsx", "cross_channel")
    _excel(pumpfreq_net, output_dir / "pumpfreq_net_contrast.xlsx", "pumpfreq_net")
    _excel(distance_decay, output_dir / "distance_decay_after_background.xlsx", "distance_decay")
    _excel(qc_outliers, output_dir / "qc_outlier_channels.xlsx", "qc_outliers")


def write_figures_from_outputs(output_dir, dpi=160):
    """Render figures by reading exported tables one at a time."""
    output_dir = Path(output_dir)
    fig_dir = output_dir / "figures"
    plot_status = {}
    active_channels = read_active_channels(output_dir)
    if active_channels:
        write_active_channels(output_dir, active_channels)

    with timed_step("background_contrast.figure_read", table="bandpower"):
        bandpower = add_band_display_columns(_read_excel_table(output_dir / "background_bandpower_contrast.xlsx"), "band_name")
    _heatmap(
        bandpower,
        index="display_label",
        columns="active_group",
        values="band_gain_dB",
        title="Median Bandpower Gain dB (missing data shown blank/gray)",
        output_path=fig_dir / "bandpower_gain_heatmap.png",
        dpi=dpi,
    )
    plot_status["bandpower_gain_heatmap"] = {"skipped": False}

    with timed_step("background_contrast.figure_read", table="cross_channel"):
        cross_channel = canonicalize_feature_column(_read_excel_table(output_dir / "cross_channel_background_contrast.xlsx"), "feature_name")
        cross_channel = add_feature_plot_label(cross_channel)
    support_count = len(active_channels) if active_channels else active_channel_count_from_support(cross_channel)
    _heatmap(
        cross_channel,
        index="plot_label",
        columns="contrast_pair",
        values="support_channel_count",
        title=f"Cross-Channel Support Count / {support_count} (missing data shown blank/gray; row label = feature type + band)",
        output_path=fig_dir / "cross_channel_support_heatmap.png",
        colorbar_label=f"support_channel_count / {support_count}",
        dpi=dpi,
    )
    plot_status["cross_channel_support_heatmap"] = {
        "skipped": False,
        "active_channel_count": support_count,
        "row_label": "feature_type: display_label",
        "wide_band_note": "peak: 10-200 kHz (wide) is a wide peak band, not a default bandpower band",
        "one_to_ten_khz_note": "bandpower: 1-10 kHz and peak: 1-10 kHz are plotted on separate rows to avoid feature-type label collision",
    }

    with timed_step("background_contrast.figure_read", table="pumpfreq_net"):
        pumpfreq_net = canonicalize_feature_column(_read_excel_table(output_dir / "pumpfreq_net_contrast.xlsx"), "feature_name")
    _heatmap(
        pumpfreq_net[pumpfreq_net["feature_type"] == "bandpower"],
        index="display_label",
        columns="distance_m",
        values="delta_50_minus_30",
        title="Pump Net Contrast: 50Hz Net - 30Hz Net (missing data shown blank/gray)",
        output_path=fig_dir / "pumpfreq_net_contrast_heatmap.png",
        dpi=dpi,
    )
    plot_status["pumpfreq_net_contrast_heatmap"] = {"skipped": False}

    with timed_step("background_contrast.figure_read", table="distance_decay"):
        distance_decay = canonicalize_feature_column(_read_excel_table(output_dir / "distance_decay_after_background.xlsx"), "feature_name")
    available_distances = available_distance_count_from_outputs(output_dir, pumpfreq_net, distance_decay)
    if available_distances < 2:
        plot_status["distance_decay_after_background"] = {
            "skipped_distance_decay": True,
            "reason": "need at least 2 distances",
            "available_distance_count": available_distances,
        }
        stale = fig_dir / "distance_decay_after_background.png"
        if stale.exists():
            stale.unlink()
    else:
        _line_distance_decay(distance_decay, fig_dir / "distance_decay_after_background.png", dpi=dpi)
        plot_status["distance_decay_after_background"] = {"skipped_distance_decay": False, "available_distance_count": available_distances}

    with timed_step("background_contrast.figure_read", table="qc_outliers"):
        qc_outliers = canonicalize_feature_column(_read_excel_table(output_dir / "qc_outlier_channels.xlsx"), "feature_name")
    outlier_overview = read_outlier_overview(output_dir, active_channels)
    _outlier_overview(outlier_overview, fig_dir / "outlier_channel_overview.png", dpi=dpi)
    plot_status["outlier_channel_overview"] = {"skipped": False}
    (output_dir / "plot_status.json").write_text(json.dumps(plot_status, indent=2, ensure_ascii=False), encoding="utf-8")
    append_plot_status_to_report(output_dir, plot_status)


def append_plot_status_to_report(output_dir, plot_status):
    report_path = Path(output_dir) / "contrast_summary_report.md"
    lines = ["", "## Plot Cleanup Status", ""]
    distance = plot_status.get("distance_decay_after_background", {})
    if distance.get("skipped_distance_decay"):
        lines.append("- skipped_distance_decay: true")
        lines.append(f"- reason: {distance.get('reason', 'UNKNOWN')}")
    else:
        lines.append("- skipped_distance_decay: false")
    cross_channel = plot_status.get("cross_channel_support_heatmap", {})
    if cross_channel:
        lines.append(f"- cross_channel_row_label: {cross_channel.get('row_label', 'UNKNOWN')}")
        lines.append(f"- wide_band_note: {cross_channel.get('wide_band_note', 'UNKNOWN')}")
        lines.append(f"- one_to_ten_khz_note: {cross_channel.get('one_to_ten_khz_note', 'UNKNOWN')}")
    text = "\n".join(lines) + "\n"
    if report_path.exists():
        existing = report_path.read_text(encoding="utf-8")
        marker = "\n## Plot Cleanup Status\n"
        if marker in existing:
            existing = existing.split(marker)[0].rstrip() + "\n"
        report_path.write_text(existing + text, encoding="utf-8")
    else:
        report_path.write_text("# Background Contrast v1.0 Report\n" + text, encoding="utf-8")


def write_figures(fig_dir, bandpower, cross_channel, pumpfreq_net, distance_decay, qc_outliers, dpi=160):
    support_count = active_channel_count_from_support(cross_channel)
    _heatmap(
        bandpower,
        index="band_name",
        columns="active_group",
        values="band_gain_dB",
        title="Median Bandpower Gain dB (missing data shown blank/gray)",
        output_path=fig_dir / "bandpower_gain_heatmap.png",
        dpi=dpi,
    )
    _heatmap(
        cross_channel,
        index="feature_name",
        columns="contrast_pair",
        values="support_channel_count",
        title=f"Cross-Channel Support Count / {support_count} (missing data shown blank/gray)",
        output_path=fig_dir / "cross_channel_support_heatmap.png",
        colorbar_label=f"support_channel_count / {support_count}",
        dpi=dpi,
    )
    _heatmap(
        pumpfreq_net[pumpfreq_net["feature_type"] == "bandpower"],
        index="feature_name",
        columns="distance_m",
        values="delta_50_minus_30",
        title="Pump Net Contrast: 50Hz Net - 30Hz Net (missing data shown blank/gray)",
        output_path=fig_dir / "pumpfreq_net_contrast_heatmap.png",
        dpi=dpi,
    )
    _line_distance_decay(distance_decay, fig_dir / "distance_decay_after_background.png", dpi=dpi)
    _outlier_overview(qc_outliers, fig_dir / "outlier_channel_overview.png", dpi=dpi)


def _heatmap(df, index, columns, values, title, output_path, colorbar_label=None, dpi=160):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path = output_path.with_name(f"{output_path.stem}_matrix.csv")
    if "missing data shown" not in title.lower():
        title = f"{title} (missing data shown blank/gray)"
    plt.figure(figsize=(12, 7))
    if df.empty:
        pd.DataFrame().to_csv(matrix_path, encoding="utf-8-sig")
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
    else:
        pivot = df.pivot_table(index=index, columns=columns, values=values, aggfunc="median")
        pivot.to_csv(matrix_path, encoding="utf-8-sig")
        cmap = colormaps.get_cmap("coolwarm").copy()
        cmap.set_bad(color="#d9d9d9")
        masked = np.ma.masked_invalid(pivot.values.astype(float))
        plt.imshow(masked, aspect="auto", cmap=cmap)
        plt.colorbar(label=colorbar_label or values)
        plt.xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns], rotation=45, ha="right")
        plt.yticks(range(len(pivot.index)), [str(i) for i in pivot.index])
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi)
    plt.close()


def _line_distance_decay(df, output_path, dpi=160):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))
    current = df[(df["feature_type"] == "bandpower") & (df["channel"] == "channel1")]
    if current.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
    else:
        for _, row in current.head(12).iterrows():
            label = row.get("display_label", row["feature_name"])
            plt.plot([2, 3, 5], [row["net_value_2m"], row["net_value_3m"], row["net_value_5m"]], marker="o", label=f"{_format_hz(row['pump_freq_hz'])}, {label}")
        plt.legend(fontsize=7)
        plt.xlabel("distance_m")
        plt.ylabel("net value")
    plt.title("Distance Decay After Background Subtraction")
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi)
    plt.close()


def _outlier_overview(df, output_path, dpi=160):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 5))
    if df.empty:
        plt.text(0.5, 0.5, "No outlier metric-band rows", ha="center", va="center")
    else:
        df = df.sort_values("channel", key=lambda s: s.map(channel_sort_key))
        plt.bar(df["channel"], df["outlier_count"])
        plt.xticks(rotation=45, ha="right")
        plt.ylabel("outlier metric-band rows")
    plt.title("Outlier Channel Overview (all active channels)")
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi)
    plt.close()


def _format_hz(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value}Hz"
    if number.is_integer():
        return f"{int(number)}Hz"
    return f"{number:g}Hz"


def read_active_channels(output_dir):
    path = Path(output_dir) / "active_channels.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted(payload.get("channels", []), key=channel_sort_key)


def read_outlier_overview(output_dir, active_channels):
    path = Path(output_dir) / "outlier_channel_overview.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame({
        "channel": active_channels,
        "outlier_count": [0] * len(active_channels),
        "total_checked_rows": [0] * len(active_channels),
        "outlier_ratio": [np.nan] * len(active_channels),
    })


def active_channel_count_from_support(cross_channel):
    if cross_channel is None or cross_channel.empty or "support_channel_ratio" not in cross_channel.columns:
        return len(REAL_CHANNELS)
    valid = cross_channel[
        cross_channel["support_channel_ratio"].notna()
        & (cross_channel["support_channel_ratio"].astype(float) > 0)
    ]
    if valid.empty:
        return len(REAL_CHANNELS)
    estimates = valid["support_channel_count"].astype(float) / valid["support_channel_ratio"].astype(float)
    estimates = estimates[np.isfinite(estimates)]
    return int(round(float(estimates.median()))) if len(estimates) else len(REAL_CHANNELS)


def available_distance_count_from_outputs(output_dir, pumpfreq_net, distance_decay):
    distances = set()
    if pumpfreq_net is not None and not pumpfreq_net.empty and "distance_m" in pumpfreq_net.columns:
        distances.update(float(value) for value in pumpfreq_net["distance_m"].dropna().unique())
    if distance_decay is not None and not distance_decay.empty:
        for column in ("net_value_2m", "net_value_3m", "net_value_5m"):
            if column in distance_decay.columns and distance_decay[column].notna().any():
                distances.add(float(column.split("_")[-1].replace("m", "")))
    return len(distances)


def channel_sort_key(channel):
    match = re.fullmatch(r"channel(\d+)", str(channel))
    return int(match.group(1)) if match else 10**9


def validate_outputs(output_dir, pairs, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, run_info, require_figures=True, require_distance_decay=True):
    checks = {}
    required_now = [name for name in OUTPUT_FILES if name not in {"contrast_summary_report.md", "contrast_run_log.txt"}]
    checks["all_output_files"] = all((output_dir / name).exists() for name in required_now)
    if require_figures:
        checks["all_figures"] = all((output_dir / name).exists() for name in FIGURE_FILES)
    active_pairs = pairs[pairs["pump_freq_hz"] != 0]
    checks["background_pairs_present"] = not active_pairs.empty and not active_pairs["missing_background"].any()
    checks["pairs_have_12_channels"] = all(
        bandpower[bandpower["active_group"] == row["active_group"]]["channel"].nunique() == 12
        for _, row in active_pairs.iterrows()
    )
    checks["formal_channels_only"] = not bandpower["channel"].astype(str).str.upper().eq("ALL").any()
    checks["cross_channel_has_conclusion"] = "conclusion_level" in cross_channel.columns and not cross_channel["conclusion_level"].isna().any()
    checks["pumpfreq_net_present"] = not pumpfreq_net.empty and "delta_50_minus_30" in pumpfreq_net.columns
    if require_distance_decay:
        checks["distance_decay_present"] = not distance_decay.empty and {"net_value_2m", "net_value_3m", "net_value_5m"}.issubset(distance_decay.columns)
    low = bandpower[bandpower["band_name"].isin(["30hz_pm2hz", "50hz_pm2hz", "60hz_pm2hz"])]
    checks["lowfreq_has_reliable_flag"] = not low.empty and "lowfreq_reliable_flag" in low.columns
    checks["no_missing_psd_acf_peak"] = not bandpower.empty and not acf.empty and not peak.empty
    status = "PASS" if all(checks.values()) else "FAIL"
    return {"status": status, "checks": checks}


def build_run_log(run_info, smoke_coverage, validation, pairs, bandpower, acf, peak):
    lines = ["# Background Contrast v1.0 Run Log", ""]
    lines.append(f"smoke_test_coverage_status = {smoke_coverage['status']}")
    lines.append(f"validation_status = {validation['status']}")
    lines.append(f"groups = {', '.join(run_info['groups'].keys())}")
    lines.append(f"channel_ALL_present = {run_info['channel_all_present']}")
    lines.append(f"channel_ALL_excluded = {run_info['channel_all_excluded']}")
    lines.append(f"background_pair_count = {len(pairs)}")
    lines.append("")
    lines.append("## Group channel/file counts")
    for group, info in run_info["groups"].items():
        counts = sorted(set(info["channel_file_counts"].values()))
        lines.append(f"- {group}: channel_count={info['channel_count']}, file_counts={counts}")
    lines.append("")
    lines.append("## Pair channel counts")
    for _, row in pairs.iterrows():
        channels = bandpower[bandpower["active_group"] == row["active_group"]]["channel"].nunique()
        lines.append(f"- {row['active_group']} vs {row['background_group']}: channels={channels}")
    lines.append("")
    lines.append(f"missing_psd_data = {bandpower.empty}")
    lines.append(f"missing_acf_data = {acf.empty}")
    lines.append(f"missing_peak_data = {peak.empty}")
    low = bandpower[bandpower["band_name"].isin(["30hz_pm2hz", "50hz_pm2hz", "60hz_pm2hz"])]
    reliable_count = int(low["lowfreq_reliable_flag"].sum()) if not low.empty else 0
    lines.append(f"low_frequency_reliable_rows = {reliable_count}/{len(low)}")
    lines.append("")
    lines.append("## Output checks")
    for key, value in validation["checks"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def build_report(run_info, smoke_coverage, pairs, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay, qc_outliers, validation, output_dir=None):
    lines = ["# Background Contrast v1.0 Report", ""]
    lines.extend(_report_run_summary(run_info, validation, output_dir))
    lines.extend(_report_smoke(smoke_coverage))
    lines.extend(_report_pair_results(cross_channel, qc_outliers))
    lines.extend(_report_bandpower(bandpower))
    lines.extend(_report_peak(peak))
    lines.extend(_report_acf(acf))
    lines.extend(_report_pumpfreq(pumpfreq_net))
    lines.extend(_report_decay(distance_decay))
    lines.extend(_report_outliers(qc_outliers))
    lines.extend(_report_conclusions(cross_channel))
    lines.extend([
        "## 11. Limitations",
        "",
        "- Background and active groups were not synchronously acquired, so no raw waveform point-by-point subtraction was performed.",
        "- Low-frequency 30/50/60Hz reliability depends on `df_hz` and `bin_count`.",
        "- Observed differences cannot be directly attributed to water flow.",
        "- Observed differences cannot be directly equated with the power-supply frequency itself.",
        "- This remains feature-level background contrast, not physical source separation.",
        "- PSD curves were adapter-generated as `psd_curve_level = group_median_recomputed`; p10/p90 in curve contrast are not file-level re-estimates.",
        "",
    ])
    return "\n".join(lines)


def _report_run_summary(run_info, validation, output_dir=None):
    lines = ["## 1. Run Summary", ""]
    lines.append(f"- Input groups: {', '.join(run_info['groups'].keys())}.")
    lines.append("- Formal channels: channel1-channel12.")
    lines.append(f"- `channel=ALL` present: {run_info['channel_all_present']}; excluded from formal statistics: {run_info['channel_all_excluded']}.")
    missing = []
    for group, info in run_info["groups"].items():
        if info["channel_count"] != 12 or sorted(set(info["channel_file_counts"].values())) != [40]:
            missing.append(group)
    lines.append(f"- Missing or incomplete groups: {', '.join(missing) if missing else 'none'}.")
    output_location = str(output_dir) if output_dir is not None else "UNKNOWN"
    lines.append(f"- Output location: `{output_location}`.")
    lines.append("")
    return lines


def _report_smoke(smoke_coverage):
    lines = ["## 2. Smoke Coverage", "", f"smoke_test_coverage_status = {smoke_coverage['status']}", ""]
    for item, covered in smoke_coverage["items"].items():
        lines.append(f"- {'PASS' if covered else 'MISSING'}: {item}")
    lines.append("")
    return lines


def _report_pair_results(cross_channel, qc_outliers):
    lines = ["## 3. Background Pair Results", ""]
    for pair, group in cross_channel.groupby("contrast_pair"):
        levels = group["conclusion_level"].value_counts().to_dict()
        top = group.sort_values(["support_channel_count", "median_delta"], ascending=[False, False]).head(5)
        outlier_channels = sorted(set(qc_outliers["channel"])) if not qc_outliers.empty else []
        lines.append(f"- {pair}: levels={levels}; top features=" + ", ".join(f"{r.feature_type}:{r.feature_name}({int(r.support_channel_count)})" for r in top.itertuples()) + f"; outlier_channels={outlier_channels or 'none'}")
    lines.append("")
    return lines


def _report_bandpower(bandpower):
    lines = ["## 4. Bandpower Contrast", ""]
    for band, group in bandpower.groupby("band_name"):
        median_gain = group.groupby("active_group")["band_gain_dB"].median().round(3).to_dict()
        support = group.groupby("active_group")["support_flag"].sum().astype(int).to_dict()
        reliable = group["lowfreq_reliable_flag"].astype(bool).all()
        lines.append(f"- {band}: median_gain_dB={median_gain}; support_rows={support}; lowfreq_reliable_all={reliable}.")
    lines.append("")
    return lines


def _report_peak(peak):
    lines = ["## 5. Peak Contrast", ""]
    for label, low, high in [("8.5kHz nearby", 8200, 8800), ("50kHz nearby", 49000, 51000), ("59.5kHz nearby", 58500, 60500), ("30/50/60Hz nearby", 28, 62)]:
        current = peak[(peak["peak_freq_hz"] >= low) & (peak["peak_freq_hz"] <= high)]
        counts = current["peak_type"].value_counts().to_dict() if not current.empty else {}
        lines.append(f"- {label}: {counts or 'none'}.")
    lines.append("")
    return lines


def _report_acf(acf):
    lines = ["## 6. ACF Contrast", ""]
    summary = acf.groupby("active_group").agg(
        change_count=("acf_change_flag", "sum"),
        median_delta_first_acf=("delta_first_strong_acf", "median"),
        median_delta_global_acf=("delta_global_max_acf", "median"),
        median_delta_spacing=("delta_peak_spacing_s", "median"),
    )
    for group, row in summary.iterrows():
        lines.append(f"- {group}: changed_channels={int(row.change_count)}/12, median_delta_first_acf={row.median_delta_first_acf:.4g}, median_delta_global_acf={row.median_delta_global_acf:.4g}, median_delta_peak_spacing_s={row.median_delta_spacing:.4g}.")
    lines.append("")
    return lines


def _report_pumpfreq(pumpfreq_net):
    lines = ["## 7. 30Hz vs 50Hz Net Contrast", "", "Formula: `(50Hz - 0Hz) - (30Hz - 0Hz)`.", ""]
    current = pumpfreq_net[pumpfreq_net["feature_type"] == "bandpower"]
    for distance, group in current.groupby("distance_m"):
        distinguish = int(group["can_distinguish_flag"].sum())
        lines.append(f"- {distance:g}m: distinguishable_rows={distinguish}/{len(group)}.")
    lines.append("")
    return lines


def _report_decay(distance_decay):
    lines = ["## 8. Distance Decay", ""]
    if distance_decay.empty:
        lines.append("- No complete 2m/3m/5m feature triplets.")
    else:
        count = int(distance_decay["monotonic_decay_flag"].sum())
        lines.append(f"- Monotonic decay rows: {count}/{len(distance_decay)}.")
    lines.append("")
    return lines


def _report_outliers(qc_outliers):
    lines = ["## 9. Outlier Channels", ""]
    if qc_outliers.empty:
        lines.append("- No QC outlier rows marked.")
    else:
        for channel, group in qc_outliers.groupby("channel"):
            lines.append(f"- {channel}: {len(group)} marked rows; examples={group['feature_name'].head(5).tolist()}.")
    lines.append("- Outliers are marked only; no rows were deleted.")
    lines.append("")
    return lines


def _report_conclusions(cross_channel):
    strong = cross_channel[cross_channel["conclusion_level"] == "strong"].head(10)
    medium = cross_channel[cross_channel["conclusion_level"] == "medium"].head(10)
    none = cross_channel[cross_channel["conclusion_level"] == "none"].head(10)
    lines = ["## 10. Conclusions", "", "Strong evidence:"]
    lines.extend(f"- {r.contrast_pair} {r.feature_type}:{r.feature_name} support={int(r.support_channel_count)}/12." for r in strong.itertuples())
    lines.append("")
    lines.append("Moderate evidence:")
    lines.extend(f"- {r.contrast_pair} {r.feature_type}:{r.feature_name} support={int(r.support_channel_count)}/12." for r in medium.itertuples())
    lines.append("")
    lines.append("Not supported:")
    lines.extend(f"- {r.contrast_pair} {r.feature_type}:{r.feature_name} support={int(r.support_channel_count)}/12." for r in none.itertuples())
    lines.append("")
    return lines


def _excel(df, path, sheet):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet[:31], index=False)


def parse_group(group):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)m(\d+(?:\.\d+)?)hz", group)
    if not match:
        raise ValueError(f"invalid group name: {group}")
    return float(match.group(1)), float(match.group(2))


if __name__ == "__main__":
    main()
