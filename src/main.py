#====================================================================
# File Name: main.py
# Project Name: 水下目标电荷探测数据分析系统
# Description: 系统主程序入口，负责启动各个模块
#====================================================================
import argparse
import logging

from src.utils.logging_utils import setup_logging
from src.utils.file_utils import generate_paths_config as generate_paths_config
from src.utils.perf_timing import maybe_write_summary
#from src.core.database import main as database_main

from src.data_io.tdms_reader_time import main as time_main
from src.data_io.tdms_reader_time_merged import run as merged_time_run
from src.data_io.tdms_reader_frequency import main as frequency_main
from src.data_io.tdms_reader_frequency_average import main as frequency_average_main

from src.visualization.time_series_plots import main as time_plots_main
from src.visualization.frequency_plots import main as freq_plots_main
from src.pipelines.nist_diagnostics_pipeline import main as nist_diagnostics_main
from src.pipelines.first_test_pipeline import main as first_test_main


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='数据分析系统')
    parser.add_argument('module', choices=['timedata', 'timedata-merged', 'first-test-pipeline', 'freqdata', 'freqavedata',
                                            'timeplots', 'freqplots', 'nistdiagnostics',
                                            'nistplots', 'visualize', 'report', 'all'])
    parser.add_argument('--data-folder')
    parser.add_argument('--input', dest='input_path', default=None)
    parser.add_argument('--output', default=None)
    parser.add_argument('--config', default='config/parameters.yaml')
    parser.add_argument('--log-config', default='config/logging.yaml')
    parser.add_argument('--debug-file-plots', action='store_true')
    parser.add_argument('--centered-plot', action='store_true')
    parser.add_argument('--centered-plot-mv', action='store_true')
    parser.add_argument('--max-acf-lag', type=int, default=None)
    parser.add_argument('--max-acf-seconds', type=float, default=None)
    parser.add_argument('--acf-min-peak-distance-s', type=float, default=None)
    parser.add_argument('--acf-min-peak-prominence', type=float, default=None)
    parser.add_argument('--acf-near-zero-exclude-s', type=float, default=None)
    parser.add_argument('--min-period-s', type=float, default=None)
    parser.add_argument('--acf-strong-peak-height', type=float, default=None)
    parser.add_argument('--acf-strong-peak-prominence', type=float, default=None)
    parser.add_argument('--welch-nperseg', type=int, default=None)
    parser.add_argument('--low-freq-nperseg', type=int, default=None)
    parser.add_argument('--psd-exclude-low-hz', type=float, default=None)
    parser.add_argument('--max-psd-period-refs', type=int, default=None)
    parser.add_argument('--plots', choices=['none', 'minimal', 'full'], default='minimal')
    parser.add_argument('--dpi', type=int, default=150)
    parser.add_argument('--max-plot-points', type=int, default=5000)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', default=True)
    parser.add_argument('--no-skip-existing', dest='skip_existing', action='store_false')
    parser.add_argument('--export-excel', action='store_true')
    parser.add_argument('--segment-seconds', type=float, default=2.7)
    parser.add_argument('--min-segment-seconds', type=float, default=0.0)
    parser.add_argument('--max-segments-per-file', type=int, default=None)
    parser.add_argument('--max-workers', type=int, default=None)
    parser.add_argument('--max-files', type=int, default=None)
    parser.add_argument('--max-channels', type=int, default=None)
    parser.add_argument('--skip-4plot', action='store_true')
    parser.add_argument('--skip-psd', action='store_true')
    parser.add_argument('--skip-bandpower-gain', action='store_true')
    parser.add_argument('--skip-time-stats', action='store_true')
    parser.add_argument('--export-time-stats-excel', action='store_true')
    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(args.log_config)
    logger.info("-------------------------启动数据分析系统-------------------------")
    generate_paths_config()
