"""Publication-style external-field audit figures from preserved COMSOL tables.

No solver or source-data changes. Re-run after summarize_external_20260915.py.
The optional gap figure is emitted only when all six balanced gap cases exist.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/thesis_followup_20260915/external"
OUT = ROOT / "results/thesis_followup_20260915/figures"
OUT.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, GREEN = "#2166AC", "#D55E00", "#27805B"
INK, MUTED, GRID = "#202B35", "#566470", "#DDE3E8"
W, H = 960, 640
FILES = []


def label(c, x, y, value, size=10, color=INK, align="left", bold=False):
    c.setFillColor(HexColor(color))
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    method = {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align]
    method(x, y, str(value))


def start(name, title, subtitle):
    path = OUT / (name + ".pdf")
    c = canvas.Canvas(str(path), pagesize=(W, H))
    c.setTitle(title)
    c.setAuthor("Research numerical audit")
    label(c, 40, H - 38, title, 20, bold=True)
    label(c, 40, H - 61, subtitle, 10, MUTED)
    return c, path


def finish(c, path, footnote):
    c.setStrokeColor(HexColor(GRID))
    c.setLineWidth(0.6)
    c.line(40, 54, W - 40, 54)
    label(c, 40, 36, footnote, 9, MUTED)
    label(c, 40, 20, "Source: preserved COMSOL exports; 0.001 Hz scenario. Numerical sensitivity is not experimental validation.", 8, MUTED)
    c.showPage()
    c.save()
    doc = pdfium.PdfDocument(str(path))
    page = doc[0]
    bitmap = page.render(scale=1.8)
    bitmap.to_pil().save(path.with_suffix(".png"))
    bitmap.close()
    page.close()
    doc.close()
    FILES.extend([path.name, path.with_suffix(".png").name])


def legend(c, x, y, items):
    for title, color, dash in items:
        c.setStrokeColor(HexColor(color))
        c.setLineWidth(1.8)
        c.setDash([4, 3] if dash else [])
        c.line(x, y + 3, x + 24, y + 3)
        c.setDash([])
        label(c, x + 31, y, title, 10)
        x += 31 + c.stringWidth(title, "Helvetica", 10) + 25


def axes(c, box, xlim, ylim, xticks, yticks=None, yfmt=None):
    x, y, w, h = box
    sx = lambda v: x + (v - xlim[0]) * w / (xlim[1] - xlim[0])
    sy = lambda v: y + (v - ylim[0]) * h / (ylim[1] - ylim[0])
    if yticks is None:
        yticks = np.linspace(ylim[0], ylim[1], 5)
    yfmt = yfmt or (lambda v: f"{v:g}")
    c.setLineWidth(0.55)
    c.setDash([])
    for v in yticks:
        if ylim[0] - 1e-12 <= v <= ylim[1] + 1e-12:
            c.setStrokeColor(HexColor(GRID))
            c.line(x, sy(v), x + w, sy(v))
            label(c, x - 8, sy(v) - 3, yfmt(v), 8, MUTED, "right")
    for v, title in xticks:
        label(c, sx(v), y - 17, title, 9, MUTED, "center")
    c.setStrokeColor(HexColor(INK))
    c.line(x, y, x + w, y)
    c.line(x, y, x, y + h)
    return sx, sy


def line(c, sx, sy, xs, ys, color, dash=False):
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(1.8)
    c.setDash([4, 3] if dash else [])
    path = c.beginPath()
    path.moveTo(sx(xs[0]), sy(ys[0]))
    for x, y in zip(xs[1:], ys[1:]):
        path.lineTo(sx(x), sy(y))
    c.drawPath(path)
    c.setDash([])
    c.setFillColor(HexColor(color))
    for x, y in zip(xs, ys):
        c.circle(sx(x), sy(y), 2.8, fill=1, stroke=0)


def reference(c, sx, sy, xlim, value, color="#8E969E"):
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(0.8)
    c.setDash([3, 3])
    c.line(sx(xlim[0]), sy(value), sx(xlim[1]), sy(value))
    c.setDash([])


def bounds(values, fraction=0.13, zero=False):
    values = np.asarray(values, dtype=float)
    lo, hi = float(values.min()), float(values.max())
    if zero:
        return 0, hi * (1 + fraction)
    pad = max((hi - lo) * fraction, abs(hi) * 0.008, 1e-12)
    return lo - pad, hi + pad


def read():
    transfers = pd.read_csv(DATA / "all_transfers.csv")
    comparisons = pd.read_csv(DATA / "comparisons.csv")
    transfers = transfers[np.isclose(transfers.frequency_hz, 0.001, rtol=0, atol=1e-12)].copy()
    assert not transfers.duplicated(["case", "distance_m"]).any()
    assert np.isfinite(transfers.norm_e_v_m_per_v).all()
    return transfers.set_index(["case", "distance_m"]), comparisons


D, COMP = read()


def value(case, distance):
    return float(D.loc[(case, distance), "norm_e_v_m_per_v"])


def comparison(a, b, distance, field="norm_relative_change"):
    row = COMP[COMP.reference.eq(a) & COMP.candidate.eq(b) & COMP.distance_m.eq(distance)]
    assert len(row) == 1, (a, b, distance)
    return float(row.iloc[0][field]) * 100


def present(case):
    return all((case, d) in D.index for d in [2, 3, 4])


def local_mesh():
    cases = ["local_h100", "local_h075", "local_h050"]
    assert all(present(k + s) for k in cases for s in ["", "_ppr"])
    c, path = start("external_local_mesh_convergence", "Local observation-mesh convergence",
                    "R = 10 m, H = 3 m; gap = 20 mm. Same model; raw derivatives and recovered derivatives are shown separately.")
    legend(c, 40, 549, [("Raw field derivative", BLUE, False), ("pprint recovered derivative", ORANGE, False)])
    label(c, 40, 522, "A   Field norm |E| [V/m per 1 V differential drive]", 12, bold=True)
    cols = [91, 393, 695]
    for j, distance in enumerate([2, 3, 4]):
        x = cols[j]
        raw = [value(k, distance) for k in cases]
        recovered = [value(k + "_ppr", distance) for k in cases]
        label(c, x + 103, 496, f"Observation distance {distance} m", 11, align="center", bold=True)
        sx, sy = axes(c, (x, 332, 218, 150), (-0.12, 2.12), bounds(raw + recovered),
                      [(0, "100"), (1, "75"), (2, "50")], yfmt=lambda v: f"{v:.2e}")
        line(c, sx, sy, [0, 1, 2], raw, BLUE)
        line(c, sx, sy, [0, 1, 2], recovered, ORANGE)
        label(c, x + 109, 296, "Local maximum element size [mm]", 9, MUTED, "center")
    label(c, 40, 268, "B   Change in field norm between adjacent meshes [%]", 12, bold=True)
    raw_delta = [comparison(cases[i], cases[i + 1], d) for d in [2, 3, 4] for i in range(2)]
    max_change = max(3.0, np.ceil(max(np.abs(raw_delta))))
    for j, distance in enumerate([2, 3, 4]):
        x = cols[j]
        sx, sy = axes(c, (x, 120, 218, 128), (-0.5, 1.5), (-max_change, max_change),
                      [(0, "100 to 75 mm"), (1, "75 to 50 mm")], yfmt=lambda v: f"{v:g}")
        reference(c, sx, sy, (-0.5, 1.5), 2)
        reference(c, sx, sy, (-0.5, 1.5), -2)
        for i in range(2):
            for shift, suffix, color in [(-10, "", BLUE), (10, "_ppr", ORANGE)]:
                delta = comparison(cases[i] + suffix, cases[i + 1] + suffix, distance)
                c.setFillColor(HexColor(color))
                y0, y1 = sorted([sy(0), sy(delta)])
                c.rect(sx(i) + shift - 6, y0, 12, max(y1 - y0, 0.6), stroke=0, fill=1)
                label(c, sx(i) + shift, sy(delta) + (5 if delta >= 0 else -12), f"{delta:+.2f}", 8, color, "center")
        vector = comparison(cases[-2] + "_ppr", cases[-1] + "_ppr", distance, "vector_relative_difference")
        label(c, x + 109, 78, f"Recovered final vector difference: {vector:.2f}%", 9, MUTED, "center")
    finish(c, path, "Dashed: +/-2% reference. Relative norm change = 100 x (candidate/reference - 1); vector difference includes complex components.")


def domain():
    specs = [("local_h050", "10 / 3"), ("local_r15_h6", "15 / 6"),
             ("local_r20_h9", "20 / 9"), ("local_r30_h15", "30 / 15"), ("local_r40_h21", "40 / 21")]
    specs = [(k + "_ppr", name) for k, name in specs if present(k + "_ppr")]
    assert len(specs) >= 2
    c, path = start("external_domain_convergence", "Outer-domain sensitivity of recovered fields",
                    "Local maximum element size = 50 mm; gap = 20 mm. R and H are the outer air-cylinder radius and height.")
    label(c, 40, 548, "A   Field norm |E| [V/m per 1 V differential drive]", 12, bold=True)
    cols = [91, 393, 695]
    xs = np.arange(len(specs))
    for j, distance in enumerate([2, 3, 4]):
        x = cols[j]
        values = [value(k, distance) for k, _ in specs]
        label(c, x + 109, 517, f"Observation distance {distance} m", 11, align="center", bold=True)
        sx, sy = axes(c, (x, 347, 218, 150), (-.12, len(specs) - .88), bounds(values),
                      list(zip(xs, [n for _, n in specs])), yfmt=lambda v: f"{v:.2e}")
        line(c, sx, sy, xs, values, ORANGE)
        label(c, x + 109, 311, "Outer radius / height [m]", 9, MUTED, "center")
    label(c, 40, 284, "B   Relative difference from the preceding domain [%]", 12, bold=True)
    legend(c, 40, 258, [("Field norm change (signed)", ORANGE, False), ("Complex field-vector difference", BLUE, True)])
    vals = [comparison(specs[i][0], specs[i + 1][0], d, field)
            for d in [2, 3, 4] for i in range(len(specs) - 1)
            for field in ["norm_relative_change", "vector_relative_difference"]]
    limit = max(6, np.ceil(max(np.abs(vals)) / 5) * 5)
    for j, distance in enumerate([2, 3, 4]):
        x = cols[j]
        dx = np.arange(len(specs) - 1)
        sx, sy = axes(c, (x, 107, 218, 124), (-.15, len(dx) - .85), (-limit, limit),
                      list(zip(dx, [n for _, n in specs[1:]])), yfmt=lambda v: f"{v:g}")
        for v in [-5, 5]:
            reference(c, sx, sy, (-.15, len(dx) - .85), v)
        for field, color, dash in [("norm_relative_change", ORANGE, False), ("vector_relative_difference", BLUE, True)]:
            deltas = [comparison(specs[i][0], specs[i + 1][0], distance, field) for i in dx]
            line(c, sx, sy, dx, deltas, color, dash)
        last = comparison(specs[-2][0], specs[-1][0], distance)
        vector = comparison(specs[-2][0], specs[-1][0], distance, "vector_relative_difference")
        label(c, x + 109, 71, f"Last step: norm {last:+.2f}%; vector {vector:.2f}%", 9, MUTED, "center")
    finish(c, path, "Dashed horizontal lines: +/-5% reference. Bottom x labels identify the candidate domain; the reference is its preceding domain.")


def gap_boundary():
    gaps = [10, 20, 50, 100, 200, 300]
    gx = np.log10(gaps)
    xlim = (gx[0] - .035, gx[-1] + .035)
    cases = [f"gap_g{g:03d}_ppr" for g in gaps]
    if not all(present(k) for k in cases):
        print("Gap/boundary figure skipped: six complete balanced gap cases are not yet available.")
        return
    c, path = start("external_gap_and_boundary", "Electrode-gap and source-boundary scenarios",
                    "Recovered fields; balanced drive = +0.5 / -0.5 V; pair centre fixed at +55 mm. Each result is a model scenario.")
    colors = {2: BLUE, 3: ORANGE, 4: GREEN}
    legend(c, 40, 548, [(f"Distance {d} m", colors[d], False) for d in [2, 3, 4]])
    label(c, 85, 514, "A   Field norm [V/m per 1 V]", 12, bold=True)
    label(c, 542, 514, "B   Gain relative to 10 mm gap [ratio]", 12, bold=True)
    values = [value(k, d) for d in [2, 3, 4] for k in cases]
    ratios = [value(k, d) / value(cases[0], d) for d in [2, 3, 4] for k in cases]
    sx, sy = axes(c, (85, 319, 340, 175), xlim, bounds(values, zero=True),
                  list(zip(gx, map(str, gaps))), yfmt=lambda v: f"{v:.2e}")
    for d in [2, 3, 4]:
        line(c, sx, sy, gx, [value(k, d) for k in cases], colors[d])
    rx, ry = axes(c, (542, 319, 340, 175), xlim, bounds(ratios + [1], zero=True),
                  list(zip(gx, map(str, gaps))), yfmt=lambda v: f"{v:.2g}")
    reference(c, rx, ry, xlim, 1)
    for d in [2, 3, 4]:
        line(c, rx, ry, gx, [value(k, d) / value(cases[0], d) for k in cases], colors[d])
    for x in [255, 712]:
        label(c, x, 283, "Electrode surface gap [mm]", 9, MUTED, "center")
    label(c, 40, 255, "C   Single-ended / balanced field-norm ratio at fixed 1 V differential drive", 12, bold=True)
    singles = [(g, f"single_g{g:03d}_ppr") for g in [10, 300] if present(f"single_g{g:03d}_ppr")]
    if singles:
        ratios = [value(k, d) / value(f"gap_g{g:03d}_ppr", d) for g, k in singles for d in [2, 3, 4]]
        lim = bounds(ratios + [1], zero=True)
        sx, sy = axes(c, (85, 115, 797, 119), (-.6, len(singles) - .4), lim,
                      [(i, f"{g} mm gap") for i, (g, _) in enumerate(singles)], yfmt=lambda v: f"{v:.2g}")
        reference(c, sx, sy, (-.6, len(singles) - .4), 1)
        for i, (g, k) in enumerate(singles):
            for offset, d in zip([-34, 0, 34], [2, 3, 4]):
                ratio = value(k, d) / value(f"gap_g{g:03d}_ppr", d)
                c.setFillColor(HexColor(colors[d]))
                c.rect(sx(i) + offset - 11, sy(0), 22, sy(ratio) - sy(0), stroke=0, fill=1)
                label(c, sx(i) + offset, sy(ratio) + 5, f"{ratio:.2f}", 9, colors[d], "center")
        label(c, 85, 76, "Single-ended drive = +1 / 0 V relative to the model ground; ground-related common-mode conditions also change.", 9, MUTED)
    else:
        label(c, 85, 172, "Single-ended boundary cases are not yet available.", 12, MUTED)
    finish(c, path, "Ratios apply to fixed differential voltage; they are not fixed-current gains, measured detection gains, or calibrated limits of detection.")


def drive_scaling():
    current_path = DATA / "gap_current_scaled.csv"
    source_path = DATA / "source_currents.csv"
    if not current_path.exists() or not source_path.exists():
        print("Fixed-current figure skipped: current exports are not available.")
        return
    scaled = pd.read_csv(current_path)
    source = pd.read_csv(source_path)
    gaps = [10, 20, 50, 100, 200, 300]
    gx = np.log10(gaps)
    xlim = (gx[0] - .035, gx[-1] + .035)
    colors = {2: BLUE, 3: ORANGE, 4: GREEN}
    selected = scaled[scaled.case.isin([f"gap_g{g:03d}" for g in gaps])].copy()
    if len(selected) != 18:
        print("Fixed-current figure skipped: six complete current-scaled gap cases are not available.")
        return
    c, path = start("external_gap_drive_scaling", "Gap effect under voltage and current normalization",
                    "Balanced ground-referenced drive; recovered fields. Current-normalized values scale each solved 1 V case to |Ipos| = 10 mA.")
    legend(c, 40, 548, [(f"Distance {d} m", colors[d], False) for d in [2, 3, 4]])
    label(c, 85, 514, "A   Field norm after 10 mA amplitude scaling [V/m]", 12, bold=True)
    vals = selected.e_norm_at_10ma_v_m.tolist()
    sx, sy = axes(c, (85, 315, 797, 177), xlim, bounds(vals, zero=True),
                  list(zip(gx, map(str, gaps))), yfmt=lambda v: f"{v:.2e}")
    for d in [2, 3, 4]:
        q = selected[selected.distance_m.eq(d)].set_index("gap_mm")
        line(c, sx, sy, gx, [q.loc[g, "e_norm_at_10ma_v_m"] for g in gaps], colors[d])
    label(c, 483, 278, "Electrode surface gap [mm]", 9, MUTED, "center")
    label(c, 85, 248, "B   Gain relative to the 10 mm case", 12, bold=True)
    label(c, 85, 226, "Fixed 1 V differential drive", 10, bold=True)
    label(c, 542, 226, "Scaled to 10 mA positive-port current", 10, bold=True)
    ratios_v=[];ratios_i=[]
    for d in [2,3,4]:
        ratios_v += [value(f"gap_g{g:03d}_ppr",d)/value("gap_g010_ppr",d) for g in gaps]
        q=selected[selected.distance_m.eq(d)].set_index("gap_mm")
        ratios_i += [q.loc[g,"e_norm_at_10ma_v_m"]/q.loc[10,"e_norm_at_10ma_v_m"] for g in gaps]
    limit=bounds(ratios_v+ratios_i+[1],zero=True)
    for x0,title,kind in [(85,"",'v'),(542,"",'i')]:
        ax,ay=axes(c,(x0,83,340,122),xlim,limit,list(zip(gx,map(str,gaps))),yfmt=lambda v:f"{v:.1f}")
        reference(c,ax,ay,xlim,1)
        for d in [2,3,4]:
            if kind=='v': ys=[value(f"gap_g{g:03d}_ppr",d)/value("gap_g010_ppr",d) for g in gaps]
            else:
                q=selected[selected.distance_m.eq(d)].set_index("gap_mm");ys=[q.loc[g,"e_norm_at_10ma_v_m"]/q.loc[10,"e_norm_at_10ma_v_m"] for g in gaps]
            line(c,ax,ay,gx,ys,colors[d])
    finish(c,path,"Current scaling is linear postprocessing of each specified common-mode solution; it is not a calibrated detector limit or a floating-source circuit solution.")


if __name__ == "__main__":
    local_mesh()
    domain()
    gap_boundary()
    drive_scaling()
    manifest = {
        "script": str(Path(__file__).relative_to(ROOT)),
        "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [DATA / "all_transfers.csv", DATA / "comparisons.csv", DATA / "gap_current_scaled.csv", DATA / "source_currents.csv"]},
        "outputs": FILES,
        "frequency_hz": 0.001,
        "notes": "No experimental results. Field norm units are V/m per 1 V; relative comparisons are explicitly labelled.",
    }
    (OUT / "external_figures_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Created {len(FILES) // 2} external-field figures (vector PDF and PNG).")
