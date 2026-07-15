from _common import TABLE_DIR, write_csv

from src.constants import DEFAULT_SIGMA_S_PER_M, MU0_H_PER_M, SIGMA_RANGE_S_PER_M


def main():
    rows = [
        {
            "item": "quasi_static_conduction_equation",
            "latex": r"\nabla\cdot(\sigma\nabla\varphi)=-\rho_I",
            "meaning": "导电海水准静态控制方程",
            "unit": "A/m^3 source density with sigma in S/m",
        },
        {
            "item": "electric_field",
            "latex": r"\mathbf E=-\nabla\varphi",
            "meaning": "电场由电势梯度给出",
            "unit": "V/m",
        },
        {
            "item": "current_density",
            "latex": r"\mathbf J=\sigma\mathbf E",
            "meaning": "欧姆导电电流密度",
            "unit": "A/m^2",
        },
        {
            "item": "uniform_seawater_poisson",
            "latex": r"\nabla^2\varphi=-\rho_I/\sigma",
            "meaning": "均匀各向同性海水中的泊松形式",
            "unit": "V/m^2",
        },
    ]
    write_csv(TABLE_DIR / "control_equations.csv", ["item", "latex", "meaning", "unit"], rows)
    params = [
        {"parameter": "mu0", "value": MU0_H_PER_M, "unit": "H/m", "note": "真空磁导率"},
        {"parameter": "sigma_default", "value": DEFAULT_SIGMA_S_PER_M, "unit": "S/m", "note": "默认海水电导率"},
        {"parameter": "sigma_min", "value": SIGMA_RANGE_S_PER_M[0], "unit": "S/m", "note": "扫描下限"},
        {"parameter": "sigma_max", "value": SIGMA_RANGE_S_PER_M[1], "unit": "S/m", "note": "扫描上限"},
    ]
    write_csv(TABLE_DIR / "physical_constants.csv", ["parameter", "value", "unit", "note"], params)


if __name__ == "__main__":
    main()
