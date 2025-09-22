#====================================================================
# File Name: main_time_analysis.py
# Project Name: 水下目标电荷探测数据分析
# Description:
# 1、主控程序：协调各模块完成完整的时域分析流程
# 2、文件夹遍历：自动遍历主文件夹下的所有子文件夹进行处理
# 3、增量式处理：支持处理指定数量的文件，避免内存溢出
# 4、并行处理支持：设计为可扩展为多通道并行处理架构
# 5、结果导出：将所有提取的时域特征保存为Excel格式，便于后续分析
# 6、进度显示：实时显示处理进度和状态，提供友好的用户反馈
# 7、异常处理：具备完善的错误捕获和处理机制，确保程序稳定运行
#====================================================================
"""
主程序：单通道时域分析
功能：协调各模块完成时域分析任务
"""
import os
import pandas as pd
import numpy as np
from tdms_reader import get_sorted_tdms_files, read_channel_data, read_multiple_files_data
from time_domain_processor import remove_dc_component, apply_bandpass_filter, detect_peaks
from feature_extractor import extract_all_features
from visualization import plot_time_series, plot_with_envelope, plot_peak_detection

def analyze_single_channel_time_domain(main_folder, channel_name, output_folder=None, max_files=20):
    """
    分析单个通道的时域特性
    
    参数:
        main_folder (str): 主文件夹路径
        channel_name (str): 通道名称，如"通道1"
        output_folder (str): 输出文件夹路径
        max_files (int): 最大处理文件数
        
    返回:
        pandas.DataFrame: 包含所有提取特征的DataFrame
    """
    # 设置输出文件夹
    if output_folder is None:
        output_folder = os.path.join(main_folder, "time_domain_analysis")
    os.makedirs(output_folder, exist_ok=True)
    
    # 获取所有子文件夹
    subfolders = []
    for item in os.listdir(main_folder):
        subfolder_path = os.path.join(main_folder, item)
        if os.path.isdir(subfolder_path):
            subfolders.append(subfolder_path)
    
    if not subfolders:
        raise ValueError(f"主文件夹 {main_folder} 中没有子文件夹")
    
    print(f"找到 {len(subfolders)} 个子文件夹")
    
    # 存储所有特征
    all_features = []
    
    # 处理每个子文件夹
    for subfolder in subfolders:
        folder_name = os.path.basename(subfolder)
        print(f"\n处理子文件夹: {folder_name}")
        
        try:
            # 获取排序后的TDMS文件
            tdms_files = get_sorted_tdms_files(subfolder)
            files_to_process = tdms_files[:min(max_files, len(tdms_files))]
            print(f"处理 {len(files_to_process)} 个文件")
            
            # 处理每个文件
            for i, file_path in enumerate(files_to_process):
                print(f"处理文件 {i+1}/{len(files_to_process)}: {os.path.basename(file_path)}")
                
                # 读取数据
                data = read_channel_data(file_path, channel_name)
                
                # 预处理
                sampling_frequency = 200000  # 根据实际情况调整采样频率
                data_no_dc = remove_dc_component(data)
                # 可选的带通滤波
                # filtered_data = apply_bandpass_filter(data_no_dc, lowcut=100, highcut=10000, fs=sampling_frequency)
                
                # 提取特征
                features = extract_all_features(
                    data_no_dc, 
                    sampling_frequency, 
                    channel_name, 
                    i+1
                )
                features['folder'] = folder_name
                features['file'] = os.path.basename(file_path)
                
                all_features.append(features)
                
                # 可视化（可选，可注释掉以加快处理速度）
                if i == 0:  # 只对第一个文件进行可视化
                    plot_save_path = os.path.join(output_folder, f"{folder_name}_{channel_name}_time_series.png")
                    plot_time_series(
                        data_no_dc[:min(100000, len(data_no_dc))],  # 只绘制前100000个点
                        sampling_frequency,
                        title=f"{folder_name} - {channel_name} - 时域信号",
                        save_path=plot_save_path
                    )
                    
                    envelope_save_path = os.path.join(output_folder, f"{folder_name}_{channel_name}_envelope.png")
                    plot_with_envelope(
                        data_no_dc[:min(100000, len(data_no_dc))],
                        sampling_frequency,
                        title=f"{folder_name} - {channel_name} - 信号与包络",
                        save_path=envelope_save_path
                    )
                    
                    peaks_save_path = os.path.join(output_folder, f"{folder_name}_{channel_name}_peaks.png")
                    plot_peak_detection(
                        data_no_dc[:min(100000, len(data_no_dc))],
                        sampling_frequency,
                        title=f"{folder_name} - {channel_name} - 峰值检测",
                        save_path=peaks_save_path
                    )
        
        except Exception as e:
            print(f"处理子文件夹 {folder_name} 时出错: {str(e)}")
            continue
    
    # 将特征保存到Excel
    df = pd.DataFrame(all_features)
    excel_path = os.path.join(output_folder, f"{channel_name}_time_domain_features.xlsx")
    df.to_excel(excel_path, index=False)
    print(f"\n特征已保存到: {excel_path}")
    
    return df

if __name__ == "__main__":
    # 配置参数
    MAIN_FOLDER = r"D:\Lab\Water\D6.25"  # 替换为您的实际路径
    CHANNEL_NAME = "通道1"  # 要分析的通道名称
    OUTPUT_FOLDER = None  # 使用默认输出文件夹
    MAX_FILES = 20  # 每个子文件夹最多处理的文件数
    
    print("开始单通道时域分析")
    print("=" * 50)
    
    # 执行分析
    features_df = analyze_single_channel_time_domain(
        MAIN_FOLDER, 
        CHANNEL_NAME, 
        OUTPUT_FOLDER, 
        MAX_FILES
    )
    
    print("\n分析完成!")
    print("=" * 50)