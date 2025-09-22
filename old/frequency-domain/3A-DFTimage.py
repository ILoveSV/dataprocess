#====================================================================
# File Name:3A-DFTimage_improved.py
# Project Name:Data Process
# Description:
# 1、读取上一步生成的Excel文件,分离奇数列(频率)和偶数列(幅度)
# 2、科学颜色映射:使用HSV色彩空间(色调=频率,亮度=幅度)
# 3、单列图像生成,每列数据生成1×20像素的RGB图像条,20个图像条 → 2×10网格布局
# 4、添加颜色条图例和元数据信息
#====================================================================
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb
from PIL import Image, ImageDraw, ImageFont
import traceback
import concurrent.futures
import time
import json
from scipy import stats

# 设置主文件夹路径
main_folder = r"D:\Lab\Water\D6.25"

def create_colorbar_legend(freq_min, freq_max, output_dir, file_name):
    """创建颜色条图例"""
    # 创建HSV颜色条
    height = 100
    width = 400
    legend_img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(legend_img)
    
    # 绘制颜色条
    for x in range(width):
        # 计算当前点的频率值 (对数坐标)
        freq_val = freq_min * (freq_max / freq_min) ** (x / width)
        # 归一化到0-1范围
        h_val = (np.log10(freq_val) - np.log10(freq_min)) / (np.log10(freq_max) - np.log10(freq_min))
        h_val = np.clip(h_val, 0, 1)
        
        # 计算颜色 (固定饱和度和亮度)
        r, g, b = hsv_to_rgb([h_val, 1.0, 1.0])
        color = (int(r*255), int(g*255), int(b*255))
        
        # 绘制垂直线
        draw.line([(x, 10), (x, height-10)], fill=color, width=1)
    
    # 添加刻度标记和标签
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        # 回退到默认字体
        font = ImageFont.load_default()
    
    # 添加频率刻度
    ticks = np.logspace(np.log10(freq_min), np.log10(freq_max), 5)
    for tick in ticks:
        x_pos = int((np.log10(tick) - np.log10(freq_min)) / 
                   (np.log10(freq_max) - np.log10(freq_min)) * width)
        draw.line([(x_pos, height-15), (x_pos, height-10)], fill=(0, 0, 0), width=1)
        draw.text((x_pos-10, height-25), f"{tick:.1e}", fill=(0, 0, 0), font=font)
    
    # 添加标题
    draw.text((10, 5), "Frequency (Hz)", fill=(0, 0, 0), font=font)
    
    # 保存图例
    legend_path = os.path.join(output_dir, f"{file_name}_colorbar.png")
    legend_img.save(legend_path)
    
    return legend_path

