from src.core.config_loader import load_config
from src.core.path_resolver import resolve_scan_folder
from src.pipelines.tdms_to_time_pipeline import (
    main,
    process_tdms_file,
    process_tdms_file_wrapper,
    process_tdms_files_parallel,
)


if __name__ == "__main__":
    main()

