import os
import re

# 设置主文件夹路径
main_folder = r"D:\Lab\Water\A6.20"

def process_files(folder):
    """处理单个文件夹中的文件"""
    # 获取文件夹中所有Excel文件
    files = [f for f in os.listdir(folder) if f.endswith('.xlsx')]
    
    # 匹配通道分析文件的模式
    pattern = re.compile(r'通道(\d+)_analysis\.xlsx$')
    
    for file in files:
        match = pattern.match(file)
        if match:
            channel_num = match.group(1)
            old_path = os.path.join(folder, file)
            new_name = f"通道{channel_num}.xlsx"
            new_path = os.path.join(folder, new_name)
            
            # 检查目标文件是否存在
            if os.path.exists(new_path):
                print(f"发现已存在文件: {new_name}，删除原文件: {file}")
                os.remove(old_path)
            else:
                print(f"重命名: {file} -> {new_name}")
                os.rename(old_path, new_path)

def main():
    # 遍历主文件夹下的所有子文件夹
    for root, dirs, files in os.walk(main_folder):
        # 跳过主文件夹本身，只处理子文件夹
        if root == main_folder:
            continue
            
        print(f"\n正在处理文件夹: {root}")
        process_files(root)

if __name__ == "__main__":
    print("开始处理文件重命名...")
    main()
    print("\n所有文件处理完成！")