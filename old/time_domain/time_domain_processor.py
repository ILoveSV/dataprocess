#====================================================================
# File Name: time_domain_processor.py
# Project Name: 水下目标电荷探测数据分析
# Description:
# 1、时域信号预处理：提供去除直流分量、滤波等预处理功能
# 2、信号滤波：实现带通和低通滤波器，可自定义截止频率和滤波器阶数
# 3、信号标准化：提供零均值、单位方差的信号标准化处理
# 4、峰值检测：基于阈值和最小距离约束的峰值检测算法
# 5、包络提取：支持希尔伯特变换和RMS两种方法计算信号包络
# 6、非平稳信号处理：专门针对水下目标电荷信号的非平稳特性设计
#====================================================================
"""
时域分析核心处理模块
功能：对时域信号进行预处理和基本分析
"""
import numpy as np
from scipy import signal
from scipy.stats import kurtosis, skew

def remove_dc_component(data):
    """
    去除信号的直流分量
    
    参数:
        data (numpy.ndarray): 输入信号
        
    返回:
        numpy.ndarray: 去除直流分量后的信号
    """
    return data - np.mean(data)

def apply_bandpass_filter(data, lowcut, highcut, fs, order=4):
    """
    应用带通滤波器
    
    参数:
        data (numpy.ndarray): 输入信号
        lowcut (float): 低频截止频率
        highcut (float): 高频截止频率
        fs (float): 采样频率
        order (int): 滤波器阶数
        
    返回:
        numpy.ndarray: 滤波后的信号
    """
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype='band')
    return signal.filtfilt(b, a, data)

def apply_lowpass_filter(data, cutoff, fs, order=4):
    """
    应用低通滤波器
    
    参数:
        data (numpy.ndarray): 输入信号
        cutoff (float): 截止频率
        fs (float): 采样频率
        order (int): 滤波器阶数
        
    返回:
        numpy.ndarray: 滤波后的信号
    """
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = signal.butter(order, normal_cutoff, btype='low')
    return signal.filtfilt(b, a, data)

def normalize_signal(data):
    """
    标准化信号（零均值，单位方差）
    
    参数:
        data (numpy.ndarray): 输入信号
        
    返回:
        numpy.ndarray: 标准化后的信号
    """
    return (data - np.mean(data)) / np.std(data)

def detect_peaks(data, threshold=0.5, min_distance=100):
    """
    检测信号中的峰值
    
    参数:
        data (numpy.ndarray): 输入信号
        threshold (float): 峰值检测阈值（相对于最大值）
        min_distance (int): 峰值之间的最小距离（样本点）
        
    返回:
        tuple: (峰值位置, 峰值高度)
    """
    peaks, properties = signal.find_peaks(
        data, 
        height=threshold * np.max(np.abs(data)), 
        distance=min_distance
    )
    return peaks, properties['peak_heights']

def calculate_envelope(data, method='hilbert'):
    """
    计算信号的包络线
    
    参数:
        data (numpy.ndarray): 输入信号
        method (str): 包络计算方法 ('hilbert' 或 'rms')
        
    返回:
        numpy.ndarray: 包络信号
    """
    if method == 'hilbert':
        analytic_signal = signal.hilbert(data)
        return np.abs(analytic_signal)
    elif method == 'rms':
        # 使用移动窗口RMS计算包络
        window_size = min(100, len(data) // 10)
        return np.sqrt(np.convolve(data**2, np.ones(window_size)/window_size, mode='same'))
    else:
        raise ValueError("method 必须是 'hilbert' 或 'rms'")