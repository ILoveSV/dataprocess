#====================================================================
# File Name: tdms_reader_time.py
# Project Name: dataprocess
# Description:
# 1、读取TDMS文件：遍历原始数据目录下的所有子文件夹
# 2、生成CSV文件：文件名保持与原TDMS文件相同的时间戳格式
# 3、CSV文件结构：
#   列名         数据类型                   描述
#   time         字符串          相对时间，从0开始的微秒数，格式为浮点数
#   channel1     数值 (float)    通道1的传感器数据
#   channel2     数值 (float)    通道2的传感器数据
#   ...          ...             ...
#   channel16    数值 (float)    通道16的传感器数据
# 4、同时生成对应的元数据JSON文件，包含采样信息和时间参考
# 5、采样间隔：5微秒 (200kHz采样率)，从TDMS文件属性自动读取
# 6、支持多进程并行处理，提高大文件处理效率
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
import json 

logger = logging.getLogger('data_process')

def load_config():
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config

def process_tdms_file(tdms_path, output_base_dir, raw_data_dir):
    """处理单个TDMS文件，使用相对时间便于分析"""
    try:
#        logger.info(f"开始处理文件: {tdms_path}")

        filename = os.path.basename(tdms_path)
        time_str = re.search(r'(\d{8}\d{6}\.\d+)', filename)

        start_time_str = time_str.group(1)
        start_time_from_filename = datetime.strptime(start_time_str, "%Y%m%d%H%M%S.%f")

        tdms_file = TdmsFile.read(tdms_path)
        groups = tdms_file.groups()
        
        group = groups[0]
        channels = [ch for ch in group.channels()]
            
        # 确定数据长度和通道数
        data_length = len(channels[0])
        num_channels = len(channels)
        
#        logger.info(f"处理文件: {filename}, 数据长度: {data_length}, 通道数: {num_channels}")
        
        # 从第一个通道读取实际的元数据
        first_channel = channels[0]
        
        # 获取实际的采样间隔（秒）
        if hasattr(first_channel, 'properties') and 'wf_increment' in first_channel.properties:
            sampling_interval = first_channel.properties['wf_increment']  # 0.000005秒
            wf_samples        = first_channel.properties['wf_samples']
#            logger.info(f"使用实际采样间隔: {sampling_interval} 秒")
        else:
            # 回退到默认值
            sampling_interval = 5e-6  # 5微秒
#            logger.warning("未找到wf_increment属性，使用默认采样间隔5微秒")
        
        # 确定起始时间（用于元数据）
        if hasattr(first_channel, 'properties') and 'wf_start_time' in first_channel.properties:
            wf_start_time = first_channel.properties['wf_start_time']
            if hasattr(wf_start_time, 'item'):
                start_time_absolute = wf_start_time.item()
            else:
                start_time_absolute = wf_start_time
#            logger.info(f"使用通道起始时间: {start_time_absolute}")
        else:
            start_time_absolute = start_time_from_filename
#            logger.info("使用文件名时间作为起始时间")
        
        time_relative_seconds = np.arange(data_length) * sampling_interval
        time_relative_ms = time_relative_seconds * 1000
        time_relative_us = time_relative_seconds * 1e6
        time_list = [f"{t:.9f}" for t in time_relative_seconds]
        
        data_dict = {"time": time_list}
        for i, channel in enumerate(channels):
            data_dict[f"channel{i+1}"] = channel[:]
        
        df = pd.DataFrame(data_dict)
        
        # 创建输出目录结构
        relative_path = os.path.relpath(os.path.dirname(tdms_path), raw_data_dir)
        output_dir = os.path.join(output_base_dir, relative_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存为CSV文件
        output_filename = f"{start_time_str}.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        # 分块写入CSV
        chunk_size = 100000
        for i in range(0, data_length, chunk_size):
            end_idx = min(i + chunk_size, data_length)
            chunk_df = df.iloc[i:end_idx]
            
            if i == 0:
                chunk_df.to_csv(output_path, index=False, encoding='utf-8-sig', float_format='%.9f')
            else:
                chunk_df.to_csv(output_path, mode='a', header=False, index=False, encoding='utf-8-sig', float_format='%.9f')
            
 #           logger.info(f"  已写入 {end_idx}/{data_length} 行数据")
        
        # === 保存元数据文件 ===
        metadata = {
            'filename': filename,
            'start_time': start_time_absolute.isoformat() if hasattr(start_time_absolute, 'isoformat') else str(start_time_absolute),
            'filename_time': start_time_from_filename.isoformat(),
            'sampling_interval_seconds': sampling_interval,
            'sampling_rate_hz': wf_samples,
            'data_length': data_length,
            'total_duration_seconds': data_length * sampling_interval,
            'num_channels': num_channels,
            'time_reference': 'relative_seconds_from_zero',
            'time_unit': 'seconds'
        }
        
        # 保存元数据为JSON
        metadata_path = output_path.replace('.csv', '_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
#        logger.info(f"已转换: {filename} -> {output_path}")
#        logger.info(f"元数据保存: {metadata_path}")
        
    except Exception as e:
        logger.error(f"处理文件 {os.path.basename(tdms_path)} 时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def process_tdms_file_wrapper(args):
    """包装函数，用于多进程调用"""
    tdms_path, output_base_dir, raw_data_dir = args
    # 在子进程中重新配置日志
    from src.utils.logging_utils import setup_logging
    import os
    project_root = Path(__file__).resolve().parent.parent.parent
    log_config_path = project_root / "config" / "logging.yaml"
    if os.path.exists(log_config_path):
        setup_logging(log_config_path)
    return process_tdms_file(tdms_path, output_base_dir, raw_data_dir)

def process_tdms_files_parallel(tdms_files, output_base_dir, raw_data_dir):
    max_workers = multiprocessing.cpu_count()
    params = [(tdms_file, output_base_dir, raw_data_dir) for tdms_file in tdms_files]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(process_tdms_file_wrapper, params))

def main():
    
    config = load_config()
    if not config:
        logger.error("无法加载配置文件")

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
    
    process_tdms_files_parallel(tdms_files, output_base_dir, data_folder)
    
    logger.info("所有文件处理完成")

if __name__ == "__main__":
    main()