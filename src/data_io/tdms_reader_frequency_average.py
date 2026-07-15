from src.core.config_loader import load_config
from src.core.path_resolver import resolve_scan_folder
from src.features.fft_average import calculate_average_fft
from src.io.fft_csv_io import group_files_by_folder, save_average_fft
from src.pipelines.fft_average_pipeline import main, process_folder_group
from src.reports.text_report import generate_summary_report


if __name__ == "__main__":
    main()

