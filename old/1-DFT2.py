import numpy as np
from scipy.fft import fft, fftfreq
from nptdms import TdmsFile
import os
import pandas as pd
import re

# 设置主文件夹路径
main_folder = r"D:\Lab\test"

def process_subfolder(subfolder):
    # 设置输入输出路径
    tdms_folder = subfolder
    output_folder = subfolder
    
    # 获取所有TDMS文件并按数字序号排序
    tdms_files = [f for f in os.listdir(tdms_folder) if f.endswith('.tdms')]
    # 使用正则表达式提取文件名中的最后一个数字作为排序依据
    try:
        tdms_files.sort(key=lambda x: int(re.findall(r'\d+', x)[-1]))
    except IndexError:
        print(f"无法解析文件序号: {subfolder}")
        return
    
    files = [os.path.join(tdms_folder, f) for f in tdms_files]
    
    if not files:
        print(f"子文件夹 {subfolder} 中没有TDMS文件，跳过...")
        return

    # 遍历16个通道
    for channel_num in range(1, 17):  
        channel_name = f"通道{channel_num}"
        extracted_data = []

        print(f"\n处理文件夹: {os.path.basename(subfolder)} | 通道: {channel_name}")

        # 逐步读取文件
        for i in range(1, len(files) + 1):
            current_files = files[:i]
            combined_data = []

            # 读取数据
            for file in current_files:
                try:
                    tdms_file = TdmsFile(file)
                    group = tdms_file["未命名"]  # 根据实际情况调整组名
                    if channel_name not in group:
                        continue
                    channel_data = group[channel_name][:]
                    combined_data.extend(channel_data)
                except Exception as e:
                    print(f"读取文件 {file} 出错: {str(e)}")
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

            extracted_data.append({'frequencies': top_freq, 'magnitudes': top_mag})

        # 保存结果
        if extracted_data:
            df = pd.DataFrame({
                f"File{i+1}_Freq": data['frequencies'] for i, data in enumerate(extracted_data)
            } | {
                f"File{i+1}_Mag": data['magnitudes'] for i, data in enumerate(extracted_data)
            })

            excel_path = os.path.join(output_folder, f"{channel_name}_analysis.xlsx")
            df.to_excel(excel_path, index=False)
            print(f"已保存: {excel_path}")

# 遍历主文件夹下的所有子文件夹
for item in os.listdir(main_folder):
    subfolder_path = os.path.join(main_folder, item)
    if os.path.isdir(subfolder_path):
        print(f"\n{'='*40}")
        print(f"开始处理子文件夹: {item}")
        process_subfolder(subfolder_path)
        print(f"完成处理子文件夹: {item}")
        print(f"{'='*40}\n")

print("所有文件夹处理完成！")