#====================================================================
# File Name:3-DFTadd.py
# Project Name:Data Process
# Description:
# 1、整合16个通道的分析结果
# 2、形成完整的实验数据可视化（每个子文件夹→1张长图）
#====================================================================
import os
from PIL import Image
import re

def natural_sort_key(s):
    """自然排序键函数，支持带数字的文件名排序"""
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', s)]

def process_subfolder(subfolder, order_mode, base_dir):
    """处理单个子文件夹 - 支持不同尺寸图片拼接和自定义顺序"""
    # 获取所有图片文件并按自然顺序排序
    image_files = sorted(
        [f for f in os.listdir(subfolder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
        key=natural_sort_key
    )
    
    num_images = len(image_files)
    if num_images == 0:
        print(f"跳过空文件夹: {subfolder}")
        return

    try:
        # 只在有16张图片时才应用交换顺序
        if order_mode == "swap" and num_images == 16:
            # 交换顺序：9-16在前，1-8在后
            image_files = image_files[8:16] + image_files[0:8]
            print(f"文件夹有16张图片，使用交换顺序模式处理: {subfolder}")
        else:
            if order_mode == "swap" and num_images != 16:
                print(f"文件夹有{num_images}张图片（不是16张），使用正常顺序处理: {subfolder}")
            else:
                print(f"使用正常顺序模式处理: {subfolder}")
        
        # 计算最大宽度和总高度
        sizes = []
        for f in image_files:
            with Image.open(os.path.join(subfolder, f)) as img:
                sizes.append(img.size)
        
        max_width = max(width for width, height in sizes)
        total_height = sum(height for width, height in sizes)
        
        # 创建新画布（白色背景）
        with Image.new("RGB", (max_width, total_height), (255, 255, 255)) as merged_image:
            # 拼接图片
            y_offset = 0
            for f in image_files:
                with Image.open(os.path.join(subfolder, f)) as img:
                    # 计算水平偏移（居中放置）
                    width, height = img.size
                    x_offset = (max_width - width) // 2
                    
                    # 粘贴图片
                    merged_image.paste(img, (x_offset, y_offset))
                    y_offset += height
            
            # 获取目录名称：上级目录和上上级目录
            parent_dir = os.path.basename(os.path.dirname(subfolder))
            grandparent_dir = os.path.basename(os.path.dirname(os.path.dirname(subfolder)))
            
            # 构建文件名：上级目录_上上级目录.png
            output_filename = f"{parent_dir}_{grandparent_dir}.png"
            output_path = os.path.join(base_dir, output_filename)
            
            # 避免覆盖现有文件
            counter = 1
            while os.path.exists(output_path):
                output_filename = f"{parent_dir}_{grandparent_dir}_{counter}.png"
                output_path = os.path.join(base_dir, output_filename)
                counter += 1
            
            merged_image.save(output_path)
            print(f"已创建拼接图：{output_path}")

    except Exception as e:
        print(f"处理失败 {subfolder}: {str(e)}")

def main():
    # 主文件夹路径
    base_dir = r"D:\Lab\test"
    
    # 选择拼接顺序模式
    print("请选择拼接顺序模式:")
    print("1: 正常顺序 (1-16)")
    print("2: 交换顺序 (9-16在前,1-8在后)")
    choice = input("请输入选项 (1 或 2): ").strip()
    
    order_mode = "normal"  # 默认正常顺序
    if choice == "2":
        order_mode = "swap"
        print("已选择交换顺序模式 (仅当16张图片时生效)")
    else:
        print("已选择正常顺序模式")
    
    # 遍历所有子文件夹
    for root, dirs, files in os.walk(base_dir):
        # 跳过主文件夹本身
        if root == base_dir:
            continue
            
        print(f"\n正在处理：{root}")
        process_subfolder(root, order_mode, base_dir)

if __name__ == "__main__":
    print("开始拼接处理...")
    main()
    print("\n所有文件夹处理完成！")