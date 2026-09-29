from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
STDOUT = ROOT / "build" / "minimal_electric_v13_stdout.log"
OUTPUT = ROOT / "results" / "minimal_electric_v13"
V9_SUMMARY = ROOT / "results" / "doorway_environment_v9_summary.csv"
DOMAIN7P5_SUMMARY = OUTPUT / "minimal_electric_v13_summary_domain7p5.csv"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
HEADER_RED = "#cf101d"
ROW_DARK = "#ebcccc"
ROW_LIGHT = "#f4e5e5"
GRID = "#ffffff"
TEXT = "#090909"

SOURCE_LABELS = {
    "motor_differential_30hz": "电机电缆三相差模基波",
    "motor_differential_50hz": "电机电缆三相差模基波",
    "cable_common_mode_4khz": "电机电缆共模单位传递",
    "cable_common_mode_8khz": "电机电缆共模单位传递",
    "cable_common_mode_12khz": "电机电缆共模单位传递",
    "cable_common_mode_20khz": "电机电缆共模单位传递",
    "cable_common_mode_50khz": "电机电缆共模单位传递",
    "cable_common_mode_80khz": "电机电缆共模单位传递",
    "cable_common_mode_100khz": "电机电缆共模单位传递",
    "cable_common_mode_120khz": "电机电缆共模单位传递",
    "cable_common_mode_150khz": "电机电缆共模单位传递",
    "cable_common_mode_200khz": "电机电缆共模单位传递",
}


def marker_rows(prefix: str) -> list[list[str]]:
    rows: list[list[str]] = []
    with STDOUT.open("r", encoding="utf-16", errors="ignore") as handle:
        for line in handle:
            marker = line.find(prefix + ",")
            if marker >= 0:
                rows.append(line[marker:].strip().split(",")[1:])
    return rows


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def frequency_label(frequency_hz: int) -> str:
    if frequency_hz < 1000:
        return f"{frequency_hz} Hz"
    return f"{frequency_hz / 1000:g} kHz"


def scientific(value: float) -> str:
    mantissa, exponent = f"{value:.3e}".split("e")
    return f"{mantissa}e{int(exponent)}"


def draw_scientific(draw, x, y, value, font, exponent_font, fill):
    match = re.fullmatch(r"([0-9.]+)e(-?[0-9]+)", value)
    if not match:
        draw.text((x, y), value, font=font, fill=fill)
        return
    base = f"{match.group(1)}×10"
    draw.text((x, y), base, font=font, fill=fill)
    base_width = draw.textlength(base, font=font)
    draw.text((x + base_width + 1, y - 7), match.group(2), font=exponent_font, fill=fill)


def draw_table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    output: Path,
    note: str,
    row_height: int = 72,
    highlight_rows: set[int] | None = None,
) -> None:
    highlight_rows = highlight_rows or set()
    header_height = 72
    note_height = 62
    width = sum(widths)
    height = header_height + row_height * len(rows) + note_height
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    header_font = ImageFont.truetype(str(FONT_BOLD), 32)
    body_font = ImageFont.truetype(str(FONT_REGULAR), 25)
    bold_font = ImageFont.truetype(str(FONT_BOLD), 25)
    exponent_font = ImageFont.truetype(str(FONT_REGULAR), 18)
    exponent_bold = ImageFont.truetype(str(FONT_BOLD), 18)
    note_font = ImageFont.truetype(str(FONT_REGULAR), 20)

    x = 0
    for header, cell_width in zip(headers, widths):
        draw.rectangle((x, 0, x + cell_width, header_height), fill=HEADER_RED, outline=GRID, width=2)
        draw.text((x + 12, 14), header, font=header_font, fill="white")
        x += cell_width

    y = header_height
    for index, row in enumerate(rows):
        fill = "#e6b8b8" if index in highlight_rows else (
            ROW_DARK if index % 2 == 0 else ROW_LIGHT
        )
        font = bold_font if index in highlight_rows else body_font
        exp_font = exponent_bold if index in highlight_rows else exponent_font
        x = 0
        for value, cell_width in zip(row, widths):
            draw.rectangle((x, y, x + cell_width, y + row_height), fill=fill, outline=GRID, width=2)
            text_y = y + (row_height - font.size) // 2 - 3
            if re.fullmatch(r"[0-9.]+e-?[0-9]+", value):
                draw_scientific(draw, x + 12, text_y, value, font, exp_font, TEXT)
            else:
                draw.text((x + 12, text_y), value, font=font, fill=TEXT)
            x += cell_width
        y += row_height

    draw.text((12, y + 15), note, font=note_font, fill="#404040")
    image.save(output)


