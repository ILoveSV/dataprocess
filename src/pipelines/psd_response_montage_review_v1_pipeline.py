import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


CHANNELS = [f"channel{i}" for i in range(1, 13)]
WINDOWS = [(start, start + 20_000) for start in range(0, 200_000, 20_000)]
WINDOW_LABELS = {f"{low:.1f}_{high:.1f}": f"{int(low/1000):03d}_{int(high/1000):03d}k" for low, high in WINDOWS}
ACTIVE_CONDITIONS = ["30Hz_minus_0Hz", "50Hz_minus_0Hz"]
DISTANCE_SETS = ["2m3m", "2m3m5m"]
MASK_NAME = "none_per_channel_review"


def main(argv=None):
    parser = argparse.ArgumentParser(description="PSD response montage review figures v1.")
    parser.add_argument(
        "--per-channel-output",
        default="analysis_out/background_subtracted_psd_response_consistency_per_channel_first39_v1",
        help="Existing per-channel PSD response output directory.",
    )
    parser.add_argument("--output", default="analysis_out/psd_response_montage_review_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.per_channel_output)
    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "montage_by_window").mkdir(parents=True, exist_ok=True)
    (output / "montage_by_channel").mkdir(parents=True, exist_ok=True)

    index_path = source / "psd_response_review_figure_index_per_channel_v1.csv"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing per-channel figure index: {index_path}")
    index = pd.read_csv(index_path)
    index["resolved_plot_path"] = index["plot_path"].map(resolve_plot_path)
    rows = []
    rows.extend(make_by_window_montages(index, output / "montage_by_window"))
    rows.extend(make_by_channel_montages(index, output / "montage_by_channel"))
    out_index = pd.DataFrame(rows)
    out_index.to_csv(output / "figure_index_v1.csv", index=False, encoding="utf-8-sig")

    write_json(output / "psd_response_montage_review_config_v1.json", {
        "per_channel_output": str(source),
        "source_index": str(index_path),
        "output": str(output),
        "montage_types": ["by_window", "by_channel"],
        "active_conditions": ACTIVE_CONDITIONS,
        "distance_sets": DISTANCE_SETS,
        "frequency_windows_hz": WINDOWS,
        "mask_name": MASK_NAME,
        "source_scope": "Uses existing per-channel PSD response PNG files; no FFT/TDMS/background recomputation.",
    })
    write_report(output, out_index)
    print(f"PSD response montage review output: {output}")
    print(f"Montage figures: {len(out_index)}")


def make_by_window_montages(index, out_dir):
    rows = []
    for active in ACTIVE_CONDITIONS:
        for distance_set in DISTANCE_SETS:
            for low, high in WINDOWS:
                window_key = f"{float(low):.1f}_{float(high):.1f}"
                selected = []
                for channel in CHANNELS:
                    row = pick_row(index, channel, active, distance_set, low, high)
                    if row is not None:
                        selected.append((channel, Path(row["resolved_plot_path"])))
                if not selected:
                    continue
                freq_label = f"{int(low/1000)}-{int(high/1000)} kHz"
                title = f"PSD response montage | {active} | {distance_set} | {freq_label} | mask: {MASK_NAME}"
                out_path = out_dir / active / distance_set
                out_path.mkdir(parents=True, exist_ok=True)
                file_path = out_path / f"montage_by_window_{active}_{distance_set}_{WINDOW_LABELS[window_key]}.png"
                stitch_grid(
                    selected,
                    file_path,
                    title=title,
                    columns=4,
                    tile_width=760,
                    tile_height=365,
                )
                rows.append({
                    "plot_path": str(file_path),
                    "active_condition": active,
                    "distance_set": distance_set,
                    "frequency_window": freq_label,
                    "montage_type": "by_window",
                    "channels_included": ",".join(channel for channel, _ in selected),
                    "mask_name": MASK_NAME,
                })
    return rows


def make_by_channel_montages(index, out_dir):
    rows = []
    for channel in CHANNELS:
        for active in ACTIVE_CONDITIONS:
            for distance_set in DISTANCE_SETS:
                selected = []
                for low, high in WINDOWS:
                    row = pick_row(index, channel, active, distance_set, low, high)
                    if row is not None:
                        selected.append((f"{int(low/1000)}-{int(high/1000)} kHz", Path(row["resolved_plot_path"])))
                if not selected:
                    continue
                title = f"PSD response montage | {channel}{channel_label_suffix(channel)} | {active} | {distance_set} | mask: {MASK_NAME}"
                out_path = out_dir / channel / active
                out_path.mkdir(parents=True, exist_ok=True)
                file_path = out_path / f"montage_by_channel_{channel}_{active}_{distance_set}.png"
                stitch_grid(
                    selected,
                    file_path,
                    title=title,
                    columns=5,
                    tile_width=620,
                    tile_height=298,
                )
                rows.append({
                    "plot_path": str(file_path),
                    "active_condition": active,
                    "distance_set": distance_set,
                    "frequency_window": "0-200 kHz split into 10 windows",
                    "montage_type": "by_channel",
                    "channels_included": channel,
                    "mask_name": MASK_NAME,
                })
    return rows


