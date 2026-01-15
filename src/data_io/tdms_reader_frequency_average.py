#====================================================================
# File Name: tdms_reader_frequency_average.py
# Project Name: dataprocess
# Description:
# 1、读取FFT CSV文件：遍历频率数据目录下的所有子文件夹
# 2、生成平均FFT CSV文件：对同一文件夹下的所有FFT文件进行平均计算
# 3、CSV文件结构：
#   列名         数据类型                   描述
#   frequency    数值 (float)    频率轴数据（Hz）
#   amplitude1   数值 (float)    通道1的平均幅度谱
#   phase1       数值 (float)    通道1的平均相位谱
#   amplitude2   数值 (float)    通道2的平均幅度谱
#   phase2       数值 (float)    通道2的平均相位谱
#   ...          ...             ...
#   amplitudeN   数值 (float)    通道N的平均幅度谱
#   phaseN       数值 (float)    通道N的平均相位谱
# 4、保持原始文件夹结构：按30hz、50hz、back等原始文件夹分组处理
# 5、输出文件命名：average_fft_文件夹名_文件数量files.csv
# 6、支持多进程并行处理，提高大文件处理效率
# 7、自动验证数据一致性：检查频率轴和数据结构匹配性
# 8、生成处理汇总报告，记录处理统计信息
#====================================================================
import numpy as np
import pandas as pd
import os
from pathlib import Path
import yaml
import logging
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

logger = logging.getLogger('data_process')

def load_config():
    """加载配置文件"""
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config

def group_files_by_folder(csv_files, input_base_dir):
    """
    根据原始文件夹结构对文件进行分组
    
    参数:
    csv_files: CSV文件路径列表
    input_base_dir: 输入基准目录
    
    返回:
    grouped_files: 按文件夹分组的文件字典 {文件夹路径: [文件路径列表]}
    """
    grouped_files = defaultdict(list)
    
    for csv_file in csv_files:
        # 获取相对于基准目录的文件夹路径
        relative_dir = os.path.relpath(os.path.dirname(csv_file), input_base_dir)
        grouped_files[relative_dir].append(csv_file)
    
    logger.info(f"按文件夹分组完成，找到 {len(grouped_files)} 个文件夹组")
    for folder, files in grouped_files.items():
        logger.info(f"  文件夹 {folder}: {len(files)} 个文件")
    
    return grouped_files

def calculate_average_fft(files_group):
    """
    计算一组文件的FFT平均值
    
    参数:
    files_group: 同一文件夹下的文件路径列表
    
    返回:
    average_data: 平均后的FFT数据字典
    group_info: 分组信息 (文件夹名, 文件数量)
    """
    if not files_group:
        return None, None
    
    # 读取第一个文件获取列结构
    first_file = files_group[0]
    first_df = pd.read_csv(first_file)
    
    # 初始化累加器
    sum_data = {col: np.zeros(len(first_df)) for col in first_df.columns if col != 'frequency'}
    frequency_col = first_df['frequency'].values
    
    file_count = 0
    
    for file_path in files_group:
        try:
            df = pd.read_csv(file_path)
            
            # 验证文件结构是否一致
            if 'frequency' not in df.columns or len(df) != len(first_df):
                logger.warning(f"文件 {os.path.basename(file_path)} 结构不匹配，跳过")
                continue
            
            # 验证频率列是否一致
            if not np.allclose(df['frequency'].values, frequency_col):
                logger.warning(f"文件 {os.path.basename(file_path)} 频率轴不匹配，跳过")
                continue
            
            # 累加数据
            for col in sum_data.keys():
                if col in df.columns:
                    sum_data[col] += df[col].values
                else:
                    logger.warning(f"文件 {os.path.basename(file_path)} 缺少列 {col}")
            
            file_count += 1
