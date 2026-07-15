import importlib


STEPS = [
    "step00_geometry_scan",
    "step01_control_equations",
    "step02_source_model_scan",
    "step03_static_dipole_scan",
    "step04_conductivity_sensitivity",
    "step05_skin_depth_scan",
    "step06_shaft_rate_scan",
    "step07_moving_target_envelope",
    "step08_receiver_array",
    "step09_mems_response",
    "step10_noise_spectrum",
    "step11_snr_range_scan",
    "step12_source_comparison",
]


def main():
    for step in STEPS:
        module = importlib.import_module(step)
        module.main()
        print(f"finished {step}")


if __name__ == "__main__":
    main()
