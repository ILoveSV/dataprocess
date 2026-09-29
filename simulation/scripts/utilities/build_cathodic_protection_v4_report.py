from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[2]
INTERNAL = ROOT / "results/cathodic_protection_tank_3d_current_sweep_v3"
EXTERNAL = ROOT / "results/cathodic_protection_external_field_v4"
V13 = ROOT / "results/minimal_electric_v13/minimal_electric_v13_source_comparison.csv"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def numeric_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if row and not row[0].lstrip().startswith("%"):
                rows.append(row)
    return rows


def setup_font() -> None:
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(FONT)).get_name()
    plt.rcParams["axes.unicode_minus"] = False


def main() -> None:
    sweep_rows = numeric_rows(INTERNAL / "current_voltage_comparison.csv")
    currents = [float(row[0]) for row in sweep_rows]
    measured_voltage = [float(row[2]) for row in sweep_rows]
    comsol_voltage = [float(row[3]) for row in sweep_rows]
    comsol_resistance = [float(row[5]) for row in sweep_rows]
    measured_resistance = [float(row[6]) for row in sweep_rows]

    transfer = {}
    for distance in (2, 3, 4):
        row = numeric_rows(EXTERNAL / f"unit_transfer_{distance}m.csv")[0]
        transfer[distance] = float(row[-1])

    scaled_rows: list[dict[str, float]] = []
    for current, voltage in zip(currents, measured_voltage):
        scaled_rows.append({
            "current_A": current,
            "measured_voltage_V": voltage,
            "field_2m_V_per_m": transfer[2] * voltage,
            "field_3m_V_per_m": transfer[3] * voltage,
            "field_4m_V_per_m": transfer[4] * voltage,
        })
    with (EXTERNAL / "measured_voltage_scaled_field.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scaled_rows[0]))
        writer.writeheader()
        writer.writerows(scaled_rows)

    with V13.open("r", encoding="utf-8-sig", newline="") as handle:
        v13_rows = list(csv.DictReader(handle))
    existing = {
        row["source_type"]: float(row["field_2m_V_per_m"])
        for row in v13_rows
        if row["source_type"] in {"motor_differential_30hz", "motor_differential_50hz"}
    }
    comparison = [
        {
            "source": "阴极保护 0.01 A",
            "frequency": "DC",
            "input": "0.20 V实测差模",
            "field_2m_V_per_m": scaled_rows[0]["field_2m_V_per_m"],
        },
        {
            "source": "阴极保护 0.05 A",
            "frequency": "DC",
            "input": "0.50 V实测差模",
            "field_2m_V_per_m": scaled_rows[1]["field_2m_V_per_m"],
        },
        {
            "source": "阴极保护 0.10 A",
            "frequency": "DC",
            "input": "0.70 V实测差模",
            "field_2m_V_per_m": scaled_rows[2]["field_2m_V_per_m"],
        },
        {
            "source": "阴极保护 0.20 A",
            "frequency": "DC",
            "input": "1.20 V实测差模",
            "field_2m_V_per_m": scaled_rows[3]["field_2m_V_per_m"],
        },
        {
            "source": "V13电机电缆差模",
            "frequency": "30 Hz",
            "input": "131.6 V RMS",
            "field_2m_V_per_m": existing["motor_differential_30hz"],
        },
        {
            "source": "V13电机电缆差模",
            "frequency": "50 Hz",
            "input": "219.4 V RMS",
            "field_2m_V_per_m": existing["motor_differential_50hz"],
        },
    ]
    with (EXTERNAL / "cathodic_protection_vs_v13_2m.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    inferred = []
    sigma_nominal = 0.05
    for current, r_model, r_measured in zip(currents, comsol_resistance, measured_resistance):
        inferred.append({
            "current_A": current,
            "comsol_resistance_ohm": r_model,
            "measured_apparent_resistance_ohm": r_measured,
            "conductivity_required_if_geometry_fixed_S_per_m": sigma_nominal * r_model / r_measured,
            "conductivity_required_if_geometry_fixed_uS_per_cm":
                sigma_nominal * r_model / r_measured * 10000,
        })
    with (INTERNAL / "effective_conductivity_diagnostic.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(inferred[0]))
        writer.writeheader()
        writer.writerows(inferred)

    setup_font()
    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=180)
    ax.plot(currents, measured_voltage, "o-", linewidth=2.2, label="电源稳定读数")
    ax.plot(currents, comsol_voltage, "s-", linewidth=2.2, label="COMSOL纯欧姆水体")
    ax.set_xlabel("恒流设定 (A)")
    ax.set_ylabel("端电压 (V)")
    ax.set_title("阴极保护四档恒流：实测与纯欧姆模型")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(INTERNAL / "measured_vs_comsol_voltage.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.8, 5.8), dpi=180)
    labels = [f"{row['current_A']:.2f} A" for row in scaled_rows]
    for distance, color in ((2, "#cf101d"), (3, "#176b87"), (4, "#2f7d32")):
        ax.plot(
            labels,
            [row[f"field_{distance}m_V_per_m"] for row in scaled_rows],
            marker="o",
            linewidth=2.2,
            color=color,
            label=f"距桶壁{distance} m",
        )
    ax.set_yscale("log")
    ax.set_xlabel("阴极保护恒流工况")
    ax.set_ylabel("按实测端电压换算的场强 (V/m)")
    ax.set_title("浮地阴极保护源的外部电场与距离衰减")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(EXTERNAL / "cathodic_protection_field_2m_3m_4m.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.8, 6.0), dpi=180)
    plot_labels = [f"{row['source']}\n{row['frequency']}" for row in comparison]
    values = [float(row["field_2m_V_per_m"]) for row in comparison]
    colors = ["#176b87"] * 4 + ["#cf101d", "#cf101d"]
    bars = ax.bar(plot_labels, values, color=colors)
    ax.set_yscale("log")
    ax.set_ylabel("距桶壁2 m场强 (V/m)")
    ax.set_title("阴极保护独立源与V13可信电机电缆源对比")
    ax.grid(True, axis="y", which="both", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.08, f"{value:.2e}",
                ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(EXTERNAL / "cathodic_protection_vs_v13_2m.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
