from src.core.config_loader import load_config
from src.features.fft_statistics import (
    analyze_frequency_clusters,
    analyze_phase_relationships,
    auto_detect_feature_frequencies,
    calculate_fft_statistics,
    categorize_frequencies_to_clusters,
)
from src.io.fft_csv_io import _collect_channel_matrix, extract_channel_info, read_fft_data
from src.pipelines.frequency_analysis_pipeline import analyze_group, main
from src.plots.frequency_plots import (
    _plot_channel_peak_windows,
    _plot_spectrum_band,
    _robust_ylim,
    _safe_positive,
    plot_group_amplitude_spectrum,
    plot_group_dominant_frequencies,
    plot_group_feature_frequencies,
    plot_group_phase_analysis,
    plot_group_stability_analysis,
)
from src.reports.json_report import generate_group_analysis_report


if __name__ == "__main__":
    main()
