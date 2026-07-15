import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


DEFAULT_ANALYSIS_ROOT = Path("analysis_out")
DOC_PATH = Path("docs/ML_FEATURE_PIPELINE_INTEGRATION_V1.md")


def main(argv=None):
    parser = argparse.ArgumentParser(description="ML Feature Pipeline Integration v1 orchestrator.")
    parser.add_argument("--output", default="analysis_out/ml_feature_pipeline_integration_v1")
    parser.add_argument("--analysis-root", default="analysis_out")
    parser.add_argument("--time-root", default="D:/Lab/process/26.5.12/time")
    parser.add_argument("--fft-root", default="D:/Lab/process/26.5.12/frequency")
    parser.add_argument("--background-output", default="D:/Lab/results/26.5.12/background_contrast_v1")
    parser.add_argument("--run-missing", action="store_true", help="Run modules only when their required artifacts are missing.")
    parser.add_argument("--force-run", action="store_true", help="Run registered modules even if outputs already exist. Heavy; use explicitly.")
    parser.add_argument("--dry-run", action="store_true", help="Only write planned commands and manifest; do not run modules.")
    args = parser.parse_args(argv)

    output_dir = Path(args.output)
    analysis_root = Path(args.analysis_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = build_registry(args, analysis_root)
    manifest = {
        "pipeline_name": "ML Feature Pipeline Integration v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "positioning": "pre-ML feature processing, QC, validation, and feature-set recommendation; no model training",
        "inputs": {
            "time_root": args.time_root,
            "fft_root": args.fft_root,
            "background_output": args.background_output,
            "analysis_root": str(analysis_root),
        },
        "execution_policy": {
            "run_missing": bool(args.run_missing),
            "force_run": bool(args.force_run),
            "dry_run": bool(args.dry_run),
            "default_behavior": "reuse existing artifacts and summarize status",
        },
        "layers": layer_descriptions(),
        "modules": [],
        "candidate_ml_inputs": {},
        "human_confirmation_needed": human_confirmation_items(),
    }

    for module in registry:
        status = inspect_module(module)
        run_allowed = module.get("run_allowed", True)
        should_run = run_allowed and (args.force_run or (args.run_missing and status["status"] != "complete"))
        status["planned_command"] = module["command"]
        status["ran"] = False
        if not run_allowed and status["status"] != "complete":
            status["status"] = "artifact_only_missing"
            status["run_blocked_reason"] = module.get("run_blocked_reason", "module is artifact-only in this integration pipeline")
        if should_run and not args.dry_run:
            status["run_result"] = run_module(module["command"])
            status["ran"] = True
            status.update(inspect_module(module))
        elif should_run and args.dry_run:
            status["status"] = "planned_not_run"
        manifest["modules"].append({**module_public_info(module), **status})

    manifest["candidate_ml_inputs"] = candidate_ml_inputs(analysis_root)
    manifest["overall_status"] = summarize_overall(manifest["modules"])
    manifest["ml_ready_note"] = ml_ready_note(manifest)

    write_json(output_dir / "ml_feature_pipeline_manifest_v1.json", manifest)
    write_json(output_dir / "ml_feature_pipeline_module_registry_v1.json", registry)
    write_markdown_summary(output_dir / "ml_feature_pipeline_summary_v1.md", manifest)
    write_report(DOC_PATH, manifest)
    print(f"ML Feature Pipeline Integration v1 output: {output_dir}")


def build_registry(args, root):
    return [
        {
            "module_id": "frequency_feature_extraction_v2",
            "layer": "feature_computation",
            "purpose": "Extract file_id x channel PSD/bandpower/subband/peak-window features from FFT CSV files.",
            "module": "src.pipelines.candidate_feature_extraction_v2_pipeline",
            "output_dir": str(root / "feature_extraction_v2"),
            "required_artifacts": [
                str(root / "feature_extraction_v2/candidate_feature_dataset_v2.csv"),
                str(root / "feature_extraction_v2/feature_stability_summary_v2.csv"),
                str(root / "feature_extraction_v2/channel_feature_summary_v2.csv"),
                str(root / "feature_extraction_v2/all_vs_strict_feature_delta_v2.csv"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.candidate_feature_extraction_v2_pipeline",
                "--fft-root", args.fft_root,
                "--background-output", args.background_output,
                "--output", str(root / "feature_extraction_v2"),
            ],
            "heavy": True,
            "notes": "Uses strict/all-data mode from existing frequency-axis audit; no ML.",
        },
        {
            "module_id": "time_domain_features_v1",
            "layer": "feature_computation",
            "purpose": "Extract file_id x channel time-domain statistics and QC indicators.",
            "module": "src.pipelines.time_domain_feature_extraction_v1_pipeline",
            "output_dir": str(root / "time_domain_features_v1"),
            "required_artifacts": [
                str(root / "time_domain_features_v1/time_domain_feature_dataset_v1.csv"),
                str(root / "time_domain_features_v1/time_domain_feature_stability_summary_v1.csv"),
                str(root / "time_domain_features_v1/time_domain_feature_input_audit.json"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.time_domain_feature_extraction_v1_pipeline",
                "--time-root", args.time_root,
                "--output", str(root / "time_domain_features_v1"),
            ],
            "heavy": True,
            "notes": "No plots or ML; produces time-stat feature table.",
        },
        {
            "module_id": "acf_features_v1",
            "layer": "feature_computation",
            "purpose": "Extract ACF/autocorrelation features from time CSV files.",
            "module": "src.pipelines.acf_feature_analysis_v1_pipeline",
            "output_dir": str(root / "acf_features_v1"),
            "required_artifacts": [
                str(root / "acf_features_v1/acf_feature_dataset_v1.csv"),
                str(root / "acf_features_v1/acf_feature_stability_summary_v1.csv"),
                str(root / "acf_features_v1/acf_feature_separability_summary_v1.csv"),
                str(root / "acf_features_v1/recommended_acf_feature_sets_v1.json"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.acf_feature_analysis_v1_pipeline",
                "--time-root", args.time_root,
                "--output", str(root / "acf_features_v1"),
            ],
            "heavy": True,
            "notes": "ACF near high-frequency lags remains auxiliary/risk-marked.",
        },
        {
            "module_id": "time_frequency_stability_features_v1",
            "layer": "feature_computation",
            "purpose": "Extract rolling FFT / window-level TF stability features from time CSV files.",
            "module": "src.pipelines.time_frequency_stability_feature_analysis_v1_pipeline",
            "output_dir": str(root / "time_frequency_stability_features_v1"),
            "required_artifacts": [
                str(root / "time_frequency_stability_features_v1/tf_window_feature_dataset_v1.csv"),
                str(root / "time_frequency_stability_features_v1/tf_stability_feature_dataset_v1.csv"),
                str(root / "time_frequency_stability_features_v1/tf_stability_feature_separability_summary_v1.csv"),
                str(root / "time_frequency_stability_features_v1/recommended_tf_stability_feature_sets_v1.json"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.time_frequency_stability_feature_analysis_v1_pipeline",
                "--time-root", args.time_root,
                "--output", str(root / "time_frequency_stability_features_v1"),
            ],
            "heavy": True,
            "notes": "No full STFT matrices; no spectrogram export by default.",
        },
        {
            "module_id": "channel_correlation_features_v1",
            "layer": "qc_and_channel_structure",
            "purpose": "Extract file-level channel correlation, common-mode, PCA, and dominant-channel risk features.",
            "module": "src.pipelines.channel_correlation_feature_analysis_v1_pipeline",
            "output_dir": str(root / "channel_correlation_features_v1"),
            "required_artifacts": [
                str(root / "channel_correlation_features_v1/channel_pair_correlation_dataset_v1.csv"),
                str(root / "channel_correlation_features_v1/channel_correlation_feature_dataset_v1.csv"),
                str(root / "channel_correlation_features_v1/channel_correlation_feature_role_assignment_v1.csv"),
                str(root / "channel_correlation_features_v1/recommended_channel_correlation_feature_sets_v1.json"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.channel_correlation_feature_analysis_v1_pipeline",
                "--time-root", args.time_root,
                "--output", str(root / "channel_correlation_features_v1"),
            ],
            "heavy": True,
            "notes": "QC/structure layer; does not delete channels.",
        },
        {
            "module_id": "frequency_feature_separability_v1",
            "layer": "feature_validation_and_selection",
            "purpose": "Validate frequency features with separability, redundancy, pilot baseline artifacts, and ML readiness gates.",
            "module": "src.pipelines.feature_separability_v1_pipeline",
            "output_dir": str(root / "feature_separability_v1"),
            "required_artifacts": [
                str(root / "feature_separability_v1/feature_matrix_file_agg.csv"),
                str(root / "feature_separability_v1/feature_separability_summary.csv"),
                str(root / "feature_separability_v1/ml_readiness_gate_summary.csv"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.feature_separability_v1_pipeline",
                "--output", str(root / "feature_separability_v1"),
            ],
            "heavy": False,
            "run_allowed": False,
            "run_blocked_reason": "This historical module includes pilot baseline model code; this integration pipeline reuses its artifacts but will not run it.",
            "notes": "Artifact-only in this integration because it contains pilot baseline outputs from a prior step; integration does not train ML.",
        },
        {
            "module_id": "time_frequency_comparison_v1",
            "layer": "feature_validation_and_selection",
            "purpose": "Compare time and frequency features, assign roles, and recommend feature sets.",
            "module": "src.pipelines.time_frequency_feature_comparison_v1_pipeline",
            "output_dir": str(root / "time_frequency_feature_comparison_v1"),
            "required_artifacts": [
                str(root / "time_frequency_feature_comparison_v1/combined_feature_dataset_v1.csv"),
                str(root / "time_frequency_feature_comparison_v1/combined_feature_matrix_file_agg.csv"),
                str(root / "time_frequency_feature_comparison_v1/feature_role_assignment_v1.csv"),
                str(root / "time_frequency_feature_comparison_v1/recommended_feature_sets_v1.json"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.time_frequency_feature_comparison_v1_pipeline",
                "--output", str(root / "time_frequency_feature_comparison_v1"),
            ],
            "heavy": False,
            "notes": "Validation layer; does not recompute raw features.",
        },
        {
            "module_id": "channel_mask_sensitivity_v1",
            "layer": "qc_and_channel_structure",
            "purpose": "Re-aggregate existing channel-level features under channel masks and test channel dependency.",
            "module": "src.pipelines.channel_mask_sensitivity_v1_pipeline",
            "output_dir": str(root / "channel_mask_sensitivity_v1"),
            "required_artifacts": [
                str(root / "channel_mask_sensitivity_v1/channel_mask_config_v1.json"),
                str(root / "channel_mask_sensitivity_v1/masked_feature_matrix_file_agg_v1.csv"),
                str(root / "channel_mask_sensitivity_v1/feature_robustness_by_mask_v1.csv"),
                str(root / "channel_mask_sensitivity_v1/recommended_feature_sets_after_channel_mask_v1.json"),
            ],
            "command": [
                sys.executable, "-m", "src.pipelines.channel_mask_sensitivity_v1_pipeline",
                "--output", str(root / "channel_mask_sensitivity_v1"),
            ],
            "heavy": False,
            "notes": "Current pilot mask config is an artifact, not a permanent bad-channel rule.",
        },
    ]


def inspect_module(module):
    artifacts = []
    missing = []
    for artifact in module["required_artifacts"]:
        path = Path(artifact)
        info = {"path": artifact, "exists": path.exists()}
        if path.exists():
            info["size_bytes"] = path.stat().st_size
            info.update(quick_shape(path))
        else:
            missing.append(artifact)
        artifacts.append(info)
    if not artifacts:
        status = "unknown"
    elif missing:
        status = "missing_required_artifacts"
    else:
        status = "complete"
    return {"status": status, "missing_artifacts": missing, "artifacts": artifacts}


def quick_shape(path):
    if path.suffix.lower() != ".csv":
        return {}
    try:
        df = pd.read_csv(path, nrows=5)
        rows = count_csv_rows(path)
        return {"rows": rows, "columns": len(df.columns)}
    except Exception as exc:
        return {"shape_error": str(exc)}


def count_csv_rows(path):
    count = 0
    with Path(path).open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for count, _ in enumerate(handle, start=0):
            pass
    return max(count, 0)


def run_module(command):
    result = subprocess.run(command, cwd=Path.cwd(), text=True, capture_output=True)
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-4000:],
    }


def module_public_info(module):
    return {
        "module_id": module["module_id"],
        "layer": module["layer"],
        "purpose": module["purpose"],
        "python_module": module["module"],
        "output_dir": module["output_dir"],
        "heavy": module["heavy"],
        "run_allowed_by_integration": module.get("run_allowed", True),
        "notes": module["notes"],
    }


def candidate_ml_inputs(root):
    paths = {
        "recommended_after_channel_mask": root / "channel_mask_sensitivity_v1/recommended_feature_sets_after_channel_mask_v1.json",
        "masked_file_agg_matrix": root / "channel_mask_sensitivity_v1/masked_feature_matrix_file_agg_v1.csv",
        "frequency_time_recommended_sets": root / "time_frequency_feature_comparison_v1/recommended_feature_sets_v1.json",
        "acf_recommended_sets": root / "acf_features_v1/recommended_acf_feature_sets_v1.json",
        "tf_recommended_sets": root / "time_frequency_stability_features_v1/recommended_feature_sets_with_tf_v1.json",
    }
    out = {}
    for key, path in paths.items():
        out[key] = {"path": str(path), "exists": path.exists()}
        if path.exists():
            out[key]["size_bytes"] = path.stat().st_size
    out["recommended_current_main_mask"] = "mask_no_ch9_global"
    out["recommended_conservative_mask"] = "mask_no_ch9_ch5_global"
    out["ml_training_status"] = "not_run_by_this_pipeline"
    return out


def summarize_overall(modules):
    missing = [m["module_id"] for m in modules if m["status"] != "complete"]
    if not missing:
        return "complete"
    return f"incomplete: missing or skipped modules: {', '.join(missing)}"


def ml_ready_note(manifest):
    after_mask = manifest["candidate_ml_inputs"].get("recommended_after_channel_mask", {}).get("exists", False)
    matrix = manifest["candidate_ml_inputs"].get("masked_file_agg_matrix", {}).get("exists", False)
    if after_mask and matrix and manifest["overall_status"] == "complete":
        return "Artifacts are organized for a pilot ML input selection step, but more experiments and cross-batch validation are still required before final ML claims."
    return "Not all pre-ML artifacts are complete; inspect module status before building pilot ML inputs."


def layer_descriptions():
    return {
        "feature_computation": {
            "responsibility": "compute file/channel candidate features from existing time, FFT, or intermediate data",
            "does_not_do": "does not decide final ML feature inclusion",
        },
        "qc_and_channel_structure": {
            "responsibility": "audit data quality, channel structure, bad/suspect-channel masks, and channel dependency risks",
            "does_not_do": "does not delete original data or permanently declare channels bad",
        },
        "feature_validation_and_selection": {
            "responsibility": "compute stability/separability/redundancy/role assignment and recommended feature-set artifacts",
            "does_not_do": "does not recompute raw signal features or train final ML models",
        },
    }


def human_confirmation_items():
    return [
        "Current pilot channel mask choices must be confirmed for each new dataset; channel9/channel5 are not permanent rules.",
        "Current frequency bands and peak windows are candidate ranges, not final scientific conclusions.",
        "Background group matching and label definitions must be reviewed when new variables such as water volume or conductivity are added.",
        "Future 16-channel data should update channel discovery, active-channel count, and any spatial-channel metadata.",
        "Recommended feature sets are pre-ML candidates; they require more experiments and cross-batch validation before final ML claims.",
    ]


def write_markdown_summary(path, manifest):
    lines = [
        "# ML Feature Pipeline Integration v1 Summary",
        "",
        f"- Overall status: `{manifest['overall_status']}`",
        f"- ML ready note: {manifest['ml_ready_note']}",
        "",
        "## Modules",
        "",
    ]
    for module in manifest["modules"]:
        lines.append(f"- `{module['module_id']}` [{module['layer']}]: {module['status']} -> `{module['output_dir']}`")
    lines += [
        "",
        "## Candidate ML Inputs",
        "",
    ]
    for key, info in manifest["candidate_ml_inputs"].items():
        if isinstance(info, dict):
            lines.append(f"- `{key}`: exists={info.get('exists')} path=`{info.get('path')}`")
        else:
            lines.append(f"- `{key}`: {info}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(path, manifest):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ML Feature Pipeline Integration v1",
        "",
        "## Positioning",
        "",
        "This is a reusable pre-ML feature processing and selection workflow. It integrates existing feature-computation, QC/channel-mask, and feature-validation artifacts. It does not train machine-learning models and does not make final scientific claims.",
        "",
        "## Three-Layer Structure",
        "",
        "### 1. Feature Computation",
        "",
        "Computes candidate features from existing time CSV, FFT CSV, or intermediate artifacts. Current modules include frequency PSD/bandpower extraction, time-domain statistics, ACF features, and time-frequency stability features.",
        "",
        "### 2. Data Quality and Channel QC",
        "",
        "Tracks file quality, channel structure, common-mode/dominant-channel risks, and channel-mask sensitivity. QC modules mark risks and produce mask-specific artifacts; they do not delete raw data or permanently remove channels.",
        "",
        "### 3. Feature Validation and Selection",
        "",
        "Consumes feature CSV/JSON artifacts and computes stability, separability, redundancy, role assignment, channel-mask robustness, and recommended candidate feature sets. It does not recompute raw signal features.",
        "",
        "## Integrated Modules",
        "",
    ]
    for module in manifest["modules"]:
        run_note = "runnable" if module.get("run_allowed_by_integration", True) else "artifact-only; not run by this orchestrator"
        lines.append(f"- `{module['module_id']}`: layer=`{module['layer']}`, status=`{module['status']}`, output=`{module['output_dir']}`, {run_note}")
    lines += [
        "",
        "## Artifact Connections",
        "",
        "- Feature computation modules write long file/channel feature tables and stability summaries.",
        "- Time/frequency, ACF, TF, and channel-mask validation modules consume those existing tables through CSV/JSON artifacts.",
        "- The final pre-ML handoff is the channel-mask sensitivity output plus recommended feature-set JSON files.",
        "- Historical artifacts that contain pilot baseline results are referenced as existing validation outputs, but this orchestrator does not run model-training or baseline-model code.",
        "",
        "## How To Re-Run For New Data",
        "",
        "Default reuse/inspection run:",
        "",
        "```powershell",
        "python -m src.pipelines.ml_feature_pipeline_integration_v1_pipeline --output analysis_out/ml_feature_pipeline_integration_v1",
        "```",
        "",
        "Run only missing artifacts:",
        "",
        "```powershell",
        "python -m src.pipelines.ml_feature_pipeline_integration_v1_pipeline --time-root D:/Lab/process/NEW/time --fft-root D:/Lab/process/NEW/frequency --background-output D:/Lab/results/NEW/background_contrast_v1 --analysis-root analysis_out/NEW_ml_features --run-missing",
        "```",
        "",
        "Use `--force-run` only when intentionally recomputing existing artifacts.",
        "",
        "## Future Extension Points",
        "",
        "- Water volume and conductivity: extend metadata parsing and task definitions in validation modules, not feature formulas.",
        "- Full 16-channel data: update active-channel discovery and channel QC artifacts; avoid fixed 12-channel assumptions in future modules.",
        "- Channel spatial relationships: add a separate channel-geometry metadata artifact and consume it in channel-structure validation.",
        "- More labels/classes: extend separability task builders while preserving feature CSV schemas.",
        "",
        "## Current Pilot Caveats",
        "",
        "- Channel9/channel5 masks are current pilot QC artifacts, not permanent rules.",
        "- 50-100 kHz, 100-200 kHz, and peak windows are candidate ranges, not final conclusions.",
        "- Current recommended feature sets are pre-ML candidates only.",
        "- More repeated experiments and cross-batch validation are needed before pilot ML or final claims.",
        "",
        "## Scope Guard",
        "",
        "- No machine learning was trained.",
        "- No new signal feature algorithm was added.",
        "- No TDMS/FFT/background contrast processing was rerun by default.",
        "- No old modules or outputs were deleted.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
