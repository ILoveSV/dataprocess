#====================================================================
# File Name:tdms_reader_frequency_one.py
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
import gc
import glob
from tqdm import tqdm  # 添加进度条

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

def combine_folder_data(folder_path):
    """
    合并文件夹中的所有CSV文件数据
    
    参数:
    folder_path: 文件夹路径
    
    返回:
    combined_df: 合并后的DataFrame
    """
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    csv_files = [f for f in csv_files if not os.path.basename(f).startswith("FFT_")]
    
    if not csv_files:
        logger.warning(f"文件夹 {folder_path} 中没有找到CSV文件")
        return None
    
    logger.info(f"在文件夹 {os.path.basename(folder_path)} 中找到 {len(csv_files)} 个CSV文件")
    
    # 按文件名排序确保时间顺序
    csv_files.sort(key=lambda x: os.path.basename(x))
    
    # 合并所有文件
    all_dfs = []
    for csv_file in tqdm(csv_files, desc=f"合并 {os.path.basename(folder_path)}"):
        try:
            df = pd.read_csv(csv_file)
            all_dfs.append(df)
        except Exception as e:
            logger.error(f"读取文件 {os.path.basename(csv_file)} 时出错: {str(e)}")
    
    if not all_dfs:
        logger.error(f"文件夹 {folder_path} 中没有成功读取任何文件")
        return None
    
    # 确定通道列
    channel_columns = [col for col in all_dfs[0].columns if col.startswith('channel')]
    
    # 合并数据
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # 只保留通道列（减少内存使用）
    combined_df = combined_df[channel_columns]
    
    logger.info(f"合并后数据长度: {len(combined_df)} 行")
    
    return combined_df

def process_folder(folder_path, output_base_dir, input_base_dir):
    """处理单个文件夹，合并所有CSV文件进行FFT分析"""
    try:
        logger.info(f"开始处理文件夹: {folder_path}")
        
        # 合并文件夹中的所有CSV文件
        combined_df = combine_folder_data(folder_path)
        if combined_df is None:
            return
        
        # 确定通道列
        channel_columns = combined_df.columns
        num_channels = len(channel_columns)
        
        if num_channels == 0:
            logger.warning(f"文件夹 {os.path.basename(folder_path)} 中没有找到通道列")
            return
        
        logger.info(f"处理文件夹: {os.path.basename(folder_path)}, 通道数: {num_channels}")
        
        # 初始化输出数据结构
        output_data = {}
        
        # 对每个通道进行FFT分析（整个合并信号）
        for channel in channel_columns:
            channel_idx = channel.replace("channel", "")
            
            # 获取通道数据
            channel_data = combined_df[channel].values
            
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
        relative_path = os.path.relpath(folder_path, input_base_dir)
        output_dir = os.path.join(output_base_dir, relative_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存为CSV文件
        folder_name = os.path.basename(folder_path)
        output_filename = f"FFT_{folder_name}.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        # 分块写入CSV，避免内存不足
        output_chunk_size = 100000  # 每次处理10万行
        for i in tqdm(range(0, len(df_output), output_chunk_size), 
                     desc=f"写入 {folder_name} 频域数据"):
            end_idx = min(i + output_chunk_size, len(df_output))
            chunk_df = df_output.iloc[i:end_idx]
            
            mode = 'w' if i == 0 else 'a'
            header = (i == 0)
            chunk_df.to_csv(output_path, mode=mode, header=header, index=False, encoding='utf-8-sig')
        
        logger.info(f"已处理文件夹: {folder_name} -> {output_path}")
        
        # 释放内存
        del combined_df, df_output
        gc.collect()
        
    except MemoryError:
        logger.error(f"处理文件夹 {os.path.basename(folder_path)} 时内存不足")
    except Exception as e:
        logger.error(f"处理文件夹 {os.path.basename(folder_path)} 时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

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
            "tdms_reader_frequency_one_output_dir": "D:/Lab/results/data/frequency"
        }
    
    # 设置输入数据文件夹路径和输出文件夹路径
    input_folder = config["tdms_reader_time_output_dir"]
    output_base_dir = config["tdms_reader_frequency_one_output_dir"]
    
    logger.info(f"输入数据目录: {input_folder}")
    logger.info(f"输出目录: {output_base_dir}")
    
    # 查找所有包含CSV文件的子文件夹
    folders_to_process = []
    for root, dirs, files in os.walk(input_folder):
        # 检查该文件夹是否有CSV文件（排除FFT结果文件）
        csv_files = [f for f in files if f.endswith('.csv') and not f.startswith('FFT_')]
        if csv_files:
            folders_to_process.append(root)
    
    if not folders_to_process:
        logger.warning("未找到任何包含CSV文件的文件夹")
        return
    
    logger.info(f"找到 {len(folders_to_process)} 个包含CSV文件的文件夹")
    
    # 处理文件夹
    for folder_path in folders_to_process:
        process_folder(folder_path, output_base_dir, input_folder)
    
    logger.info("所有文件夹处理完成")

if __name__ == "__main__":
    main()