"""Read existing DPS150 logs only; never opens the serial port."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/dps150_modulation_feasibility_20261104/rate_benchmark"


def main():
    rows, inputs = [], []
    for name in ("dps150_rate_20261104_142720", "dps150_rate_20261104_142833"):
        folder = ROOT / "local/logs" / name
        for filename in ("commands.csv", "telemetry.csv", "summary.json"):
            path = folder / filename
            inputs.append(dict(path=str(path.relative_to(ROOT)),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        with (folder / "commands.csv").open(encoding="utf-8-sig", newline="") as handle:
            commands = list(csv.DictReader(handle))
        with (folder / "telemetry.csv").open(encoding="utf-8-sig", newline="") as handle:
            telemetry = list(csv.DictReader(handle))
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        for result in summary["results"]:
            stage = result["stage"]
            selected = [row for row in commands if row["stage"] == stage]
            sent = np.array([float(row["sent_s"]) for row in selected])
            planned = np.array([float(row["target_s"]) for row in selected])
            intervals = np.diff(sent)*1000
            late = (sent-planned)*1000
            rate = result["requested_rate_hz"]
            updates = [float(row["t_s"]) for row in telemetry
                       if row["stage"] == stage and row["frame_kind"] == "195"]
            assert len(selected) == result["acknowledged_count"]
            assert all(row["match"] == "True" for row in selected)
            rows.append(dict(log=name, stage=stage, requested_updates_per_s=rate,
                points=len(selected), all_setpoint_readbacks_match=True,
                scheduling_rule_pass=result["schedule_pass"],
                send_interval_quantiles_ms=dict(zip(
                    ("min", "p01", "p50", "p95", "p99", "max"),
                    np.quantile(intervals, (0, .01, .5, .95, .99, 1)).tolist())),
                host_lateness_p95_ms=float(np.quantile(late, .95)),
                host_lateness_max_ms=float(max(late)),
                late_by_more_than_one_slot_count=int(sum(late > 1000/rate)),
                interval_over_two_slots_count=int(sum(intervals > 2000/rate)),
                output_telemetry_frame_count=len(updates),
                output_telemetry_interval_median_ms=(
                    float(np.median(np.diff(updates))*1000) if len(updates)>1 else None)))
    report = dict(
        scope="Existing log audit; no hardware actions or new output tests",
        official_sources=["https://www.fnirsi.com/products/dps-150",
                          "https://www.fnirsi.com/pages/software-downloads"],
        official_software_documented_sweep_delay_s=[1, 86400],
        official_documentation_checked_date="2026-11-04",
        interpretation="200/s is a tested short-duration SET-current + GET-current-setpoint pattern, not analog bandwidth or a uniform output update rate",
        independently_measured_output_step_response=None,
        independently_measured_modulation_bandwidth=None,
        official_sweep_delay_is_hardware_speed_limit=False,
        raw_input_hashes=inputs, stages=rows)
    (OUT / "control_timing_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
