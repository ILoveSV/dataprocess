#====================================================================
# File Name:1-DFT2.py
# Project Name:Data Process
# Description:
# 1、读取TDMS文件：遍历主文件夹下的子文件夹，按文件名末尾数字排序（确保时间序列连续性）
# 2、"通道1"到"通道16"，增量式数据合并：从第1个文件开始，逐步追加后续文件数据
# 3、FFT快速傅里叶变换,得到频率和对应振幅
# 4、Excel结果文件：奇数列存储对数变换后的频率，偶数列存储幅度
#====================================================================
import numpy as np
from scipy.fft import fft, fftfreq
from nptdms import TdmsFile
import os
import pandas as pd
import re
import concurrent.futures
import time
import multiprocessing
import traceback

# 设置主文件夹路径
main_folder = r"D:\Lab\Water\D6.25"

def process_subfolder(subfolder):
    """处理单个子文件夹 - 并行任务函数"""
    start_time = time.time()
    folder_name = os.path.basename(subfolder)
    print(f"\n{'='*40}\n开始处理子文件夹: {folder_name}")
    
    # 设置输入输出路径
    output_folder = subfolder
    
    # 获取所有TDMS文件并按数字序号排序
    try:
        tdms_files = [f for f in os.listdir(subfolder) if f.endswith('.tdms')]
        if not tdms_files:
            print(f"子文件夹 {folder_name} 中没有TDMS文件，跳过...")
            return
        
        # 使用正则表达式提取文件名中的最后一个数字作为排序依据
        def extract_number(filename):
            numbers = re.findall(r'\d+', filename)
            return int(numbers[-1]) if numbers else 0
        
        tdms_files.sort(key=extract_number)
        files = [os.path.join(subfolder, f) for f in tdms_files]
        
        print(f"找到 {len(tdms_files)} 个TDMS文件，将只处理前20个文件...")
        
        # 只取前20个文件
        files_to_process = files[:20]
        file_count = len(files_to_process)
        
        # 遍历16个通道
        for channel_num in range(1, 17):  
            channel_name = f"通道{channel_num}"
            extracted_data = []
            print(f"处理通道: {channel_name} | 处理文件数: {file_count}")

            # 逐步读取文件
            for i in range(1, file_count + 1):
                current_files = files_to_process[:i]
                combined_data = []

                # 读取数据
                for file in current_files:
                    try:
                        tdms_file = TdmsFile(file)
                        
                        # ==== 改进的组识别逻辑 ====
                        # 获取所有可用组
                        groups = tdms_file.groups()
                        if not groups:
                            print(f"文件 {os.path.basename(file)} 中没有找到任何组，跳过...")
                            continue
                        
                        # 使用第一个组（通常只有一个组）
                        group = groups[0]
                        group_name = group.name
                        
                        if channel_name not in group:
                            print(f"组 {group_name} 中不存在通道 {channel_name}，跳过此文件...")
                            continue
                            
                        channel_data = group[channel_name][:]
                        combined_data.extend(channel_data)
                        
                    except Exception as e:
                        # 输出更详细的错误信息
                        try:
                            group_names = [g.name for g in tdms_file.groups()]
                            print(f"文件 {os.path.basename(file)} 可用组: {group_names}")
                        except:
                            print(f"文件 {os.path.basename(file)} 无法获取组信息")
                            
                        print(f"读取文件 {os.path.basename(file)} 出错: {str(e)}")
                        continue

                if not combined_data:
                    print(f"{channel_name} 没有数据，跳过...")
                    continue

                # 傅里叶变换
                combined_array = np.array(combined_data)
                n_points = len(combined_array)
                sampling_frequency = 200000  # 根据实际情况调整采样频率

                spectrum = fft(combined_array)
                spectrum[0] = 0  # 去除直流分量
                magnitude = np.abs(spectrum)
                frequencies = fftfreq(n_points, d=1/sampling_frequency)

                # 处理正频率部分
                positive_freq = frequencies[:n_points//2]
                positive_mag = magnitude[:n_points//2]

                # 对数频率处理
                log_freq = np.log10(positive_freq + 1e-6)

                # 阈值筛选
                threshold = np.max(positive_mag) * 0.2
                valid_indices = np.where(positive_mag >= threshold)[0]
                
                # 提取前20个最大点
                if valid_indices.size > 0:
                    sorted_indices = valid_indices[np.argsort(-positive_mag[valid_indices])]
                    top_freq = log_freq[sorted_indices[:20]]
                    top_mag = positive_mag[sorted_indices[:20]]
                else:
                    top_freq = np.array([])
                    top_mag = np.array([])

                # 填充到20个数据点
                top_freq = np.pad(top_freq, (0, 20 - len(top_freq)), constant_values=np.nan)
                top_mag = np.pad(top_mag, (0, 20 - len(top_mag)), constant_values=np.nan)

                extracted_data.append((top_freq, top_mag))

            # 保存通道结果 - 修改为奇数列频率，偶数列幅度
            if extracted_data:
                # 创建空DataFrame
                df = pd.DataFrame()
                
                # 添加列：奇数列频率，偶数列幅度
                for i, (freq, mag) in enumerate(extracted_data):
                    df[f"File{i+1}_Freq"] = freq
                    df[f"File{i+1}_Mag"] = mag
                
                excel_path = os.path.join(output_folder, f"{channel_name}_analysis.xlsx")
                df.to_excel(excel_path, index=False)
                print(f"已保存: {os.path.basename(excel_path)}")
    
    except Exception as e:
        print(f"处理子文件夹 {folder_name} 时发生严重错误: {str(e)}")
        traceback.print_exc()
    
    elapsed = time.time() - start_time
    print(f"完成处理子文件夹: {folder_name} [耗时: {elapsed:.2f}秒]\n{'='*40}")

def main():
    """主函数 - 组织并行处理"""
    # 收集所有需要处理的子文件夹
    subfolders = []
    for item in os.listdir(main_folder):
        subfolder_path = os.path.join(main_folder, item)
        if os.path.isdir(subfolder_path):
            subfolders.append(subfolder_path)
    
    if not subfolders:
        print("未找到需要处理的子文件夹！")
        return
    
    print(f"找到 {len(subfolders)} 个子文件夹，开始并行处理...")
    start_total = time.time()
    
    # 创建进程池 (根据CPU核心数自动设置)
    max_workers = min(len(subfolders), multiprocessing.cpu_count() - 1 or 1)
    print(f"使用 {max_workers} 个工作进程进行并行处理")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 使用map方法分配任务
        futures = {executor.submit(process_subfolder, subfolder): subfolder for subfolder in subfolders}
        
        # 等待所有任务完成并处理结果
        completed = 0
        total = len(subfolders)
        
        for future in concurrent.futures.as_completed(futures):
            subfolder = futures[future]
            try:
                future.result()  # 获取结果（如果有异常会在此处抛出）
                completed += 1
                print(f"进度: {completed}/{total} 文件夹 ({completed/total*100:.1f}%)")
            except Exception as e:
                print(f"处理文件夹 {os.path.basename(subfolder)} 时发生错误: {str(e)}")
    
    total_elapsed = time.time() - start_total
    print(f"\n所有文件夹处理完成！总耗时: {total_elapsed:.2f}秒")

if __name__ == "__main__":
    print("=" * 60)
    print("开始并行处理TDMS数据（仅处理前20个文件）")
    print("=" * 60)
    main()