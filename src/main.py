#====================================================================
# File Name: main.py
# Project Name: 水下目标电荷探测数据分析系统
# Description: 系统主程序入口，负责启动各个模块
#====================================================================

#!/usr/bin/env python3

"""
水下目标电荷探测数据分析系统主程序
简化版本，仅负责启动各个模块
"""

import argparse
import logging
from src.utils.logging_utils import setup_logging

def main():
    """主函数 - 仅负责启动各个模块"""
    # 设置日志
    logger = setup_logging()
    logger.info("启动水下目标电荷探测数据分析系统")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='水下目标电荷探测数据分析系统')
    parser.add_argument('module', choices=['timedata', 'freqdata', 'freqodata', 'time', 'freq', 'visualize', 'report', 'all'],
                       help='选择要执行的模块')
    parser.add_argument('--data-folder', help='数据文件夹路径')
    parser.add_argument('--config', default='config/parameters.yaml', 
                       help='配置文件路径')
    parser.add_argument('--log-config', default='config/logging.yaml',
                       help='日志配置文件路径')
    
    args = parser.parse_args()
    
    # 重新设置日志以使用指定的配置文件
    if args.log_config:
        logger = setup_logging(args.log_config)
    
    # 根据选择的模块执行相应的功能
    try:
        if args.module == 'timedata':
            logger.info("生成时域csv文件")
            from src.data_io.tdms_reader_time import main as load_main
            load_main()

        elif args.module == 'freqdata':
            logger.info("生成频域csv文件")
            from src.data_io.tdms_reader_frequency import main as load_main
            load_main()

        elif args.module == 'freqodata':
            logger.info("生成频域csv文件")
            from src.data_io.tdms_reader_frequency_one import main as load_main
            load_main()

        elif args.module == 'preprocess':
            logger.info("启动数据预处理模块")
            from src.preprocessing.background_subtraction import main as preprocess_main
            preprocess_main()
        
        elif args.module == 'time':
            logger.info("启动时域分析模块")
            from src.analysis.time_domain import main as time_main
            time_main()
        
        elif args.module == 'freq':
            logger.info("启动频域分析模块")
            from src.analysis.frequency_domain import main as freq_main
            freq_main()
        
        elif args.module == 'visualize':
            logger.info("启动可视化模块")
            from src.visualization.dft_images import main as visualize_main
            visualize_main()
        
        elif args.module == 'report':
            logger.info("启动报告生成模块")
            from src.reporting.report_generator import main as report_main
            report_main()
        
        elif args.module == 'all':
            logger.info("启动完整分析流程")
            # 依次执行所有模块
            from src.data_io.tdms_reader_time import main as load_main
            from src.preprocessing.background_subtraction import main as preprocess_main
            from src.analysis.time_domain import main as time_main
            from src.analysis.frequency_domain import main as freq_main
            from src.visualization.dft_images import main as visualize_main
            from src.reporting.report_generator import main as report_main
            
            load_main()
            preprocess_main()
            time_main()
            freq_main()
            visualize_main()
            report_main()
        
        logger.info("模块执行完成")
    
    except Exception as e:
        logger.exception(f"执行模块 {args.module} 时发生错误: {e}")
        raise

if __name__ == "__main__":
    main()