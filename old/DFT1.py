
#统一提取16个通道数据（⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐）

import numpy as np
from scipy.fft import fft, fftfreq
from nptdms import TdmsFile  # 用于读取TDMS文件
import os
import pandas as pd

# 设置TDMS文件的路径
tdms_folder = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼下\缺口圆柱不开盖不接地正弦波正偏压"
output_folder = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼下\缺口圆柱不开盖不接地正弦波正偏压"  # Excel文件保存路径
os.makedirs(output_folder, exist_ok=True)  # 如果输出文件夹不存在，则创建

# 假设有40个文件
files = [f"{tdms_folder}/1_250_1_{i:03d}.tdms" for i in range(1, 15)]  # 前40个文件

# 遍历 16 个通道
for channel_num in range(1, 17):  
    channel_name = f"通道{channel_num}"  # 动态获取通道名称
    extracted_data = []  # 用于存储当前通道的数据

    print(f"正在处理 {channel_name}...")

    # 逐步读取TDMS文件并进行傅里叶变换
    for i in range(1, len(files) + 1):
        current_files = files[:i]
        combined_data = []  

        # 读取文件数据
        for file in current_files:
            tdms_file = TdmsFile(file)
            group = tdms_file["未命名"]  # 依据实际文件结构调整
            if channel_name not in group:
                print(f"{file} 不包含 {channel_name}，跳过...")
                continue
            channel_data = group[channel_name][:]
            combined_data.extend(channel_data)  

        # 如果该通道没有数据，则跳过
        if len(combined_data) == 0:
            print(f"{channel_name} 没有数据，跳过...")
            continue

        combined_data = np.array(combined_data)

        # 进行傅里叶变换
        n_points = len(combined_data)  
        sampling_frequency = 200000  

        spectrum = fft(combined_data)
        spectrum[0] = 0  # 去除直流分量
        magnitude = np.abs(spectrum)  
        frequencies = fftfreq(n_points, d=1/sampling_frequency)

        # 只保留正频率部分
        positive_frequencies = frequencies[:n_points//2]
        positive_magnitude = magnitude[:n_points//2]

        # 频率轴对数变换
        log_frequencies = np.log10(positive_frequencies + 1e-6)

        # 提取幅度大于最大值 20% 的点
        max_magnitude = np.max(positive_magnitude)
        threshold = max_magnitude * 0.2

        valid_indices = np.where(positive_magnitude >= threshold)[0]
        valid_frequencies = log_frequencies[valid_indices]
        valid_magnitudes = positive_magnitude[valid_indices]

        # 选取幅度最大的前 20 个点
        if len(valid_frequencies) > 20:
            top_20_indices = np.argsort(valid_magnitudes)[-20:]
            top_20_frequencies = valid_frequencies[top_20_indices]
            top_20_magnitudes = valid_magnitudes[top_20_indices]
        else:
            top_20_frequencies = valid_frequencies
            top_20_magnitudes = valid_magnitudes

        # 填充不足 20 个点的部分
        top_20_frequencies = np.pad(top_20_frequencies, (0, 20 - len(top_20_frequencies)), constant_values=np.nan)
        top_20_magnitudes = np.pad(top_20_magnitudes, (0, 20 - len(top_20_magnitudes)), constant_values=np.nan)

        extracted_data.append({'frequencies': top_20_frequencies, 'magnitudes': top_20_magnitudes})

        print(f"{channel_name} 提取了 {i} 个文件的数据，共找到 {len(valid_frequencies)} 个点，保留了 {len(top_20_frequencies)} 个点")

    # 如果该通道没有提取到任何数据，则跳过
    if not extracted_data:
        print(f"{channel_name} 没有有效数据，跳过保存...")
        continue

    # 保存数据为 Excel
    excel_data = {}
    max_length = max(len(data['frequencies']) for data in extracted_data)

    for i, data in enumerate(extracted_data):
        frequencies = np.pad(data['frequencies'], (0, max_length - len(data['frequencies'])), constant_values=np.nan)
        magnitudes = np.pad(data['magnitudes'], (0, max_length - len(data['magnitudes'])), constant_values=np.nan)

        excel_data[f"File {i+1} - Frequencies (Log)"] = frequencies
        excel_data[f"File {i+1} - Magnitudes"] = magnitudes

    df = pd.DataFrame(excel_data)

    # Excel 文件路径
    excel_file_path = os.path.join(output_folder, f"{channel_name}.xlsx")
    df.to_excel(excel_file_path, index=False)

    print(f"{channel_name} 处理完成，已保存为: {excel_file_path}\n")


#统一提取16个通道数据（⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐）

import numpy as np
from scipy.fft import fft, fftfreq
from nptdms import TdmsFile  # 用于读取TDMS文件
import os
import pandas as pd

# 设置TDMS文件的路径
tdms_folder = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼下\缺口圆柱不开盖接地10k欧方波负偏压"
output_folder = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼下\缺口圆柱不开盖接地10k欧方波负偏压"  # Excel文件保存路径
os.makedirs(output_folder, exist_ok=True)  # 如果输出文件夹不存在，则创建

# 假设有40个文件
files = [f"{tdms_folder}/1_250_1_{i:03d}.tdms" for i in range(1, 15)]  # 前40个文件

# 遍历 16 个通道
for channel_num in range(1, 17):  
    channel_name = f"通道{channel_num}"  # 动态获取通道名称
    extracted_data = []  # 用于存储当前通道的数据

    print(f"正在处理 {channel_name}...")

    # 逐步读取TDMS文件并进行傅里叶变换
    for i in range(1, len(files) + 1):
        current_files = files[:i]
        combined_data = []  

        # 读取文件数据
        for file in current_files:
            tdms_file = TdmsFile(file)
            group = tdms_file["未命名"]  # 依据实际文件结构调整
            if channel_name not in group:
                print(f"{file} 不包含 {channel_name}，跳过...")
                continue
            channel_data = group[channel_name][:]
            combined_data.extend(channel_data)  

        # 如果该通道没有数据，则跳过
        if len(combined_data) == 0:
            print(f"{channel_name} 没有数据，跳过...")
            continue

        combined_data = np.array(combined_data)

        # 进行傅里叶变换
        n_points = len(combined_data)  
        sampling_frequency = 200000  

        spectrum = fft(combined_data)
        spectrum[0] = 0  # 去除直流分量
        magnitude = np.abs(spectrum)  
        frequencies = fftfreq(n_points, d=1/sampling_frequency)

        # 只保留正频率部分
        positive_frequencies = frequencies[:n_points//2]
        positive_magnitude = magnitude[:n_points//2]

        # 频率轴对数变换
        log_frequencies = np.log10(positive_frequencies + 1e-6)

        # 提取幅度大于最大值 20% 的点
        max_magnitude = np.max(positive_magnitude)
        threshold = max_magnitude * 0.2

        valid_indices = np.where(positive_magnitude >= threshold)[0]
        valid_frequencies = log_frequencies[valid_indices]
        valid_magnitudes = positive_magnitude[valid_indices]

        # 选取幅度最大的前 20 个点
        if len(valid_frequencies) > 20:
            top_20_indices = np.argsort(valid_magnitudes)[-20:]
            top_20_frequencies = valid_frequencies[top_20_indices]
            top_20_magnitudes = valid_magnitudes[top_20_indices]
        else:
            top_20_frequencies = valid_frequencies
            top_20_magnitudes = valid_magnitudes

        # 填充不足 20 个点的部分
        top_20_frequencies = np.pad(top_20_frequencies, (0, 20 - len(top_20_frequencies)), constant_values=np.nan)
        top_20_magnitudes = np.pad(top_20_magnitudes, (0, 20 - len(top_20_magnitudes)), constant_values=np.nan)

        extracted_data.append({'frequencies': top_20_frequencies, 'magnitudes': top_20_magnitudes})

        print(f"{channel_name} 提取了 {i} 个文件的数据，共找到 {len(valid_frequencies)} 个点，保留了 {len(top_20_frequencies)} 个点")

    # 如果该通道没有提取到任何数据，则跳过
    if not extracted_data:
        print(f"{channel_name} 没有有效数据，跳过保存...")
        continue

    # 保存数据为 Excel
    excel_data = {}
    max_length = max(len(data['frequencies']) for data in extracted_data)

    for i, data in enumerate(extracted_data):
        frequencies = np.pad(data['frequencies'], (0, max_length - len(data['frequencies'])), constant_values=np.nan)
        magnitudes = np.pad(data['magnitudes'], (0, max_length - len(data['magnitudes'])), constant_values=np.nan)

        excel_data[f"File {i+1} - Frequencies (Log)"] = frequencies
        excel_data[f"File {i+1} - Magnitudes"] = magnitudes

    df = pd.DataFrame(excel_data)

    # Excel 文件路径
    excel_file_path = os.path.join(output_folder, f"{channel_name}.xlsx")
    df.to_excel(excel_file_path, index=False)

    print(f"{channel_name} 处理完成，已保存为: {excel_file_path}\n")


#统一提取16个通道数据（⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐）

import numpy as np
from scipy.fft import fft, fftfreq
from nptdms import TdmsFile  # 用于读取TDMS文件
import os
import pandas as pd

# 设置TDMS文件的路径
tdms_folder = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼下\缺口圆柱不开盖接地10k欧方波正偏压"
output_folder = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼下\缺口圆柱不开盖接地10k欧方波正偏压"  # Excel文件保存路径
os.makedirs(output_folder, exist_ok=True)  # 如果输出文件夹不存在，则创建

# 假设有40个文件
files = [f"{tdms_folder}/1_250_1_{i:03d}.tdms" for i in range(1, 15)]  # 前40个文件

# 遍历 16 个通道
for channel_num in range(1, 17):  
    channel_name = f"通道{channel_num}"  # 动态获取通道名称
    extracted_data = []  # 用于存储当前通道的数据

    print(f"正在处理 {channel_name}...")

    # 逐步读取TDMS文件并进行傅里叶变换
    for i in range(1, len(files) + 1):
        current_files = files[:i]
        combined_data = []  

        # 读取文件数据
        for file in current_files:
            tdms_file = TdmsFile(file)
            group = tdms_file["未命名"]  # 依据实际文件结构调整
            if channel_name not in group:
                print(f"{file} 不包含 {channel_name}，跳过...")
                continue
            channel_data = group[channel_name][:]
            combined_data.extend(channel_data)  

        # 如果该通道没有数据，则跳过
        if len(combined_data) == 0:
            print(f"{channel_name} 没有数据，跳过...")
            continue

        combined_data = np.array(combined_data)

        # 进行傅里叶变换
        n_points = len(combined_data)  
        sampling_frequency = 200000  

        spectrum = fft(combined_data)
        spectrum[0] = 0  # 去除直流分量
        magnitude = np.abs(spectrum)  
        frequencies = fftfreq(n_points, d=1/sampling_frequency)

        # 只保留正频率部分
        positive_frequencies = frequencies[:n_points//2]
        positive_magnitude = magnitude[:n_points//2]

        # 频率轴对数变换
        log_frequencies = np.log10(positive_frequencies + 1e-6)

        # 提取幅度大于最大值 20% 的点
        max_magnitude = np.max(positive_magnitude)
        threshold = max_magnitude * 0.2

        valid_indices = np.where(positive_magnitude >= threshold)[0]
        valid_frequencies = log_frequencies[valid_indices]
        valid_magnitudes = positive_magnitude[valid_indices]

        # 选取幅度最大的前 20 个点
        if len(valid_frequencies) > 20:
            top_20_indices = np.argsort(valid_magnitudes)[-20:]
            top_20_frequencies = valid_frequencies[top_20_indices]
            top_20_magnitudes = valid_magnitudes[top_20_indices]
        else:
            top_20_frequencies = valid_frequencies
            top_20_magnitudes = valid_magnitudes

        # 填充不足 20 个点的部分
        top_20_frequencies = np.pad(top_20_frequencies, (0, 20 - len(top_20_frequencies)), constant_values=np.nan)
        top_20_magnitudes = np.pad(top_20_magnitudes, (0, 20 - len(top_20_magnitudes)), constant_values=np.nan)

        extracted_data.append({'frequencies': top_20_frequencies, 'magnitudes': top_20_magnitudes})

        print(f"{channel_name} 提取了 {i} 个文件的数据，共找到 {len(valid_frequencies)} 个点，保留了 {len(top_20_frequencies)} 个点")

    # 如果该通道没有提取到任何数据，则跳过
    if not extracted_data:
        print(f"{channel_name} 没有有效数据，跳过保存...")
        continue

    # 保存数据为 Excel
    excel_data = {}
    max_length = max(len(data['frequencies']) for data in extracted_data)

    for i, data in enumerate(extracted_data):
        frequencies = np.pad(data['frequencies'], (0, max_length - len(data['frequencies'])), constant_values=np.nan)
        magnitudes = np.pad(data['magnitudes'], (0, max_length - len(data['magnitudes'])), constant_values=np.nan)

        excel_data[f"File {i+1} - Frequencies (Log)"] = frequencies
        excel_data[f"File {i+1} - Magnitudes"] = magnitudes

    df = pd.DataFrame(excel_data)

    # Excel 文件路径
    excel_file_path = os.path.join(output_folder, f"{channel_name}.xlsx")
    df.to_excel(excel_file_path, index=False)

    print(f"{channel_name} 处理完成，已保存为: {excel_file_path}\n")