def build_comparison(summary: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[int, float]] = {}
    metadata: dict[str, tuple[int, float, str]] = {}
    for row in summary:
        source = row["source_type"]
        distance = int(row["distance_from_tank_wall_m"])
        grouped.setdefault(source, {})[distance] = float(row["normE_V_per_m"])
        metadata[source] = (
            int(row["frequency_hz"]),
            float(row["source_voltage_rms_V"]),
            row["excitation_mode"],
        )

    comparison = []
    for source, values in grouped.items():
        frequency_hz, source_voltage, mode = metadata[source]
        comparison.append({
            "source_type": source,
            "source_label": SOURCE_LABELS[source],
            "excitation_mode": mode,
            "frequency_hz": frequency_hz,
            "frequency_label": frequency_label(frequency_hz),
            "source_voltage_rms_V": source_voltage,
            "field_2m_V_per_m": values[2],
            "field_3m_V_per_m": values[3],
            "field_4m_V_per_m": values[4],
            "ratio_3m_to_2m": values[3] / values[2],
            "ratio_4m_to_2m": values[4] / values[2],
        })
    comparison.sort(key=lambda row: int(row["frequency_hz"]))
    return comparison


def write_dict_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def render_main_table(comparison: list[dict[str, object]]) -> None:
    rows = []
    for row in comparison:
        source_voltage = float(row["source_voltage_rms_V"])
        voltage_label = f"{source_voltage:.1f} V" if source_voltage > 1 else "1 V归一化"
        rows.append([
            str(row["source_label"]),
            str(row["frequency_label"]),
            voltage_label,
            scientific(float(row["field_2m_V_per_m"])),
            scientific(float(row["field_3m_V_per_m"])),
            scientific(float(row["field_4m_V_per_m"])),
        ])
    highlight = {
        index for index, row in enumerate(comparison)
        if int(row["frequency_hz"]) in {30, 50, 100000}
    }
    draw_table(
        ["信号源", "频率", "输入条件", "2 m", "3 m", "4 m"],
        rows,
        [390, 175, 225, 265, 265, 265],
        OUTPUT / "minimal_electric_v13_source_table.png",
        "注：10 m空气域，场强单位V/m；高频为每1 V RMS共模单位传递，不代表实际共模电压。",
        row_height=70,
        highlight_rows=highlight,
    )


def render_voltage_scan(comparison: list[dict[str, object]]) -> None:
    row_100k = next(row for row in comparison if int(row["frequency_hz"]) == 100000)
    scan_rows = []
    output_rows = []
    for voltage in (1, 10, 30, 100):
        values = [float(row_100k[f"field_{distance}m_V_per_m"]) * voltage for distance in (2, 3, 4)]
        output_rows.append({
            "frequency_hz": 100000,
            "common_mode_voltage_rms_V": voltage,
            "field_2m_V_per_m": values[0],
            "field_3m_V_per_m": values[1],
            "field_4m_V_per_m": values[2],
        })
        scan_rows.append([
            "100 kHz共模灵敏度",
            f"{voltage} V RMS",
            scientific(values[0]),
            scientific(values[1]),
            scientific(values[2]),
        ])
    write_dict_csv(OUTPUT / "common_mode_100khz_voltage_scan.csv", output_rows)
    draw_table(
        ["工况", "等效共模电压", "2 m", "3 m", "4 m"],
        scan_rows,
        [410, 280, 280, 280, 280],
        OUTPUT / "common_mode_100khz_voltage_scan_table.png",
        "注：由1 V单位传递线性缩放；1/10/30/100 V为灵敏度档位，不是实测源电压。",
        row_height=78,
    )


