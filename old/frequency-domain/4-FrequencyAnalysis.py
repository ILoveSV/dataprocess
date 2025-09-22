#====================================================================
# File Name: 4-FrequencyAnalysis.py
# Project Name:Data Process
# Description:
# 1、读取之前生成的Excel文件（包含FFT结果）
# 2、进行常规频域分析：幅度谱、相位谱、峰值检测、带宽计算、信噪比计算
# 3、生成相关图像并保存
#====================================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import os
import glob
import matplotlib.font_manager as fm

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

def analyze_discrete_data(frequencies, magnitudes, output_path, channel_name, file_num):
    """分析离散的FFT数据点"""
    # 转换为线性频率
    linear_freq = 10**frequencies
    
    # 绘制离散点图
    plt.figure(figsize=(12, 8))
    
    # 绘制幅度点
    plt.subplot(2, 1, 1)
    plt.scatter(linear_freq, magnitudes, color='blue', s=50, label='FFT Points')
    
    # 标记前5个最大点
    if len(magnitudes) > 0:
        top5_idx = np.argsort(magnitudes)[-5:]
        plt.scatter(linear_freq[top5_idx], magnitudes[top5_idx], color='red', s=100, label='Top 5 Points')
        
        # 标注前5个点的频率和幅度
        for i, idx in enumerate(top5_idx):
            plt.annotate(f'f={linear_freq[idx]:.2e} Hz\nA={magnitudes[idx]:.2e}', 
                        xy=(linear_freq[idx], magnitudes[idx]),
                        xytext=(linear_freq[idx]*1.1, magnitudes[idx]*0.9),
                        arrowprops=dict(arrowstyle='->', color='red', alpha=0.7))
    
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title(f'Discrete FFT Points - {channel_name} - File {file_num}')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.gca().xaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    plt.gca().ticklabel_format(style='sci', axis='x', scilimits=(0,0))
    
    # 绘制频率分布直方图
    plt.subplot(2, 1, 2)
    if len(linear_freq) > 1:
        plt.hist(linear_freq, bins=min(10, len(linear_freq)), alpha=0.7, color='green')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Count')
        plt.title(f'Frequency Distribution - {channel_name} - File {file_num}')
        plt.grid(True, alpha=0.3)
        plt.gca().xaxis.set_major_formatter(ScalarFormatter(useMathText=True))
        plt.gca().ticklabel_format(style='sci', axis='x', scilimits=(0,0))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    # 计算统计信息
    stats = {}
    if len(linear_freq) > 0:
        stats['num_points'] = len(linear_freq)
        stats['max_frequency'] = np.max(linear_freq)
        stats['min_frequency'] = np.min(linear_freq)
        stats['mean_frequency'] = np.mean(linear_freq)
        stats['max_magnitude'] = np.max(magnitudes)
        stats['min_magnitude'] = np.min(magnitudes)
        stats['mean_magnitude'] = np.mean(magnitudes)
        
        # 如果有多个点，计算频率和幅度的标准差
        if len(linear_freq) > 1:
            stats['std_frequency'] = np.std(linear_freq)
            stats['std_magnitude'] = np.std(magnitudes)
        else:
            stats['std_frequency'] = 0
            stats['std_magnitude'] = 0
    
    return stats

def analyze_excel_file(excel_path, output_dir, channel_name):
    """分析单个Excel文件"""
    # 读取Excel文件
    df = pd.read_excel(excel_path)
    
    # 提取文件名信息
    file_name = os.path.basename(excel_path)
    base_name = file_name.replace('.xlsx', '')
    
    # 创建输出子目录
    channel_output_dir = os.path.join(output_dir, base_name)
    os.makedirs(channel_output_dir, exist_ok=True)
    
    # 获取所有文件列
    file_cols = [col for col in df.columns if 'File' in col]
    file_numbers = sorted(set([int(col.split('_')[0].replace('File', '')) for col in file_cols]))
    
    # 存储所有统计信息
    all_stats = []
    
    # 处理每个文件的数据
    for file_num in file_numbers:
        # 提取频率和幅度数据
        freq_col = f"File{file_num}_Freq"
        mag_col = f"File{file_num}_Mag"
        
        if freq_col not in df.columns or mag_col not in df.columns:
            continue
            
        frequencies = df[freq_col].dropna().values
        magnitudes = df[mag_col].dropna().values
        
        # 跳过没有足够数据点的情况
        if len(frequencies) < 1 or len(magnitudes) < 1:
            print(f"跳过 {channel_name} - 文件 {file_num}: 数据点不足")
            continue
        
        # 分析离散数据
        output_path = os.path.join(channel_output_dir, f'discrete_analysis_file_{file_num}.png')
        stats = analyze_discrete_data(frequencies, magnitudes, output_path, channel_name, file_num)
        
        # 添加文件信息到统计
        stats['file_number'] = file_num
        stats['channel_name'] = channel_name
        all_stats.append(stats)
        
        print(f"处理完成: {channel_name} - 文件 {file_num} - 数据点数量: {len(frequencies)}")
    
    # 保存统计信息
    if all_stats:
        stats_df = pd.DataFrame(all_stats)
        stats_df.to_csv(os.path.join(channel_output_dir, 'statistics_summary.csv'), index=False)
    
    return True

