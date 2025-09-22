#====================================================================
# File Name:tdms_reader_frequency.py
# Project Name:dataprocess
# Description:
# 1、读取时域CSV文件：遍历主文件夹下的子文件夹
# 2、对每个通道的数据进行FFT分析，得到频率、幅度和相位信息
# 3、生成csv文件，文件名格式为FFT_原文件名
# 4、csv文件结构：
#  列名	       数据类型	                   描述	                         示例
#  frequency	  数值 (float)	        频率值，单位Hz	                 1000.0
#  amplitude1	数值 (float)	    通道1的幅度数据	                0.12345
#  phase1	    数值 (float)	     通道1的相位数据，单位弧度	        -1.23456
#  amplitude2	数值 (float)	    通道2的幅度数据	                0.23456
#  phase2	    数值 (float)	     通道2的相位数据，单位弧度	         0.34567
#  ...	        ...	                       ...	                          ...
#  amplitudeN	数值 (float)	通道N的幅度数据，N最大为16	          2.34567
#  phaseN	    数值 (float)	 通道N的相位数据，单位弧度	          -0.45678
# 5、采样率：500kHz
#====================================================================

import numpy as np
import pandas as pd
import os
from pathlib import Path
import yaml
import logging
import re
import gc  # 垃圾回收

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

def perform_fft_analysis(data, sampling_rate=500000):
    """
    对数据进行FFT分析，返回频率、幅度和相位
    
    参数:
    data: 输入数据数组
    sampling_rate: 采样率，默认为500kHz
    
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
        
        # 读取整个CSV文件（不再分块）
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
            freqs, amplitude, phase = perform_fft_analysis(channel_data)
            
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

def process_csv_files_parallel(csv_files, output_base_dir, input_base_dir):
    """处理CSV文件（可选择并行或串行）"""
    # 根据文件大小决定处理方式
    large_file_threshold = 500 * 1024 * 1024  # 500MB
    
    for csv_file in csv_files:
        file_size = os.path.getsize(csv_file)
        
        if file_size > large_file_threshold:
            logger.warning(f"文件 {os.path.basename(csv_file)} 过大 ({file_size/1024/1024:.2f}MB), 可能需要较长时间处理")
        
        process_csv_file(csv_file, output_base_dir, input_base_dir)

def main():
    """主函数"""
    # 设置日志级别
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 加载配置文件
    config = load_config()
    
    if not config:
        logger.warning("无法加载配置文件，使用默认路径")
        config = {
            "tdms_reader_time_output_dir": "D:/Lab/results/data/time",
            "tdms_reader_frequency_output_dir": "D:/Lab/results/data/frequency"
        }
    
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
    logger.info("开始处理文件...")
    process_csv_files_parallel(csv_files, output_base_dir, input_folder)
    
    logger.info("所有文件处理完成")

if __name__ == "__main__":
    main()