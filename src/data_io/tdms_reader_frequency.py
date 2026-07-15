from src.core.config_loader import load_config
from src.core.path_resolver import resolve_scan_folder
from src.features.fft_core import perform_fft_analysis
from src.io.metadata_io import normalize_sampling_rate
from src.pipelines.fft_export_pipeline import (
    main,
    process_csv_file,
    process_csv_file_wrapper,
    process_csv_files_parallel,
)


if __name__ == "__main__":
    main()

