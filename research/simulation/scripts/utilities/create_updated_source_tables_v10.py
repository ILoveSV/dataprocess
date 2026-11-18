"""Create PPT-ready V10 source tables in the style of the previous tables."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUTPUT = RESULTS / "pulsation_v10"
V9_SUMMARY = RESULTS / "doorway_environment_v9_summary.csv"
V10_SUMMARY = OUTPUT / "external_field_case_summary.csv"

FONT_REGULAR = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
HEADER_RED = "#cf101d"
ROW_DARK = "#ebcccc"
ROW_LIGHT = "#f4e5e5"
GRID = "#ffffff"
TEXT = "#090909"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def scientific(value: float) -> str:
    mantissa, exponent = f"{value:.3e}".split("e")
    return f"{mantissa}e{int(exponent)}"


def source_values() -> dict[tuple[str, int], float]:
    values: dict[tuple[str, int], float] = {}
    for row in read_csv(V9_SUMMARY):
        values[(row["source_type"], int(row["distance_from_tank_wall_m"]))] = float(
            row["normE_V_per_m"]
        )
    return values


def water_values() -> dict[tuple[int, int], float]:
    values: dict[tuple[int, int], float] = {}
    for row in read_csv(V10_SUMMARY):
        if abs(float(row["velocity_amplitude_A"]) - 0.05) > 1e-12:
            continue
        key = (int(row["operating_mode_hz"]), int(row["distance_from_tank_wall_m"]))
        values[key] = float(row["total_10_harmonic_vector_field_rms_v_per_m"])
    return values


def draw_table(
    rows: list[list[str]],
    output: Path,
    bold_rows: set[int],
    note: str,
    row_heights: list[int] | None = None,
    headers: list[str] | None = None,
) -> None:
    headers = headers or ["信号源", "对应频率", "2 m", "3 m", "4 m"]
    widths = [410, 350, 340, 340, 340] if len(headers) == 5 else [260, 170, 260, 340, 340, 340]
    header_height = 72
    row_heights = row_heights or [82] * len(rows)
    note_height = 58
    width = sum(widths)
    height = header_height + sum(row_heights) + note_height
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_header = ImageFont.truetype(FONT_BOLD, 37)
    font_body = ImageFont.truetype(FONT_REGULAR, 31)
    font_body_bold = ImageFont.truetype(FONT_BOLD, 31)
    font_exponent = ImageFont.truetype(FONT_REGULAR, 21)
    font_exponent_bold = ImageFont.truetype(FONT_BOLD, 21)
    font_note = ImageFont.truetype(FONT_REGULAR, 22)

    x = 0
    for column, (label, cell_width) in enumerate(zip(headers, widths)):
        draw.rectangle((x, 0, x + cell_width, header_height), fill=HEADER_RED, outline=GRID, width=2)
        draw.text((x + 15, 12), label, font=font_header, fill="white")
        x += cell_width

    y = header_height
    for row_index, (row, row_height) in enumerate(zip(rows, row_heights)):
        fill = ROW_DARK if row_index % 2 == 0 else ROW_LIGHT
        font = font_body_bold if row_index in bold_rows else font_body
        x = 0
        for value, cell_width in zip(row, widths):
            draw.rectangle((x, y, x + cell_width, y + row_height), fill=fill, outline=GRID, width=2)
            match = re.fullmatch(r"([0-9.]+)e(-?[0-9]+)", value)
            if match:
                base = f"{match.group(1)}×10"
                text_y = y + (row_height - font.size) // 2 - 2
                draw.text((x + 15, text_y), base, font=font, fill=TEXT)
                base_width = draw.textlength(base, font=font)
                exponent_font = font_exponent_bold if row_index in bold_rows else font_exponent
                draw.text((x + 15 + base_width + 1, text_y - 7), match.group(2), font=exponent_font, fill=TEXT)
                x += cell_width
                continue
            lines = value.split("\n")
            line_height = font.size + 8
            text_height = len(lines) * line_height - 8
            text_y = y + max(6, (row_height - text_height) // 2)
            for line in lines:
                draw.text((x + 15, text_y), line, font=font, fill=TEXT)
                text_y += line_height
            x += cell_width
        y += row_height

    draw.rectangle((0, y, width, height), fill="white")
    draw.text((12, y + 12), note, font=font_note, fill="#404040")
    image.save(output)


def create_source_table(mode: int, source: dict[tuple[str, int], float], water: dict[tuple[int, int], float]) -> None:
    pump = f"pump_chassis_{mode}hz"
    cable = f"vfd_motor_cable_{mode}hz"
    combined = f"combined_{mode}hz"
    rows = [
        ["水流脉动（A=5%对比点）", "0.3226 Hz"]
        + [scientific(water[(mode, distance)]) for distance in (2, 3, 4)],
        ["泵壳共模，1 V基准", f"{mode} Hz"]
        + [scientific(source[(pump, distance)]) for distance in (2, 3, 4)],
        ["变频器至电机电缆\n基波", f"{mode} Hz"]
        + [scientific(source[(cable, distance)]) for distance in (2, 3, 4)],
    ]
    if mode == 50:
        rows.append(
            ["墙内380 V供电", "50 Hz"]
            + [scientific(source[("wall_supply_50hz", distance)]) for distance in (2, 3, 4)]
        )
    rows.append(
        [f"{mode} Hz电气低频组合场\n（不含水流谱线）", f"{mode} Hz"]
        + [scientific(source[(combined, distance)]) for distance in (2, 3, 4)]
    )
    if mode == 30:
        rows.append(
            ["墙内380 V供电", "50 Hz"]
            + [scientific(source[("wall_supply_50hz", distance)]) for distance in (2, 3, 4)]
        )
    for tag, label, frequency in (
        ("vfd_pwm_4khz", "VFD共模载波", "4 kHz"),
        ("vfd_pwm_8khz", "VFD二次载波", "8 kHz"),
        ("vfd_pwm_12khz", "VFD三次载波", "12 kHz"),
    ):
        rows.append(
            [label, frequency] + [scientific(source[(tag, distance)]) for distance in (2, 3, 4)]
        )

    combined_index = 4 if mode == 50 else 3
    row_heights = [88, 88, 108, 88, 112, 88, 88, 88] if mode == 50 else [88, 88, 108, 112, 88, 88, 88, 88]
    draw_table(
        rows,
        OUTPUT / f"updated_source_table_{mode}hz_A005.png",
        {combined_index},
        "注：场强单位为 V/m；0.3226 Hz 水流谱线与 30/50 Hz 电气相量分开报告。",
        row_heights,
    )


def create_scan_table() -> None:
    rows: list[list[str]] = []
    for row in read_csv(V10_SUMMARY):
        if int(row["distance_from_tank_wall_m"]) != 2:
            continue
        mode = int(row["operating_mode_hz"])
        amplitude = float(row["velocity_amplitude_A"])
        same_case = [
            item for item in read_csv(V10_SUMMARY)
            if int(item["operating_mode_hz"]) == mode
            and abs(float(item["velocity_amplitude_A"]) - amplitude) < 1e-12
        ]
        same_case.sort(key=lambda item: int(item["distance_from_tank_wall_m"]))
        rows.append(
            [
                f"{mode} Hz工况",
                f"{amplitude * 100:.0f}%",
                "0.3226 Hz",
                *[
                    scientific(float(item["total_10_harmonic_vector_field_rms_v_per_m"]))
                    for item in same_case
                ],
            ]
        )
    rows.sort(key=lambda row: (int(row[0].split()[0]), float(row[1].rstrip("%"))))
    draw_table(
        rows,
        OUTPUT / "water_pulsation_parameter_scan_table.png",
        set(),
        "注：A 为入口速度相对平均速度的调制幅度；场强单位为 V/m。",
        [66] * len(rows),
        ["运行工况", "A", "水流频率", "2 m", "3 m", "4 m"],
    )


def main() -> None:
    source = source_values()
    water = water_values()
    create_source_table(30, source, water)
    create_source_table(50, source, water)
    create_scan_table()
    for name in (
        "updated_source_table_30hz_A005.png",
        "updated_source_table_50hz_A005.png",
        "water_pulsation_parameter_scan_table.png",
    ):
        print(OUTPUT / name)


if __name__ == "__main__":
    main()
