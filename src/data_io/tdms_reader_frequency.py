import numpy as np
import pandas as pd
import os
from pathlib import Path
import yaml
import logging
import re
import gc  # 垃圾回收
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import json

logger = logging.getLogger('data_process')

def load_config():
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config

def perform_fft_analysis(data, sampling_rate=200000):  # 修改为正确的200kHz采样率
    """
    对数据进行FFT分析，返回频率、幅度和相位
    
    参数:
    data: 输入数据数组
    sampling_rate: 采样率，默认为200kHz
    
    返回:
    freqs: 频率数组
    amplitude: 幅度数组
    phase: 相位数组
    """
    n = len(data)
    
    # 执行FFT
    fft_result = np.fft.fft(data)
    
    # 计算频率轴
    freqs = np.fft.fftfreq(n, 1/sampling_rate)
    
    # 计算幅度和相位
    amplitude = np.abs(fft_result) / n  # 归一化
    phase = np.angle(fft_result)
    
    # 只返回正频率部分
    positive_freq_idx = freqs > 0
    return freqs[positive_freq_idx], amplitude[positive_freq_idx], phase[positive_freq_idx]

def process_csv_file(csv_path, output_base_dir, input_base_dir):
    """处理单个CSV文件，进行FFT分析并保存结果"""
    try:
        logger.info(f"开始处理文件: {csv_path}")
        
        # 读取对应的元数据文件获取真实采样率
        metadata_path = csv_path.replace('.csv', '_metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            sampling_rate = metadata['sampling_rate_hz']  # 从元数据获取真实采样率
            logger.info(f"使用元数据采样率: {sampling_rate} Hz")
        else:
            logger.warning(f"未找到元数据文件 {metadata_path}，使用默认采样率200kHz")
            sampling_rate = 200000  # 默认采样率
        
        # 读取整个CSV文件
        df = pd.read_csv(csv_path)
        logger.info(f"成功读取文件: {os.path.basename(csv_path)}, 数据长度: {len(df)}")
        
        # 确定通道列
        channel_columns = [col for col in df.columns if col.startswith('channel')]
        num_channels = len(channel_columns)
        
        if num_channels == 0:
            logger.warning(f"文件 {os.path.basename(csv_path)} 中没有找到通道列")
            return
        
        logger.info(f"处理文件: {os.path.basename(csv_path)}, 通道数: {num_channels}")
        
        # 初始化输出数据结构
        output_data = {}
        
        # 对每个通道进行FFT分析（整个信号）
        for channel in channel_columns:
            channel_idx = channel.replace("channel", "")
            
            # 获取通道数据
            channel_data = df[channel].values
            
            # 执行FFT分析
            freqs, amplitude, phase = perform_fft_analysis(channel_data, sampling_rate)
            
            # 如果是第一个通道，保存频率数组
            if not output_data:
                output_data['frequency'] = freqs
            
            # 保存幅度和相位
            output_data[f'amplitude{channel_idx}'] = amplitude
            output_data[f'phase{channel_idx}'] = phase
        
        # 创建输出数据框
        df_output = pd.DataFrame(output_data)
        
        # 创建输出目录结构
        relative_path = os.path.relpath(os.path.dirname(csv_path), input_base_dir)
        output_dir = os.path.join(output_base_dir, relative_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存为CSV文件
        input_filename = os.path.basename(csv_path)
        output_filename = f"FFT_{input_filename}"
        output_path = os.path.join(output_dir, output_filename)
        
        # 分块写入CSV，避免内存不足
        output_chunk_size = 100000  # 每次处理10万行
        for i in range(0, len(df_output), output_chunk_size):
            end_idx = min(i + output_chunk_size, len(df_output))
            chunk_df = df_output.iloc[i:end_idx]
            
            mode = 'w' if i == 0 else 'a'
            header = (i == 0)
            chunk_df.to_csv(output_path, mode=mode, header=header, index=False, encoding='utf-8-sig')
            
            logger.info(f"  已写入 {end_idx}/{len(df_output)} 行FFT数据")
        
        logger.info(f"已处理: {input_filename} -> {output_path}")
        
        # 释放内存
        del df, df_output
        gc.collect()
        
    except MemoryError:
        logger.error(f"处理文件 {os.path.basename(csv_path)} 时内存不足，文件过大")
    except Exception as e:
        logger.error(f"处理文件 {os.path.basename(csv_path)} 时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def process_csv_file_wrapper(args):
    """包装函数，用于多进程调用"""
    csv_path, output_base_dir, input_base_dir = args
    # 在子进程中重新配置日志
    from src.utils.logging_utils import setup_logging
    import os
    project_root = Path(__file__).resolve().parent.parent.parent
    log_config_path = project_root / "config" / "logging.yaml"
    if os.path.exists(log_config_path):
        setup_logging(log_config_path)
    return process_csv_file(csv_path, output_base_dir, input_base_dir)

def process_csv_files_parallel(csv_files, output_base_dir, input_base_dir):
    """并行处理CSV文件"""
    max_workers = multiprocessing.cpu_count()
    params = [(csv_file, output_base_dir, input_base_dir) for csv_file in csv_files]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(process_csv_file_wrapper, params))

def main():
    config = load_config()
    
    if not config:
        logger.error("无法加载配置文件")
        return
    
    # 设置输入数据文件夹路径和输出文件夹路径
    input_folder = config["tdms_reader_time_output_dir"]
    output_base_dir = config["tdms_reader_frequency_output_dir"]
    
    logger.info(f"输入数据目录: {input_folder}")
    logger.info(f"输出目录: {output_base_dir}")
    
    # 查找所有CSV文件
    csv_files = []
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.endswith('.csv') and not file.startswith('FFT_'):
                csv_files.append(os.path.join(root, file))
    
    if not csv_files:
        logger.warning("未找到任何CSV文件")
        return
    
    logger.info(f"找到 {len(csv_files)} 个CSV文件")
    
    # 处理文件
    logger.info("开始并行处理文件...")
    process_csv_files_parallel(csv_files, output_base_dir, input_folder)
    
    logger.info("所有文件处理完成")

if __name__ == "__main__":
    main()