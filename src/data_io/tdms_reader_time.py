#====================================================================
# File Name:tdms_reader.py
# Project Name:dataprocess
# Description:
# 1、读取TDMS文件：遍历主文件夹下的子文件夹
# 2、生成csv文件，文件名格式为TDMS文件名格式：YYYYMMDDHHMMSS.ffffff.csv
# 3、csv文件结构：
#  列名	       数据类型	                   描述	                         示例
#  time	       字符串	        时间戳，格式为YYYYMMDDHHMMSS.ffffff	 "20250724170135.631506"
#  channel1	数值 (float/int)	    通道1的传感器数据	                0.12345
#  channel2	数值 (float/int)	     通道2的传感器数据	                -1.23456
#  ...	        ...	                       ...	                          ...
#  channelN	数值 (float/int)	通道N的传感器数据，N最大为16	          2.34567
# 4、采样间隔：2微秒 (500kHz采样率)
#====================================================================

import numpy as np
from nptdms import TdmsFile
import os
import pandas as pd
from datetime import datetime, timedelta
import re
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import yaml
import sys
from pathlib import Path
import logging

# 设置日志
logger = logging.getLogger(__name__)

def load_config():
    """加载YAML配置文件"""
    try:
        # 获取项目根目录
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "config" / "paths.yaml"
        
        logger.info(f"尝试加载配置文件: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        logger.info(f"配置文件加载成功: {config}")
        return config
    except Exception as e:
        logger.error(f"加载配置文件时出错: {str(e)}")
        return None

def process_tdms_file(tdms_path, output_base_dir, raw_data_dir):
    """处理单个TDMS文件，添加时间列并保存为CSV到指定输出目录"""
    try:
        logger.info(f"开始处理文件: {tdms_path}")
        
        # 从文件名提取起始时间
        filename = os.path.basename(tdms_path)
        time_str = re.search(r'(\d{8}\d{6}\.\d+)', filename)
        if not time_str:
            logger.warning(f"文件名 {filename} 中未找到有效时间戳")
            return
            
        start_time_str = time_str.group(1)
        # 解析起始时间
        start_time = datetime.strptime(start_time_str, "%Y%m%d%H%M%S.%f")
        
        # 读取TDMS文件
        tdms_file = TdmsFile.read(tdms_path)
        
        # 获取所有组和通道
        groups = tdms_file.groups()
        if not groups:
            logger.warning(f"文件 {filename} 中没有找到任何组")
            return
            
        # 使用第一个组
        group = groups[0]
        channels = [ch for ch in group.channels()]
        
        if not channels:
            logger.warning(f"组 {group.name} 中没有找到任何通道")
            return
            
        # 确定数据长度和通道数
        data_length = len(channels[0])
        num_channels = len(channels)
        
        logger.info(f"处理文件: {filename}, 数据长度: {data_length}, 通道数: {num_channels}")
        
        # 创建时间列 (时间间隔设置为2微秒，根据实际情况调整)
        time_interval = timedelta(microseconds=2)  # 500kHz采样率
        
        # 创建时间字符串列表
        time_list = []
        for i in range(data_length):
            current_time = start_time + i * time_interval
            # 格式化为与文件名相同的格式，并确保精度完整
            time_str = current_time.strftime("%Y%m%d%H%M%S.%f")
            # 确保微秒部分有6位数字
            if len(time_str.split('.')[1]) < 6:
                time_str = time_str.ljust(21, '0')  # 总长度21字符，不足补零
            time_list.append(time_str)
        
        # 创建数据字典
        data_dict = {"time": time_list}
        
        # 添加每个通道的数据，使用英文列名
        for i, channel in enumerate(channels):
            data_dict[f"channel{i+1}"] = channel[:]
        
        df = pd.DataFrame(data_dict)
        
        # 创建输出目录结构
        # 获取相对于原始数据根目录的路径
        relative_path = os.path.relpath(os.path.dirname(tdms_path), raw_data_dir)
        output_dir = os.path.join(output_base_dir, relative_path)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存为CSV文件 (分块保存以避免内存问题)
        output_filename = f"{start_time_str}.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        # 分块写入CSV，避免内存不足
        chunk_size = 100000  # 每次处理10万行
        for i in range(0, data_length, chunk_size):
            end_idx = min(i + chunk_size, data_length)
            chunk_df = df.iloc[i:end_idx]
            
            # 如果是第一块，写入列名，否则追加
            if i == 0:
                chunk_df.to_csv(output_path, index=False, encoding='utf-8-sig', quoting=1)
            else:
                chunk_df.to_csv(output_path, mode='a', header=False, index=False, encoding='utf-8-sig', quoting=1)
            
            logger.info(f"  已写入 {end_idx}/{data_length} 行数据")
        
        logger.info(f"已转换: {filename} -> {output_path}")
        
    except Exception as e:
        logger.error(f"处理文件 {os.path.basename(tdms_path)} 时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def process_tdms_files_serial(tdms_files, output_base_dir, raw_data_dir):
    """串行处理TDMS文件"""
    for tdms_file in tdms_files:
        process_tdms_file(tdms_file, output_base_dir, raw_data_dir)

def process_tdms_files_parallel(tdms_files, output_base_dir, raw_data_dir):
    """并行处理TDMS文件"""
    max_workers = multiprocessing.cpu_count()
    logger.info(f"使用 {max_workers} 个进程并行处理")
    
    # 创建参数列表
    params = [(tdms_file, output_base_dir, raw_data_dir) for tdms_file in tdms_files]
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 使用executor.map处理参数列表
        list(executor.map(lambda args: process_tdms_file(*args), params))

def main():
    """主函数"""
    # 设置日志级别
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 加载配置文件
    config = load_config()
    
    if not config:
        logger.warning("无法加载配置文件，使用默认路径")
        config = {
            "raw_data_dir": "D:/Lab/test/2025.7.22",
            "tdms_reader_time_output_dir": "D:/Lab/results/data/time"
        }
    
    # 设置原始数据文件夹路径和输出文件夹路径
    data_folder = config["raw_data_dir"]
    output_base_dir = config["tdms_reader_time_output_dir"]
    
    logger.info(f"原始数据目录: {data_folder}")
    logger.info(f"输出目录: {output_base_dir}")
    
    # 查找所有TDMS文件
    tdms_files = []
    for root, dirs, files in os.walk(data_folder):
        for file in files:
            if file.endswith('.tdms'):
                tdms_files.append(os.path.join(root, file))
    
    if not tdms_files:
        logger.warning("未找到任何TDMS文件")
        return
    
    logger.info(f"找到 {len(tdms_files)} 个TDMS文件")
    
    # 先尝试串行处理，以便更好地调试
#    logger.info("开始串行处理文件...")
#    process_tdms_files_serial(tdms_files, output_base_dir, data_folder)
    
    # 如果需要并行处理，可以取消下面的注释
    logger.info("开始并行处理文件...")
    process_tdms_files_parallel(tdms_files, output_base_dir, data_folder)
    
    logger.info("所有文件处理完成")

if __name__ == "__main__":
    main()