#            logger.info(f"  已处理 {file_count}/{len(files_group)} 个文件: {os.path.basename(file_path)}")
            
        except Exception as e:
            logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
            continue
    
    if file_count == 0:
        logger.error("没有成功读取任何文件")
        return None, None
    
    # 计算平均值
    average_data = {'frequency': frequency_col}
    for col, sum_values in sum_data.items():
        average_data[col] = sum_values / file_count
    
    # 获取文件夹信息
    folder_name = os.path.basename(os.path.dirname(first_file))
    
    return average_data, (folder_name, file_count)

def save_average_fft(average_data, group_info, output_dir, relative_folder):
    """
    保存平均后的FFT数据
    
    参数:
    average_data: 平均后的FFT数据
    group_info: 分组信息 (文件夹名, 文件数量)
    output_dir: 输出目录
    relative_folder: 相对文件夹路径
    """
    folder_name, file_count = group_info
    
    # 创建输出目录（保持原始文件夹结构）
    output_folder = os.path.join(output_dir, relative_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    # 生成输出文件名
    output_filename = f"average_fft_{folder_name}_{file_count}files.csv"
    output_path = os.path.join(output_folder, output_filename)
    
    # 创建DataFrame并保存
    df_output = pd.DataFrame(average_data)
    df_output.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    logger.info(f"已保存平均FFT数据: {output_path}")
    return output_path

def process_folder_group(args):
    """
    处理单个文件夹组的包装函数，用于多进程
    
    参数:
    args: (folder_path, files, output_dir, relative_folder)
    """
    folder_path, files, output_dir, relative_folder = args
    
    # 在子进程中重新配置日志
    from src.utils.logging_utils import setup_logging
    project_root = Path(__file__).resolve().parent.parent.parent
    log_config_path = project_root / "config" / "logging.yaml"
    if os.path.exists(log_config_path):
        setup_logging(log_config_path)

    logger.info(f"开始处理文件夹 {relative_folder}, 共 {len(files)} 个文件")
    
    average_data, group_info = calculate_average_fft(files)
    
    if average_data is not None:
        output_path = save_average_fft(average_data, group_info, output_dir, relative_folder)
        return output_path
    else:
        logger.error(f"文件夹 {relative_folder} 组处理失败")
        return None

def main():
    config = load_config()
    
    # 设置输入和输出目录
    input_dir = config["tdms_reader_frequency_output_dir"]
    output_dir = config["tdms_reader_frequency_average_output_dir"]
    
    logger.info(f"FFT数据输入目录: {input_dir}")
    logger.info(f"平均FFT输出目录: {output_dir}")
    
    # 查找所有FFT CSV文件
    csv_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.csv') and file.startswith('FFT_'):
                csv_files.append(os.path.join(root, file))
    
    if not csv_files:
        logger.warning("未找到任何FFT CSV文件")
        return
    
    logger.info(f"找到 {len(csv_files)} 个FFT CSV文件")
    
    grouped_files = group_files_by_folder(csv_files, input_dir)

    # 准备多进程参数
    process_args = []
    for relative_folder, files in grouped_files.items():
        # 跳过空文件夹
        if len(files) == 0:
            continue
            
        process_args.append((relative_folder, files, output_dir, relative_folder))
    
    # 并行处理各文件夹组
    max_workers = min(multiprocessing.cpu_count(), len(process_args))
    logger.info(f"使用 {max_workers} 个进程并行处理")
    
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_folder_group, process_args))

    
    # 统计处理结果
    successful = [r for r in results if r is not None]
    logger.info(f"处理完成: 成功 {len(successful)}/{len(process_args)} 个文件夹组")
    
    # 生成汇总报告
    generate_summary_report(successful, output_dir)

def generate_summary_report(processed_files, output_dir):
    logger.info("========================FFT数据平均处理汇总报告===========================")
    logger.info(f"处理时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"成功处理的文件数量: {len(processed_files)}")
    logger.info("处理文件列表:")
    for i, file_path in enumerate(processed_files, 1):
        file_info = os.path.basename(file_path)
        logger.info(f"{i:2d}. {file_info}")

if __name__ == "__main__":
    main()