#    database_main()

    if args.module == 'timedata':
            time_main(args.data_folder)

    elif args.module == 'timedata-merged':
            merged_time_run(
                    input_path=args.input_path,
                    output_path=args.output,
                    data_folder=args.data_folder,
                    segment_seconds=args.segment_seconds,
                    min_segment_seconds=args.min_segment_seconds,
                    max_segments_per_file=args.max_segments_per_file,
                    skip_existing=args.skip_existing,
                    max_workers=args.max_workers,
            )

    elif args.module == 'first-test-pipeline':
            first_args = []
            if args.input_path:
                    first_args.extend(['--input', args.input_path])
            if args.output:
                    first_args.extend(['--output', args.output])
            if args.max_files is not None:
                    first_args.extend(['--max-files', str(args.max_files)])
            if args.max_channels is not None:
                    first_args.extend(['--max-channels', str(args.max_channels)])
            if args.welch_nperseg is not None:
                    first_args.extend(['--welch-nperseg', str(args.welch_nperseg)])
            if args.low_freq_nperseg is not None:
                    first_args.extend(['--low-freq-nperseg', str(args.low_freq_nperseg)])
            if args.psd_exclude_low_hz is not None:
                    first_args.extend(['--psd-exclude-low-hz', str(args.psd_exclude_low_hz)])
            if args.skip_4plot:
                    first_args.append('--skip-4plot')
            if args.skip_psd:
                    first_args.append('--skip-psd')
            if args.skip_bandpower_gain:
                    first_args.append('--skip-bandpower-gain')
            if args.skip_time_stats:
                    first_args.append('--skip-time-stats')
            if args.export_time_stats_excel:
                    first_args.append('--export-time-stats-excel')
            if not args.skip_existing:
                    first_args.append('--no-skip-existing')
            first_test_main(first_args)

    elif args.module == 'freqdata':
            frequency_main(args.data_folder, force=args.force, skip_existing=args.skip_existing)

    elif args.module == 'freqavedata':
            frequency_average_main(args.data_folder, force=args.force, skip_existing=args.skip_existing)

    elif args.module == 'timeplots':
            time_input = args.input_path or args.data_folder
            time_plot_args = ['--input', time_input] if time_input else []
            if args.output:
                    time_plot_args.extend(['--output', args.output])
            if args.export_excel:
                    time_plot_args.append('--export-excel')
            if args.force:
                    time_plot_args.append('--force')
            if not args.skip_existing:
                    time_plot_args.append('--no-skip-existing')
            time_plots_main(time_plot_args)
        
    elif args.module == 'freqplots':
            freq_args = ['--plots', args.plots, '--dpi', str(args.dpi), '--max-plot-points', str(args.max_plot_points)]
            freq_input = args.input_path or args.data_folder
            if freq_input:
                    freq_args.extend(['--input', freq_input])
            if args.output:
                    freq_args.extend(['--output', args.output])
            if args.force:
                    freq_args.append('--force')
            if not args.skip_existing:
                    freq_args.append('--no-skip-existing')
            freq_plots_main(freq_args)

    elif args.module in ('nistdiagnostics', 'nistplots'):
            nist_args = ['--input', args.data_folder] if args.data_folder else []
            if args.debug_file_plots:
                    nist_args.append('--debug-file-plots')
            if args.centered_plot:
                    nist_args.append('--centered-plot')
            if args.centered_plot_mv:
                    nist_args.append('--centered-plot-mv')
            if args.max_acf_lag is not None:
                    nist_args.extend(['--max-acf-lag', str(args.max_acf_lag)])
            if args.max_acf_seconds is not None:
                    nist_args.extend(['--max-acf-seconds', str(args.max_acf_seconds)])
            if args.acf_min_peak_distance_s is not None:
                    nist_args.extend(['--acf-min-peak-distance-s', str(args.acf_min_peak_distance_s)])
            if args.acf_min_peak_prominence is not None:
                    nist_args.extend(['--acf-min-peak-prominence', str(args.acf_min_peak_prominence)])
            if args.acf_near_zero_exclude_s is not None:
                    nist_args.extend(['--acf-near-zero-exclude-s', str(args.acf_near_zero_exclude_s)])
            if args.min_period_s is not None:
                    nist_args.extend(['--min-period-s', str(args.min_period_s)])
            if args.acf_strong_peak_height is not None:
                    nist_args.extend(['--acf-strong-peak-height', str(args.acf_strong_peak_height)])
            if args.acf_strong_peak_prominence is not None:
                    nist_args.extend(['--acf-strong-peak-prominence', str(args.acf_strong_peak_prominence)])
            if args.welch_nperseg is not None:
                    nist_args.extend(['--welch-nperseg', str(args.welch_nperseg)])
            if args.low_freq_nperseg is not None:
                    nist_args.extend(['--low-freq-nperseg', str(args.low_freq_nperseg)])
            if args.psd_exclude_low_hz is not None:
                    nist_args.extend(['--psd-exclude-low-hz', str(args.psd_exclude_low_hz)])
            if args.max_psd_period_refs is not None:
                    nist_args.extend(['--max-psd-period-refs', str(args.max_psd_period_refs)])
            nist_diagnostics_main(nist_args)

    elif args.module == 'visualize':
            time_plot_args = ['--input', args.data_folder] if args.data_folder else []
            time_plots_main(time_plot_args)
            freq_plots_main(['--plots', args.plots, '--dpi', str(args.dpi), '--max-plot-points', str(args.max_plot_points)])

    elif args.module == 'report':
            # 当前报告由可视化模块一并生成
            time_plots_main()
            freq_plots_main(['--plots', args.plots, '--dpi', str(args.dpi), '--max-plot-points', str(args.max_plot_points)])

    elif args.module == 'all':
            time_main(args.data_folder)
            frequency_main(args.data_folder)
            frequency_average_main(args.data_folder)
            time_plots_main([])
            freq_plots_main(['--plots', args.plots, '--dpi', str(args.dpi), '--max-plot-points', str(args.max_plot_points)])
        
    logger.info("-----------------------------执行完成-----------------------------")


    maybe_write_summary()

if __name__ == "__main__":
    main()