def create_summary_plots(output_dir):
    """创建所有通道的汇总图表"""
    # 查找所有统计文件
    stats_files = glob.glob(os.path.join(output_dir, "**", "statistics_summary.csv"), recursive=True)
    
    if not stats_files:
        print("未找到任何统计文件！")
        return
    
    # 读取所有统计文件
    all_stats = []
    for stats_file in stats_files:
        df = pd.read_csv(stats_file)
        # 添加通道名称
        channel_name = os.path.basename(os.path.dirname(stats_file)).replace('_analysis', '')
        df['channel'] = channel_name
        all_stats.append(df)
    
    if not all_stats:
        return
        
    # 合并所有数据
    combined_df = pd.concat(all_stats, ignore_index=True)
    
    # 创建汇总目录
    summary_dir = os.path.join(output_dir, "summary_plots")
    os.makedirs(summary_dir, exist_ok=True)
    
    # 绘制各通道最大幅度随文件数的变化
    plt.figure(figsize=(12, 8))
    for channel in combined_df['channel'].unique():
        channel_data = combined_df[combined_df['channel'] == channel]
        plt.plot(channel_data['file_number'], channel_data['max_magnitude'], 
                marker='o', label=channel, linewidth=2)
    
    plt.xlabel('File Number')
    plt.ylabel('Max Magnitude')
    plt.title('Max Magnitude by Channel and File Number')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(summary_dir, 'max_magnitude_by_channel.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 绘制各通道平均频率随文件数的变化
    plt.figure(figsize=(12, 8))
    for channel in combined_df['channel'].unique():
        channel_data = combined_df[combined_df['channel'] == channel]
        plt.plot(channel_data['file_number'], channel_data['mean_frequency'], 
                marker='s', label=channel, linewidth=2)
    
    plt.xlabel('File Number')
    plt.ylabel('Mean Frequency (Hz)')
    plt.title('Mean Frequency by Channel and File Number')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.gca().yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    plt.gca().ticklabel_format(style='sci', axis='y', scilimits=(0,0))
    plt.savefig(os.path.join(summary_dir, 'mean_frequency_by_channel.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 绘制各通道数据点数量随文件数的变化
    plt.figure(figsize=(12, 8))
    for channel in combined_df['channel'].unique():
        channel_data = combined_df[combined_df['channel'] == channel]
        plt.plot(channel_data['file_number'], channel_data['num_points'], 
                marker='^', label=channel, linewidth=2)
    
    plt.xlabel('File Number')
    plt.ylabel('Number of Data Points')
    plt.title('Number of Data Points by Channel and File Number')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(summary_dir, 'num_points_by_channel.png'), dpi=300, bbox_inches='tight')
    plt.close()

def main():
    """主函数"""
    # 设置主文件夹路径
    main_folder = r"D:\Lab\Water\C6.25\30hz-close"
    output_dir = os.path.join(main_folder, "frequency_analysis_results")
    os.makedirs(output_dir, exist_ok=True)
    
    # 查找所有Excel文件
    excel_files = glob.glob(os.path.join(main_folder, "**", "*_analysis.xlsx"), recursive=True)
    
    if not excel_files:
        print("未找到任何Excel分析文件！")
        return
    
    print(f"找到 {len(excel_files)} 个Excel分析文件")
    
    # 处理每个Excel文件
    for excel_path in excel_files:
        # 提取通道名称
        file_name = os.path.basename(excel_path)
        channel_name = file_name.replace('_analysis.xlsx', '')
        
        print(f"\n处理通道: {channel_name}")
        
        # 分析Excel文件
        try:
            analyze_excel_file(excel_path, output_dir, channel_name)
            print(f"完成处理: {channel_name}")
        except Exception as e:
            print(f"处理文件 {excel_path} 时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # 创建汇总图表
    print("\n创建汇总图表...")
    create_summary_plots(output_dir)
    
    print(f"\n所有分析完成！结果保存在: {output_dir}")

if __name__ == "__main__":
    print("=" * 60)
    print("开始离散数据频域分析")
    print("=" * 60)
    main()