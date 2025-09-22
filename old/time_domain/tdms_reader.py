#====================================================================
# File Name: tdms_reader.py
# Project Name: 水下目标电荷探测数据分析
# Description:
# 1、TDMS文件读取工具模块：提供从TDMS文件中读取数据的通用功能
# 2、文件排序功能：按文件名末尾数字排序，确保时间序列连续性
# 3、多文件数据合并：支持从多个TDMS文件中读取并合并指定通道的数据
# 4、异常处理：包含完善的错误检测和处理机制，确保数据读取的可靠性
# 5、通道数据提取：能够从TDMS文件组中提取指定通道的原始电压数据
#====================================================================
"""
TDMS 文件读取工具模块
功能：读取TDMS文件，提取指定通道的数据
"""
import numpy as np
from nptdms import TdmsFile
import os
import re

def get_sorted_tdms_files(folder_path):
    """
    获取指定文件夹中按数字排序的TDMS文件列表
    
    参数:
        folder_path (str): 文件夹路径
        
    返回:
        list: 排序后的TDMS文件路径列表
    """
    tdms_files = [f for f in os.listdir(folder_path) if f.endswith('.tdms')]
    if not tdms_files:
        raise ValueError(f"文件夹 {folder_path} 中没有TDMS文件")
    
    # 使用正则表达式提取文件名中的最后一个数字作为排序依据
    def extract_number(filename):
        numbers = re.findall(r'\d+', filename)
        return int(numbers[-1]) if numbers else 0
    
    tdms_files.sort(key=extract_number)
    return [os.path.join(folder_path, f) for f in tdms_files]

def read_channel_data(tdms_file_path, channel_name):
    """
    从TDMS文件中读取指定通道的数据
    
    参数:
        tdms_file_path (str): TDMS文件路径
        channel_name (str): 通道名称，如"通道1"
        
    返回:
        numpy.ndarray: 通道数据数组
    """
    try:
        tdms_file = TdmsFile(tdms_file_path)
        
        # 获取所有可用组
        groups = tdms_file.groups()
        if not groups:
            raise ValueError(f"文件 {os.path.basename(tdms_file_path)} 中没有找到任何组")
        
        # 使用第一个组（通常只有一个组）
        group = groups[0]
        
        if channel_name not in group:
            raise ValueError(f"组 {group.name} 中不存在通道 {channel_name}")
            
        return group[channel_name][:]
        
    except Exception as e:
        raise Exception(f"读取文件 {os.path.basename(tdms_file_path)} 出错: {str(e)}")

def read_multiple_files_data(file_paths, channel_name):
    """
    从多个TDMS文件中读取指定通道的数据并合并
    
    参数:
        file_paths (list): TDMS文件路径列表
        channel_name (str): 通道名称
        
    返回:
        numpy.ndarray: 合并后的数据数组
    """
    all_data = []
    for file_path in file_paths:
        data = read_channel_data(file_path, channel_name)
        all_data.extend(data)
    
    return np.array(all_data)