def plot_frequency_transfer(comparison: list[dict[str, object]]) -> None:
    common = [row for row in comparison if row["excitation_mode"] == "normalized_common_mode"]
    font_manager.fontManager.addfont(str(FONT_REGULAR))
    font_name = font_manager.FontProperties(fname=str(FONT_REGULAR)).get_name()
    plt.rcParams["font.family"] = font_name
    plt.rcParams["axes.unicode_minus"] = False
    colors = {2: "#cf101d", 3: "#176b87", 4: "#2f7d32"}
    fig, ax = plt.subplots(figsize=(10.8, 6.2), dpi=180)
    frequencies = [int(row["frequency_hz"]) / 1000 for row in common]
    for distance in (2, 3, 4):
        fields = [float(row[f"field_{distance}m_V_per_m"]) for row in common]
        ax.plot(frequencies, fields, marker="o", linewidth=2.2, markersize=5.5,
                color=colors[distance], label=f"距桶壁 {distance} m")
    ax.axvspan(80, 150, color="#d8b11e", alpha=0.15, label="实测关注区 80–150 kHz")
    ax.set_xscale("log")
    ax.set_xlabel("共模激励频率 (kHz)")
    ax.set_ylabel("单位共模电压场强 (V/m per 1 V RMS)")
    ax.set_title("V13 电机电缆共模电场传递与距离衰减")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(OUTPUT / "common_mode_frequency_transfer.png", bbox_inches="tight")
    plt.close(fig)


def plot_horizontal_comparison(comparison: list[dict[str, object]]) -> None:
    font_manager.fontManager.addfont(str(FONT_REGULAR))
    font_name = font_manager.FontProperties(fname=str(FONT_REGULAR)).get_name()
    plt.rcParams["font.family"] = font_name
    labels = [str(row["frequency_label"]) for row in comparison]
    y = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(11.5, 8.2), dpi=180)
    offsets = (-0.23, 0, 0.23)
    colors = {2: "#cf101d", 3: "#176b87", 4: "#2f7d32"}
    for offset, distance in zip(offsets, (2, 3, 4)):
        values = [float(row[f"field_{distance}m_V_per_m"]) for row in comparison]
        ax.barh([value + offset for value in y], values, height=0.2,
                color=colors[distance], label=f"{distance} m")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("场强 (V/m；高频行为每1 V RMS共模输入)")
    ax.set_title("V13 2/3/4 m场强横向对比")
    ax.grid(True, axis="x", which="both", alpha=0.25)
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(OUTPUT / "minimal_electric_v13_horizontal_comparison.png", bbox_inches="tight")
    plt.close(fig)


def compare_v9_v13(comparison: list[dict[str, object]]) -> None:
    v9 = read_csv(V9_SUMMARY)
    v9_values = {
        (row["source_type"], int(row["distance_from_tank_wall_m"])):
            float(row["normE_V_per_m"])
        for row in v9
    }
    output_rows = []
    for frequency in (30, 50):
        v13 = next(row for row in comparison if int(row["frequency_hz"]) == frequency)
        for distance in (2, 3, 4):
            old = v9_values[(f"vfd_motor_cable_{frequency}hz", distance)]
            new = float(v13[f"field_{distance}m_V_per_m"])
            output_rows.append({
                "frequency_hz": frequency,
                "distance_m": distance,
                "v9_field_V_per_m": old,
                "v13_field_V_per_m": new,
                "v13_change_from_v9_percent": 100 * (new / old - 1),
            })
    write_dict_csv(OUTPUT / "v9_v13_fundamental_comparison.csv", output_rows)


