"""Recompute only representative cases and redraw mentor-method figures."""

from __future__ import annotations

from scripts.analyze_mentor_nonlinear_highfreq import (
    bicoherence_analysis,
    load_common_raw_snippets,
    plot_bicoherence_maps,
)
from scripts.analyze_mentor_wavelet_relaxation import (
    cwt_analysis,
    plot_representative_scalograms,
)
from scripts.mentor_method_common import (
    METHOD_OUTPUT,
    all_cases,
    load_analysis_signals,
    load_health_table,
    stable_seed,
)


def main() -> None:
    target_ids = {
        "duo1_tc1_background", "duo1_tc1_30hz", "duo1_tc1_50hz"
    }
    cases = [case for case in all_cases() if case.case_id in target_ids]
    health = load_health_table()
    cwt_cache = {}
    bicoherence_cache = {}
    for case in cases:
        loaded = load_analysis_signals(case, health)
        cwt_cache[(case.case_id, "slow_pc1")] = cwt_analysis(
            loaded.signals["slow_pc1"], loaded.sample_rate_hz
        )
        snippets, raw_rate = load_common_raw_snippets(
            case.archive, loaded.healthy_indices
        )
        bicoherence_cache[case.case_id] = bicoherence_analysis(
            snippets, raw_rate, 1, stable_seed("rerender", case.case_id)
        )
    plot_representative_scalograms(
        cwt_cache,
        METHOD_OUTPUT / "wavelet_relaxation" / "figures" / "representative_slow_cwt.png",
    )
    plot_bicoherence_maps(
        bicoherence_cache,
        METHOD_OUTPUT / "nonlinear_highfreq" / "figures" / "representative_short_bicoherence.png",
    )
    print("Representative figures redrawn")


if __name__ == "__main__":
    main()