def process_folder(subfolder):
    """处理单个子文件夹 - 并行任务函数"""
    start_time = time.time()
    folder_name = os.path.basename(subfolder)
    output_dir = os.path.join(subfolder, "processed_images")
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取所有 Excel 文件
    excel_files = [f for f in os.listdir(subfolder) if f.endswith(('.xlsx', '.xls'))]
    
    if not excel_files:
        print(f"文件夹 {folder_name} 中没有Excel文件，跳过")
        return
    
    print(f"开始处理文件夹: {folder_name} ({len(excel_files)}个Excel文件)")
    
    # 收集所有频率和幅度数据用于全局归一化
    all_freqs = []
    all_mags = []
    
    for file_name in excel_files:
        try:
            file_path = os.path.join(subfolder, file_name)
            df = pd.read_excel(file_path, header=None).fillna(0)
            
            # 提取频率和幅度数据
            even_columns_data = df.iloc[1:, 1::2].values.astype(float)
            odd_columns_data = df.iloc[1:, 0::2].values.astype(float)
            
            # 收集数据用于全局归一化
            all_freqs.extend(odd_columns_data.flatten())
            all_mags.extend(even_columns_data.flatten())
            
        except Exception as e:
            print(f"读取文件 {file_name} 时发生错误: {str(e)}")
            continue
    
    # 计算全局频率范围 (使用对数空间)
    all_freqs = np.array(all_freqs)
    all_freqs = all_freqs[all_freqs > 0]  # 移除无效频率
    freq_min = np.percentile(all_freqs, 5)  # 使用5%分位数作为最小值
    freq_max = np.percentile(all_freqs, 95)  # 使用95%分位数作为最大值
    
    # 计算全局幅度范围
    all_mags = np.array(all_mags)
    mag_min = np.min(all_mags)
    mag_max = np.max(all_mags)
    
    # 为每个文件创建元数据
    metadata = {
        "freq_min": float(freq_min),
        "freq_max": float(freq_max),
        "mag_min": float(mag_min),
        "mag_max": float(mag_max),
        "processing_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files_processed": []
    }
    
    for file_name in excel_files:
        try:
            file_path = os.path.join(subfolder, file_name)
            
            # 读取数据
            df = pd.read_excel(file_path, header=None).fillna(0)

            # 数据处理部分
            even_columns_data = df.iloc[1:, 1::2].values.astype(float)
            odd_columns_data = df.iloc[1:, 0::2].values.astype(float)

            if np.any(np.isnan(even_columns_data) | np.isinf(even_columns_data)):
                print(f"跳过包含无效数据的文件: {file_name}")
                continue

            # 归一化处理 - 使用全局范围
            normalized_mags = (even_columns_data - mag_min) / (mag_max - mag_min + 1e-10)
            normalized_mags = np.clip(normalized_mags, 0, 1)
            
            # 使用HSV色彩空间: H(色调)=频率, S(饱和度)=1, V(亮度)=幅度
            # 频率映射到HSV的Hue通道 (0-1范围)
            normalized_freqs = (np.log10(odd_columns_data) - np.log10(freq_min)) / \
                              (np.log10(freq_max) - np.log10(freq_min) + 1e-10)
            normalized_freqs = np.clip(normalized_freqs, 0, 1)
            
            # 生成单个图像
            image_files = []
            for idx in range(normalized_mags.shape[1]):
                try:
                    # 获取当前列的数据
                    freq_col = normalized_freqs[:, idx]
                    mag_col = normalized_mags[:, idx]
                    
                    # 创建HSV数组
                    h = freq_col
                    s = np.ones_like(h)  # 饱和度为1
                    v = mag_col          # 亮度为归一化幅度
                    
                    # 转换为RGB
                    hsv_array = np.stack([h, s, v], axis=-1)
                    rgb_image = np.zeros_like(hsv_array)
                    
                    for i in range(len(h)):
                        rgb_image[i] = hsv_to_rgb(hsv_array[i])
                    
                    # 转换为0-255整数
                    rgb_image = (rgb_image * 255).astype(np.uint8)
                    
                    # 创建图像
                    plt.figure(figsize=(5, 1))
                    plt.imshow(rgb_image.reshape(1, -1, 3), aspect='auto')
                    plt.axis('off')
                    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
                    
                    img_path = os.path.join(output_dir, f"{file_name}_col_{idx+1}.png")
                    plt.savefig(img_path, bbox_inches='tight', pad_inches=0, dpi=100)
                    plt.close()
                    image_files.append(img_path)
                    
                except Exception as e:
                    print(f"生成图像失败 {file_name} 列 {idx+1}: {str(e)}")
                    continue

            # 图像拼接
            if len(image_files) >= 10:
                try:
                    images = [Image.open(img) for img in image_files]
                    width, height = images[0].size
                    total_width = width * 2 + 10  # 增加间距
                    total_height = height * 10 + 50  # 增加标题空间
                    
                    # 创建新图像
                    new_image = Image.new("RGB", (total_width, total_height), (255, 255, 255))
                    draw = ImageDraw.Draw(new_image)
                    
                    # 添加标题
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
                    
                    draw.text((10, 10), f"{file_name} - {folder_name}", fill=(0, 0, 0), font=font)
                    
                    # 粘贴图像
                    for i in range(10):
                        for j in range(2):
                            x = j * (width + 5)
                            y = i * height + 40
                            img_index = i * 2 + j
                            if img_index < len(images):
                                new_image.paste(images[img_index], (x, y))
                    
                    # 添加网格线
                    for i in range(11):
                        y_pos = i * height + 40
                        draw.line([(0, y_pos), (total_width, y_pos)], fill=(200, 200, 200), width=1)
                    
                    for j in range(3):
                        x_pos = j * (width + 5)
                        draw.line([(x_pos, 40), (x_pos, total_height)], fill=(200, 200, 200), width=1)
                    
                    merged_path = os.path.join(output_dir, f"{file_name}_{folder_name}.png")
                    new_image.save(merged_path)
                    
                    # 创建颜色条图例
                    legend_path = create_colorbar_legend(freq_min, freq_max, output_dir, file_name)
                    
                    # 记录元数据
                    metadata["files_processed"].append({
                        "file_name": file_name,
                        "processed_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "image_path": merged_path,
                        "legend_path": legend_path,
                        "columns_processed": normalized_mags.shape[1]
                    })
                    
                    # 清理临时文件
                    for img in images:
                        img.close()
                    for img_path in image_files:
                        os.remove(img_path)
                        
                except Exception as e:
                    print(f"拼接图像失败 {file_name}: {str(e)}")
                    traceback.print_exc()

        except Exception as e:
            print(f"处理文件 {file_name} 时发生错误: {str(e)}")
            traceback.print_exc()
            continue
    
    # 保存元数据
    metadata_path = os.path.join(output_dir, "processing_metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"完成文件夹: {folder_name} [耗时: {elapsed:.2f}秒]")

def main():
    # 收集所有需要处理的子文件夹
    subfolders = []
    for root, dirs, files in os.walk(main_folder):
        # 跳过主文件夹本身
        if root == main_folder:
            continue
        subfolders.append(root)
    
    if not subfolders:
        print("未找到需要处理的子文件夹！")
        return
    
    print(f"找到 {len(subfolders)} 个子文件夹，开始并行处理...")
    start_total = time.time()
    
    # 创建进程池 (根据CPU核心数自动设置)
    max_workers = max(1, int(os.cpu_count() * 0.8))
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 使用map方法分配任务
        futures = {executor.submit(process_folder, subfolder): subfolder for subfolder in subfolders}
        
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
                print(f"处理文件夹 {subfolder} 时发生错误: {str(e)}")
    
    total_elapsed = time.time() - start_total
    print(f"\n所有文件夹处理完成！总耗时: {total_elapsed:.2f}秒")

if __name__ == "__main__":
    print("=" * 60)
    print("开始并行处理图像生成任务 (改进版)")
    print("=" * 60)
    main()
'''
#====================================================================
# File Name:3A-DFTimage.py
# Project Name:Data Process
# Description:
# 1、读取上一步生成的Excel文件,分离奇数列(频率)和偶数列(幅度)
# 2、颜色映射:幅度→绿色通道(G);频率→红色通道(R)
# 3、单列图像生成,每列数据生成1×20像素的RGB图像条,20个图像条 → 2×10网格布局
#====================================================================
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import traceback
import concurrent.futures
import time

# 设置主文件夹路径
main_folder = r"D:\Lab\test"

def process_folder(subfolder):
    """处理单个子文件夹 - 并行任务函数"""
    start_time = time.time()
    folder_name = os.path.basename(subfolder)
    output_dir = os.path.join(subfolder, "processed_images")
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取所有 Excel 文件
    excel_files = [f for f in os.listdir(subfolder) if f.endswith(('.xlsx', '.xls'))]
    
    if not excel_files:
        print(f"文件夹 {folder_name} 中没有Excel文件，跳过")
        return
    
    print(f"开始处理文件夹: {folder_name} ({len(excel_files)}个Excel文件)")
    
    for file_name in excel_files:
        try:
            file_path = os.path.join(subfolder, file_name)
            
            # 读取数据
            df = pd.read_excel(file_path, header=None).fillna(0)

            # 数据处理部分
            even_columns_data = df.iloc[1:, 1::2].values.astype(float)
            odd_columns_data = df.iloc[1:, 0::2].values.astype(float)

            if np.any(np.isnan(even_columns_data) | np.isinf(even_columns_data)):
                print(f"跳过包含无效数据的文件: {file_name}")
                continue

            # 归一化处理
            max_value = np.max(even_columns_data)
            if max_value == 0:
                print(f"跳过无效文件（最大值为0）: {file_name}")
                continue
                
            normalization_factor = 256 / max_value
            normalized_even_data = np.clip(even_columns_data * normalization_factor, 0, 255).astype(np.uint8)

            # R通道处理
            normalized_odd_data = odd_columns_data.astype(int)
            r_values = np.zeros_like(normalized_odd_data, dtype=np.uint8)
            for i in range(normalized_odd_data.shape[1]):
                r_values[:, i] = np.mod(normalized_odd_data[:, i], 10)
                r_values[:, i] = np.where(r_values[:, i] == 0, 1,
                                        np.where(r_values[:, i] == 1, 64,
                                                np.where(r_values[:, i] == 2, 128,
                                                        np.where(r_values[:, i] == 3, 192, 255))))

            # 生成单个图像
            image_files = []
            for idx in range(normalized_even_data.shape[1]):
                try:
                    # 图像生成逻辑
                    column_data_g = normalized_even_data[:, idx]
                    column_data_r = r_values[:, idx]
                    column_data_b = np.zeros_like(column_data_g)
                    
                    rgb_image = np.stack([column_data_r, column_data_g, column_data_b], axis=-1)
                    
                    plt.figure(figsize=(5, 1))
                    plt.imshow(rgb_image.reshape(1, -1, 3), vmin=0, vmax=255)
                    plt.axis('off')
                    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
                    
                    img_path = os.path.join(output_dir, f"{file_name}_col_{idx+1}.png")
                    plt.savefig(img_path, bbox_inches='tight', pad_inches=0)
                    plt.close()
                    image_files.append(img_path)
                except Exception as e:
                    print(f"生成图像失败 {file_name} 列 {idx+1}: {str(e)}")
                    continue

            # 图像拼接
            if len(image_files) >= 10:
                try:
                    images = [Image.open(img) for img in image_files]
                    width, height = images[0].size
                    total_width = width * 2 + 1
                    total_height = height * 10
                    
                    new_image = Image.new("RGB", (total_width, total_height), (255, 255, 255))
                    for i in range(10):
                        for j in range(2):
                            x = j * (width + 1)
                            y = i * height
                            img_index = i * 2 + j
                            if img_index < len(images):
                                img = images[img_index].transpose(Image.FLIP_LEFT_RIGHT) if j == 0 else images[img_index]
                                new_image.paste(img, (x, y))
                    
                    merged_path = os.path.join(output_dir, f"{file_name}_{folder_name}.png")
                    new_image.save(merged_path)
                    
                    # 清理临时文件
                    for img in images:
                        img.close()
                    for img_path in image_files:
                        os.remove(img_path)
                except Exception as e:
                    print(f"拼接图像失败 {file_name}: {str(e)}")
                    traceback.print_exc()

        except Exception as e:
            print(f"处理文件 {file_name} 时发生错误: {str(e)}")
            traceback.print_exc()
            continue
    
    elapsed = time.time() - start_time
    print(f"完成文件夹: {folder_name} [耗时: {elapsed:.2f}秒]")

def main():
    # 收集所有需要处理的子文件夹
    subfolders = []
    for root, dirs, files in os.walk(main_folder):
        # 跳过主文件夹本身
        if root == main_folder:
            continue
        subfolders.append(root)
    
    if not subfolders:
        print("未找到需要处理的子文件夹！")
        return
    
    print(f"找到 {len(subfolders)} 个子文件夹，开始并行处理...")
    start_total = time.time()
    
    # 创建进程池 (根据CPU核心数自动设置)
    # 注意：处理图像时建议不要超过CPU核心数的80%
    max_workers = max(1, int(os.cpu_count() * 0.8))
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 使用map方法分配任务
        futures = {executor.submit(process_folder, subfolder): subfolder for subfolder in subfolders}
        
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
                print(f"处理文件夹 {subfolder} 时发生错误: {str(e)}")
    
    total_elapsed = time.time() - start_total
    print(f"\n所有文件夹处理完成！总耗时: {total_elapsed:.2f}秒")

if __name__ == "__main__":
    print("=" * 60)
    print("开始并行处理图像生成任务")
    print("=" * 60)
    main()
'''