def write_quality_checks(comparison: list[dict[str, object]]) -> None:
    checks = []
    for row in comparison:
        e2 = float(row["field_2m_V_per_m"])
        e3 = float(row["field_3m_V_per_m"])
        e4 = float(row["field_4m_V_per_m"])
        checks.append({
            "source_type": row["source_type"],
            "frequency_hz": row["frequency_hz"],
            "finite_positive": all(math.isfinite(value) and value > 0 for value in (e2, e3, e4)),
            "monotonic_distance_decay": e2 > e3 > e4,
            "ratio_3m_to_2m": e3 / e2,
            "ratio_4m_to_2m": e4 / e2,
        })
    write_dict_csv(OUTPUT / "minimal_electric_v13_quality_checks.csv", checks)


def compare_domain_radius(summary: list[dict[str, str]]) -> None:
    old_rows = read_csv(DOMAIN7P5_SUMMARY)
    old = {
        (row["source_type"], int(row["distance_from_tank_wall_m"])):
            float(row["normE_V_per_m"])
        for row in old_rows
    }
    detailed = []
    grouped: dict[str, list[float]] = {}
    frequencies: dict[str, int] = {}
    for row in summary:
        source = row["source_type"]
        distance = int(row["distance_from_tank_wall_m"])
        field_7p5 = old[(source, distance)]
        field_10 = float(row["normE_V_per_m"])
        change = 100 * (field_10 / field_7p5 - 1)
        grouped.setdefault(source, []).append(abs(change))
        frequencies[source] = int(row["frequency_hz"])
        detailed.append({
            "source_type": source,
            "frequency_hz": frequencies[source],
            "distance_m": distance,
            "field_domain_7p5m_V_per_m": field_7p5,
            "field_domain_10m_V_per_m": field_10,
            "change_7p5m_to_10m_percent": change,
            "absolute_change_percent": abs(change),
        })
    write_dict_csv(OUTPUT / "minimal_electric_v13_domain_sensitivity.csv", detailed)
    aggregate = [{
        "source_type": source,
        "frequency_hz": frequencies[source],
        "max_absolute_change_2m_3m_4m_percent": max(changes),
        "mean_absolute_change_2m_3m_4m_percent": sum(changes) / len(changes),
    } for source, changes in grouped.items()]
    aggregate.sort(key=lambda row: int(row["frequency_hz"]))
    write_dict_csv(OUTPUT / "minimal_electric_v13_domain_sensitivity_summary.csv", aggregate)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    phasor_rows = marker_rows("V13_PHASOR")
    summary_rows = marker_rows("V13_SUMMARY")
    if len(phasor_rows) != 216 or len(summary_rows) != 36:
        raise RuntimeError(
            f"Incomplete COMSOL output: {len(phasor_rows)} phasors, {len(summary_rows)} summaries"
        )
    write_csv(
        OUTPUT / "minimal_electric_v13_phasors.csv",
        ["case_index", "source_type", "excitation_mode", "frequency_hz",
         "source_voltage_rms_V", "distance_from_tank_wall_m", "quantity",
         "real", "imaginary", "magnitude"],
        phasor_rows,
    )
    write_csv(
        OUTPUT / "minimal_electric_v13_summary.csv",
        ["source_type", "excitation_mode", "frequency_hz", "source_voltage_rms_V",
         "distance_from_tank_wall_m", "normE_V_per_m", "sensor_axis_E_V_per_m"],
        summary_rows,
    )
    summary = read_csv(OUTPUT / "minimal_electric_v13_summary.csv")
    comparison = build_comparison(summary)
    write_dict_csv(OUTPUT / "minimal_electric_v13_source_comparison.csv", comparison)
    render_main_table(comparison)
    render_voltage_scan(comparison)
    plot_frequency_transfer(comparison)
    plot_horizontal_comparison(comparison)
    compare_v9_v13(comparison)
    write_quality_checks(comparison)
    compare_domain_radius(summary)
    print(f"phasors={len(phasor_rows)}, summaries={len(summary_rows)}, cases={len(comparison)}")
    for output in sorted(OUTPUT.iterdir()):
        print(output.name)


if __name__ == "__main__":
    main()
