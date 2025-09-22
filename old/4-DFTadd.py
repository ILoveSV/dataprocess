import os
from PIL import Image
import re

def natural_sort_key(s):
    """自然排序键函数，支持带数字的文件名排序"""
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', s)]

def process_subfolder(subfolder):
    """处理单个子文件夹"""
    # 获取所有图片文件并按自然顺序排序
    image_files = sorted(
        [f for f in os.listdir(subfolder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
        key=natural_sort_key
    )

    if not image_files:
        print(f"跳过空文件夹: {subfolder}")
        return

    try:
        # 读取所有图片并检查尺寸一致性
        images = [Image.open(os.path.join(subfolder, f)) for f in image_files]
        widths, heights = zip(*(img.size for img in images))
        
        if len(set(widths)) != 1 or len(set(heights)) != 1:
            print(f"图片尺寸不一致，跳过文件夹: {subfolder}")
            return

        # 计算拼接尺寸
        width, height = images[0].size
        total_height = height * len(images)

        # 创建新画布
        merged_image = Image.new("RGB", (width, total_height))
        
        # 拼接图片
        y_offset = 0
        for img in images:
            merged_image.paste(img, (0, y_offset))
            y_offset += height
            img.close()  # 显式关闭图片

        # 保存结果到原文件夹
        folder_name = os.path.basename(subfolder)
        output_path = os.path.join(subfolder, f"{folder_name}_merged.png")
        merged_image.save(output_path)
        print(f"已创建拼接图：{output_path}")

    except Exception as e:
        print(f"处理失败 {subfolder}: {str(e)}")

def main():
    # 主文件夹路径
    base_dir = r"D:\Lab\Water\A6.20"
    
    # 遍历所有子文件夹
    for root, dirs, files in os.walk(base_dir):
        # 跳过主文件夹本身
        if root == base_dir:
            continue
            
        print(f"\n正在处理：{root}")
        process_subfolder(root)

if __name__ == "__main__":
    print("开始拼接处理...")
    main()
    print("\n所有文件夹处理完成！")