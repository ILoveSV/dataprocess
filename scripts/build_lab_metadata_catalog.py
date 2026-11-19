"""Index Lab TDMS headers and existing experiment labels without reading waveforms."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from nptdms import TdmsFile


REPO = Path(__file__).resolve().parents[1]
PUMP11 = "experiments/20261111_pump/record_labels.json"
PUMP12 = "experiments/20261112_pump/EXPERIMENT_ANALYSIS_REPORT.md"
AUG06 = "experiments/20260806/analysis_manifest.json"
AUG11 = "experiments/20260811/EXPERIMENT_ANALYSIS_REPORT.md"
AUG11_2 = "experiments/20260811_2/EXPERIMENT_ANALYSIS_REPORT.md"
NEEDLE = "experiments/20261117_needle/EXPERIMENT_ANALYSIS_REPORT.md"
DETECTOR_BY_CHASSIS = {"cDAQ9188-1855C19": "TC1", "cDAQ9188-1B5105D": "TC2"}
SCHEDULE12 = {
    "2m1": [(15, "RUN50"), (30, "RUN30"), (45, "RUN50"), (55, "RUN30"),
            (70, "RUN50"), (82, "RUN30"), (100, "RUN50"), (110, "RUN30")],
    "3m1": [(25, "RUN50"), (50, "RUN30"), (90, "RUN50")],
    "4m1": [(15, "RUN50"), (45, "STOP"), (70, "RUN50"), (90, "RUN30"), (115, "STOP")],
}


def labels(parts, nov11, aug06):
    batch, *folders, filename = parts
    case = folders[-1] if folders else ""
    x = dict(detector=None, detector_status="unknown", condition=None,
             label_source=None, family=None)
    if batch in {"26.5.12", "0617"}:
        m = re.fullmatch(r"(\d+)m_?(\d+)hz", case.lower())
        if m:
            distance, hz = map(int, m.groups())
            x.update(family="pump", condition="STOP" if hz == 0 else f"NOMINAL_{hz}HZ",
                     distance_nominal_m=distance, distance_reference=None,
                     output_nominal_hz=hz, label_source="raw_folder")
            if hz == 0:
                x["condition_source"] = "operator_default_powered_stop_20261119"
    elif batch == "26.7.31":
        condition = {"background": "BG", "vfdbackground": "STOP",
                     "30": "RUN30", "30hz": "RUN30", "50": "RUN50", "50hz": "RUN50"}
        c = condition[case.lower()]
        x.update(family="pump", detector=folders[0].upper(), detector_status="documented",
                 condition=c, output_nominal_hz=int(c[3:]) if c.startswith("RUN") else None,
                 label_source="experiments/20260731/EXPERIMENT_ANALYSIS_REPORT.md")
    elif batch == "26.8.6":
        a = aug06["/".join(folders)]
        c = a["condition"]
        x.update(family="pump", detector=a["detector"], detector_status="documented",
                 condition={"background": "BG", "vfd_stop": "STOP"}.get(
                     c, f"RUN{a['output_hz']}"), output_nominal_hz=a["output_hz"],
                 carrier_nominal_khz=a["carrier_khz"], position=a["position"],
                 arrangement=a["arrangement"], label_source=AUG06)
    elif batch == "11.11":
        a = nov11["records_by_source"]["/".join(parts[1:])]
        x.update(family="pump", detector=a["detector"], detector_status="documented",
                 condition="DYNAMIC", mode=a["mode"], existing_record_id=a["record_id"],
                 distance_m=a["distance_m"], distance_nominal_m=a["distance_nominal_m"],
                 distance_status=a["distance_status"], distance_reference="sensor_to_pump",
                 nominal_intervals=nov11["protocols"][a["mode"]],
                 timing_status="operator_plan_not_synchronized", label_source=PUMP11)
    elif batch == "11.12":
        stop = case.startswith("back")
        x.update(family="pump", detector="TC2", detector_status="documented",
                 condition="STOP" if stop else "DYNAMIC",
                 distance_nominal_m=int(case[-1] if stop else case[0]),
                 distance_reference="sensor_to_pump", label_source=PUMP12)
        if not stop:
            x.update(initial_state="STOP", nominal_commands_s=SCHEDULE12[case],
                     nominal_settling_s=10, timing_status="operator_plan_not_synchronized")
    elif batch in {"8.11", "8.11.2"}:
        x.update(family="cathodic", detector="TC2", detector_status="documented",
                 label_source=AUG11 if batch == "8.11" else AUG11_2)
        steady = re.fullmatch(r"(\d+)v(\d+)ma2?", case.lower())
        toggle = re.fullmatch(r"alter(\d+)ma", case.lower())
        near = re.fullmatch(r"cp(\d+)near2?", case.lower())
        if case == "cp3000near2nottrans":
            x.update(condition="UNCONFIRMED", possible_duplicate_of=
                     f"{batch}/cp3000near2/{filename}",
                     note="Same filename in cp3000near2; do not count as an independent repeat without verification.")
        elif case in {"bkg", "bkg2"}:
            x["condition"] = "BG"
        elif case == "bar5a":
            x.update(condition="METAL_DIRECT", current_set_ma=5000)
        elif case in {"out100ma", "opensvnear"}:
            x.update(condition="OPEN", current_set_ma=100 if case == "out100ma" else None)
        elif steady:
            x.update(condition="STEADY", voltage_set_v=int(steady[1]), current_set_ma=int(steady[2]))
        elif toggle or near:
            x.update(condition="CYCLIC", current_set_ma=int((toggle or near)[1]),
                     nominal_half_period_s=30 if toggle else 5,
                     nominal_cycles=None if toggle else 12)
        elif case == "005hz":
            x.update(condition="CYCLIC", current_nominal_ma=100, nominal_half_period_s=10)
        elif case == "10to100":
            x.update(condition="STAIRCASE", nominal_current_steps_ma=[10, 50, 100, 200],
                     nominal_step_s=30, note="Operator correction: last step is 200 mA.")
    elif batch == "26.11.10":
        x.update(family="cathodic", label_source="operator description and raw folders",
                 condition="BG" if case.startswith("back") else "ON_OFF")
        if case in {"35ma", "3v5ma2min"}:
            high = case == "35ma"
            x.update(voltage_nominal_v=20 if high else 3, current_nominal_ma=35 if high else 5,
                     nominal_on_s=60 if high else 120, nominal_sequence=["OFF", "ON", "OFF"],
                     conductivity_reported=250, conductivity_unit=None)
    elif batch.startswith("11.17"):
        nw = "西北" in folders[0]
        kv = int(case.lower().removesuffix("kv"))
        x.update(family="needle_plate", detector="TC1", detector_status="documented",
                 condition="HV_ON_OFF", voltage_nominal_kv=kv, bearing="NW" if nw else "N",
                 distance_nominal_m=1.5 if nw else 1.8, distance_reference=None,
                 nominal_sequence=["OFF", "ON", "OFF"], label_source=NEEDLE,
                 current_reported_for_group=kv in {10, 15},
                 current_report_status="reported" if kv in {10, 15} else "not_reported",
                 vessel_nominal_tonnes=4)
    return x


def header(path):
    tdms = TdmsFile.read_metadata(path)
    channels = []
    for g in tdms.groups():
        for ch in g.channels():
            p = ch.properties
            channels.append(dict(group=g.name, name=ch.name, ni_name=p.get("NI_ChannelName"),
                                 unit=p.get("unit_string"), samples=len(ch),
                                 interval_s=p.get("wf_increment"),
                                 wf_start_time_raw=str(p["wf_start_time"]) if "wf_start_time" in p else None))
    rates = {c["interval_s"] for c in channels}
    counts = {c["samples"] for c in channels}
    dt = next(iter(rates)) if len(rates) == 1 else None
    duration = next(iter(counts)) * dt if len(counts) == 1 and dt else None
    chassis = sorted({m[0] for c in channels if (
        m := re.match(r"cDAQ\d+-[0-9A-F]+(?=Mod)", c["ni_name"] or c["name"], re.I))})
    return dict(channel_count=len(channels), channels=channels, chassis=chassis,
                sample_rate_hz=round(1 / dt, 6) if dt else None, duration_s=duration)


def build(root):
    nov11 = json.loads((REPO / PUMP11).read_text(encoding="utf-8"))
    nov11["records_by_source"] = {r["source"]: r for r in nov11["records"]}
    aug06 = {"/".join(a["folder"].split("\\")[-2:]): a for a in
             json.loads((REPO / AUG06).read_text(encoding="utf-8"))["cases"]}
    records, companions = [], []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root)
        if path.suffix.lower() != ".tdms":
            if path.suffix.lower() != ".tdms_index" or not path.with_suffix(".tdms").exists():
                companions.append(dict(path=relative.as_posix(), bytes=path.stat().st_size))
            continue
        x = dict(record_id=relative.as_posix(), batch=relative.parts[0],
                 case=path.parent.name, bytes=path.stat().st_size,
                 has_tdms_index=path.with_suffix(".tdms_index").exists())
        x.update(labels(relative.parts, nov11, aug06))
        try:
            x.update(header(path))
            x["metadata_read_status"] = "ok"
        except (OSError, ValueError, RuntimeError, EOFError) as exc:
            x.update(metadata_read_status="error", metadata_read_error=str(exc))
        records.append(x)

    for x in records:
        if len(x.get("chassis", [])) != 1:
            continue
        detector = DETECTOR_BY_CHASSIS.get(x["chassis"][0])
        if detector and x["detector"] not in (None, detector):
            raise ValueError(f"Detector label conflicts with known chassis: {x['record_id']}")
        if detector and x["detector"] is None:
            x.update(detector=detector, detector_status="confirmed_chassis_match")
    return dict(schema_version=1, raw_root=root.as_posix(),
                detector_by_chassis=DETECTOR_BY_CHASSIS,
                created_utc=datetime.now(timezone.utc).isoformat(),
                companion_files=companions, records=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("D:/Lab/raw/raw"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.raw.resolve(strict=True))
    if not result["records"]:
        parser.error("no TDMS files found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    print(f"{len(result['records'])} records; {args.output}")


if __name__ == "__main__":
    main()
