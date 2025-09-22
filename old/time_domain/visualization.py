#====================================================================
# File Name: visualization.py
# Project Name: 水下目标电荷探测数据分析
# Description:
# 1、时域信号可视化：绘制原始时域信号波形图，支持自定义时间轴
# 2、包络显示：同时显示信号及其包络线，便于观察信号幅度变化
# 3、峰值标注：在信号波形上标注检测到的峰值位置和高度
# 4、多信号对比：支持多个信号在同一图表中的对比显示
# 5、高质量输出：生成高分辨率图像文件，适合学术论文和报告使用
# 6、自定义配置：提供丰富的图表标题、标签和样式配置选项
#====================================================================
"""
数据可视化模块
功能：绘制时域信号的各种图形
"""
import matplotlib.pyplot as plt
import numpy as np

def plot_time_series(data, fs, title="时域信号", save_path=None):
    """
    绘制时域信号波形图
    
    参数:
        data (numpy.ndarray): 输入信号
        fs (float): 采样频率
        title (str): 图表标题
        save_path (str): 保存路径，如果为None则不保存
    """
    time_axis = np.arange(len(data)) / fs
    
    plt.figure(figsize=(12, 6))
    plt.plot(time_axis, data)
    plt.title(title)
    plt.xlabel('时间 (秒)')
    plt.ylabel('幅度')
    plt.grid(True)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    plt.show()

def plot_with_envelope(data, fs, title="信号与包络", save_path=None):
    """
    绘制信号及其包络线
    
    参数:
        data (numpy.ndarray): 输入信号
        fs (float): 采样频率
        title (str): 图表标题
        save_path (str): 保存路径，如果为None则不保存
    """
    from time_domain_processor import calculate_envelope
    
    time_axis = np.arange(len(data)) / fs
    envelope = calculate_envelope(data)
    
    plt.figure(figsize=(12, 6))
    plt.plot(time_axis, data, label='原始信号')
    plt.plot(time_axis, envelope, 'r-', label='包络线', linewidth=2)
    plt.title(title)
    plt.xlabel('时间 (秒)')
    plt.ylabel('幅度')
    plt.legend()
    plt.grid(True)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    plt.show()

def plot_peak_detection(data, fs, threshold=0.5, min_distance=100, title="峰值检测", save_path=None):
    """
    绘制信号及其检测到的峰值
    
    参数:
        data (numpy.ndarray): 输入信号
        fs (float): 采样频率
        threshold (float): 峰值检测阈值
        min_distance (int): 峰值之间的最小距离
        title (str): 图表标题
        save_path (str): 保存路径，如果为None则不保存
    """
    from time_domain_processor import detect_peaks
    
    time_axis = np.arange(len(data)) / fs
    peaks, peak_heights = detect_peaks(data, threshold, min_distance)
    
    plt.figure(figsize=(12, 6))
    plt.plot(time_axis, data, label='原始信号')
    plt.plot(time_axis[peaks], data[peaks], 'ro', label='检测到的峰值')
    plt.title(title)
    plt.xlabel('时间 (秒)')
    plt.ylabel('幅度')
    plt.legend()
    plt.grid(True)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    plt.show()

def plot_multiple_signals(signals_list, fs, titles=None, super_title="多信号对比", save_path=None):
    """
    绘制多个信号的对比图
    
    参数:
        signals_list (list): 信号列表
        fs (float): 采样频率
        titles (list): 每个子图的标题列表
        super_title (str): 总标题
        save_path (str): 保存路径，如果为None则不保存
    """
    n_signals = len(signals_list)
    
    fig, axes = plt.subplots(n_signals, 1, figsize=(12, 4 * n_signals))
    if n_signals == 1:
        axes = [axes]
    
    for i, (data, ax) in enumerate(zip(signals_list, axes)):
        time_axis = np.arange(len(data)) / fs
        ax.plot(time_axis, data)
        if titles and i < len(titles):
            ax.set_title(titles[i])
        ax.set_xlabel('时间 (秒)')
        ax.set_ylabel('幅度')
        ax.grid(True)
    
    plt.suptitle(super_title)
    plt.tight_layout(rect=[0, 0, 1, 0.96])  # 为总标题留出空间
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    plt.show()