def stitch_grid(items, output_path, title, columns, tile_width, tile_height):
    font = load_font(24)
    small_font = load_font(18)
    label_font = load_font(22)
    rows = (len(items) + columns - 1) // columns
    header_h = 58
    label_h = 30
    margin = 16
    gap = 10
    canvas_w = margin * 2 + columns * tile_width + (columns - 1) * gap
    canvas_h = header_h + margin + rows * (tile_height + label_h) + (rows - 1) * gap + margin
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 14), title, fill="black", font=font)
    draw.text((margin, 42), "Source: existing per-channel first39 PSD response PNGs; montage only, no new algorithm.", fill="#555555", font=small_font)

    for idx, (label, path) in enumerate(items):
        row = idx // columns
        col = idx % columns
        x = margin + col * (tile_width + gap)
        y = header_h + margin + row * (tile_height + label_h + gap)
        draw.text((x, y), label_with_status(label), fill=status_color(label), font=label_font)
        img_y = y + label_h
        if path.exists():
            with Image.open(path) as img:
                img = img.convert("RGB")
                img.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
                tile = Image.new("RGB", (tile_width, tile_height), "white")
                tile.paste(img, ((tile_width - img.width) // 2, (tile_height - img.height) // 2))
                canvas.paste(tile, (x, img_y))
        else:
            draw.rectangle((x, img_y, x + tile_width, img_y + tile_height), outline="#c0c0c0", width=2)
            draw.text((x + 20, img_y + 20), f"Missing source plot:\n{path}", fill="#a00000", font=small_font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def pick_row(index, channel, active, distance_set, low, high):
    match = index[
        (index["channel"].astype(str) == channel)
        & (index["active_condition"].astype(str) == active)
        & (index["distance_set"].astype(str) == distance_set)
        & (pd.to_numeric(index["freq_window_low_hz"], errors="coerce") == float(low))
        & (pd.to_numeric(index["freq_window_high_hz"], errors="coerce") == float(high))
    ]
    if match.empty:
        return None
    return match.iloc[0]


def resolve_plot_path(value):
    path = Path(str(value))
    if path.exists():
        return str(path)
    joined = Path.cwd() / path
    return str(joined)


def channel_label_suffix(channel):
    if channel == "channel9":
        return " BAD"
    if channel == "channel5":
        return " SUSPECT"
    return ""


def label_with_status(label):
    if str(label) == "channel9":
        return "channel9 BAD"
    if str(label) == "channel5":
        return "channel5 SUSPECT"
    return str(label)


def status_color(label):
    if str(label) == "channel9":
        return "#a00000"
    if str(label) == "channel5":
        return "#b06000"
    return "black"


def load_font(size):
    for font_name in ["arial.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def write_report(output, index):
    report = Path("docs/PSD_RESPONSE_MONTAGE_REVIEW_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    by_type = index["montage_type"].value_counts().to_dict() if not index.empty else {}
    lines = [
        "# PSD Response Montage Review v1",
        "",
        "## Purpose",
        "",
        "This review artifact rearranges the latest per-channel first39 background-subtracted PSD response PNGs into larger montage figures for manual inspection of repeated response frequencies.",
        "",
        "## Scope",
        "",
        "- Active conditions: 30Hz_minus_0Hz and 50Hz_minus_0Hz.",
        "- Distance sets: 2m3m and 2m3m5m.",
        "- Frequency coverage: 0-200 kHz split into 10 fixed 20 kHz windows.",
        "- Montage types: by_window and by_channel.",
        "- Source: existing per-channel PSD response figures; no TDMS, FFT, background contrast, peak detection, ML, or new science conclusion.",
        "",
        "## Outputs",
        "",
        f"- Output directory: `{output}`",
        f"- Montage count by type: {by_type}",
        "- `montage_by_window/`: one figure per active condition, distance set, and 20 kHz window; each figure contains all 12 channels.",
        "- `montage_by_channel/`: one figure per channel, active condition, and distance set; each figure contains all 10 frequency windows.",
        "- `figure_index_v1.csv`: lookup table for all montage figures.",
        "",
        "## Channel Notes",
        "",
        "- channel9 is marked BAD according to current pilot QC context.",
        "- channel5 is marked SUSPECT according to current pilot QC context.",
        "- These labels are review annotations, not permanent channel rules.",
        "",
        "## Suggested Manual Review Order",
        "",
        "- Start with `montage_by_window` for 40-60 kHz, 120-140 kHz, 160-180 kHz, and 180-200 kHz.",
        "- Compare 2m3m first, then check whether the same structure remains in 2m3m5m.",
        "- Use `montage_by_channel` after spotting a candidate frequency band to inspect one channel across all windows.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
