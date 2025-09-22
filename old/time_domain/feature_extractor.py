#====================================================================
# File Name: feature_extractor.py
# Project Name: 水下目标电荷探测数据分析
# Description:
# 1、时域特征提取：从时域信号中提取多种统计特征用于目标识别
# 2、基本统计量：包括均值、标准差、方差、RMS、峰值等基础特征
# 3、形状特征：计算偏度、峰度等描述信号分布形状的特征
# 4、能量特征：提取信号能量、峰值因子等与能量相关的特征
# 5、高级特征：包括过零率、自相关特征、包络统计等高级时域特征
# 6、特征整合：将所有提取的特征整合为结构化数据，便于后续分析
#====================================================================
"""
时域特征提取模块
功能：从时域信号中提取各种统计特征
"""
import numpy as np
from scipy.stats import kurtosis, skew, entropy

def extract_basic_features(data):
    """
    提取基本时域统计特征
    
    参数:
        data (numpy.ndarray): 输入信号
        
    返回:
        dict: 包含各种时域特征的字典
    """
    features = {}
    
    # 基本统计量
    features['mean'] = np.mean(data)
    features['std'] = np.std(data)
    features['var'] = np.var(data)
    features['rms'] = np.sqrt(np.mean(data**2))
    features['peak'] = np.max(np.abs(data))
    features['peak_to_peak'] = np.ptp(data)
    
    # 形状特征
    features['skewness'] = skew(data)
    features['kurtosis'] = kurtosis(data)
    
    # 能量特征
    features['energy'] = np.sum(data**2)
    
    # 幅值特征
    features['crest_factor'] = features['peak'] / features['rms'] if features['rms'] != 0 else 0
    features['clearance_factor'] = features['peak'] / (np.mean(np.sqrt(np.abs(data)))**2) if np.mean(np.sqrt(np.abs(data))) != 0 else 0
    features['impulse_factor'] = features['peak'] / np.mean(np.abs(data)) if np.mean(np.abs(data)) != 0 else 0
    features['shape_factor'] = features['rms'] / np.mean(np.abs(data)) if np.mean(np.abs(data()) != 0 else 0
    
    return features

def extract_advanced_features(data, fs):
    """
    提取高级时域特征
    
    参数:
        data (numpy.ndarray): 输入信号
        fs (float): 采样频率
        
    返回:
        dict: 包含高级时域特征的字典
    """
    features = {}
    
    # 过零率
    zero_crossings = np.where(np.diff(np.sign(data)))[0]
    features['zero_crossing_rate'] = len(zero_crossings) / (len(data) / fs) if len(data) > 0 else 0
    
    # 自相关特征
    autocorr = np.correlate(data, data, mode='full')
    autocorr = autocorr[autocorr.size // 2:]
    features['autocorr_peak'] = np.max(autocorr) if len(autocorr) > 0 else 0
    
    # 包络特征
    envelope = np.abs(signal.hilbert(data))
    features['envelope_mean'] = np.mean(envelope)
    features['envelope_std'] = np.std(envelope)
    
    return features

def extract_all_features(data, fs, channel_name, file_index):
    """
    提取所有时域特征
    
    参数:
        data (numpy.ndarray): 输入信号
        fs (float): 采样频率
        channel_name (str): 通道名称
        file_index (int): 文件索引
        
    返回:
        dict: 包含所有特征的字典，包含通道和文件信息
    """
    features = {
        'channel': channel_name,
        'file_index': file_index,
        'length': len(data)
    }
    
    # 添加基本特征
    basic_features = extract_basic_features(data)
    features.update(basic_features)
    
    # 添加高级特征
    advanced_features = extract_advanced_features(data, fs)
    features.update(advanced_features)
    
    return features