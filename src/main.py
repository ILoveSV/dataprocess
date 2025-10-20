#====================================================================
# File Name: main.py
# Project Name: 水下目标电荷探测数据分析系统
# Description: 系统主程序入口，负责启动各个模块
#====================================================================
import argparse
import logging
from src.utils.logging_utils import setup_logging
#from src.core.database import main as database_main
from src.data_io.tdms_reader_time import main as load_main
from src.data_io.tdms_reader_frequency import main as frequency_main
from src.data_io.tdms_reader_frequency_average import main as frequency_average_main
from src.data_io.sql_tdms_reader import main as sql_tdms_reader_main
from src.analysis.time_domain import main as time_main
from src.utils.file_utils import generate_paths_config as generate_paths_config

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='数据分析系统')
    parser.add_argument('module', choices=['timedata', 'freqdata', 'freqavedata',
                                            'time', 'freq', 'visualize', 'report', 'all'])
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
            load_main()

    elif args.module == 'freqdata':
            frequency_main()

    elif args.module == 'freqavedata':
            frequency_average_main()

    elif args.module == 'preprocess':
            load_main()
        
    elif args.module == 'time':
            sql_tdms_reader_main()
        
    elif args.module == 'freq':
            load_main()
        
    elif args.module == 'visualize':
            load_main()
        
    elif args.module == 'report':
            print("11111")
        
    elif args.module == 'all':
            load_main()
            time_main()
        
    logger.info("-----------------------------执行完成-----------------------------")


if __name__ == "__main__":
    main()