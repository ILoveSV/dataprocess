from pathlib import Path

import pandas as pd


def export_background_contrast_smoke_outputs(outputs, output_dir):
    """Write Background Contrast v1 smoke outputs."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs["psd_gain_curves"].to_csv(output_dir / "smoke_background_psd_diff_curves.csv", index=False)
    _to_excel(outputs["bandpower"], output_dir / "smoke_background_bandpower_contrast.xlsx", "bandpower")
    _to_excel(outputs["peak"], output_dir / "smoke_background_peak_contrast.xlsx", "peak_contrast")
    _to_excel(outputs["acf"], output_dir / "smoke_background_acf_contrast.xlsx", "acf_contrast")
    _to_excel(outputs["cross_channel"], output_dir / "smoke_cross_channel_background_contrast.xlsx", "cross_channel")
    _to_excel(outputs["pumpfreq_net"], output_dir / "smoke_pumpfreq_net_contrast.xlsx", "pumpfreq_net")
    _to_excel(outputs["distance_decay"], output_dir / "smoke_distance_decay_after_background.xlsx", "distance_decay")
    _to_excel(outputs["qc_outliers"], output_dir / "smoke_qc_outlier_channels.xlsx", "qc_outliers")
    (output_dir / "smoke_report.md").write_text(outputs["report"], encoding="utf-8")
    (output_dir / "smoke_run_log.txt").write_text(outputs["run_log"], encoding="utf-8")
    return output_dir


def _to_excel(df, output_path, sheet_name):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output_path
