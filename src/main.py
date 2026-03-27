#====================================================================
# File Name: main.py
# Project Name: 水下目标电荷探测数据分析系统
# Description: 系统主程序入口，负责启动各个模块
#====================================================================
import argparse
import logging

from src.utils.logging_utils import setup_logging
from src.utils.file_utils import generate_paths_config as generate_paths_config
#from src.core.database import main as database_main

from src.data_io.tdms_reader_time import main as time_main
from src.data_io.tdms_reader_frequency import main as frequency_main
from src.data_io.tdms_reader_frequency_average import main as frequency_average_main

from src.visualization.time_series_plots import main as time_plots_main
from src.visualization.frequency_plots import main as freq_plots_main


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='数据分析系统')
    parser.add_argument('module', choices=['timedata', 'freqdata', 'freqavedata',
                                            'timeplots', 'freqplots', 'visualize', 'report', 'all'])
    parser.add_argument('--data-folder')
    parser.add_argument('--config', default='config/parameters.yaml')
    parser.add_argument('--log-config', default='config/logging.yaml')
    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(args.log_config)
    logger.info("-------------------------启动数据分析系统-------------------------")
    generate_paths_config()
#    database_main()

    if args.module == 'timedata':
            time_main()

    elif args.module == 'freqdata':
            frequency_main()

    elif args.module == 'freqavedata':
            frequency_average_main()

    elif args.module == 'timeplots':
            time_plots_main()
        
    elif args.module == 'freqplots':
            freq_plots_main()

    elif args.module == 'visualize':
            time_plots_main()
            freq_plots_main()

    elif args.module == 'report':
            # 当前报告由可视化模块一并生成
            time_plots_main()
            freq_plots_main()

    elif args.module == 'all':
            time_main()
            frequency_main()
            frequency_average_main()
            time_plots_main()
            freq_plots_main()
        
    logger.info("-----------------------------执行完成-----------------------------")


if __name__ == "__main__":
    main()
