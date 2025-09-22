import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import traceback

# 设置主文件夹路径
main_folder = r"D:\Lab\Water\A6.20"

def process_folder(subfolder):
    """处理单个子文件夹"""
    folder_name = os.path.basename(subfolder)
    output_dir = os.path.join(subfolder, "processed_images")
    os.makedirs(output_dir, exist_ok=True)

    # 获取所有 Excel 文件
    excel_files = [f for f in os.listdir(subfolder) if f.endswith(('.xlsx', '.xls'))]

    for file_name in excel_files:
        try:
            file_path = os.path.join(subfolder, file_name)
            
            # 读取数据
            df = pd.read_excel(file_path, header=None).fillna(0)

            # 数据处理部分（保持原有逻辑）
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

if __name__ == "__main__":
    # 遍历所有子文件夹
    for root, dirs, files in os.walk(main_folder):
        # 跳过主文件夹本身
        if root == main_folder:
            continue
            
        print(f"\n{'='*40}")
        print(f"开始处理文件夹: {root}")
        process_folder(root)
        print(f"完成处理文件夹: {root}")
        print(f"{'='*40}")

    print("所有文件夹处理完成！")