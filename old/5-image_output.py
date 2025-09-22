import os
import shutil
import re
from glob import glob

def safe_filename(name):
    """生成安全的文件名（保留中文和常用符号）"""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

def collect_images(main_folder):
    output_dir = os.path.join(main_folder, "finalresult")
    os.makedirs(output_dir, exist_ok=True)
    
    counter = {
        "total_found": 0,
        "copied": 0,
        "duplicates": 0,
        "errors": 0
    }

    merged_files = glob(os.path.join(main_folder, "**", "*merged*.png"), recursive=True)
    counter["total_found"] = len(merged_files)

    processed_names = {}
    for idx, file_path in enumerate(merged_files, 1):
        try:
            # 获取上上级文件夹名称
            grandparent_dir = os.path.dirname(os.path.dirname(file_path))
            folder_name = os.path.basename(grandparent_dir)
            
            clean_name = f"{safe_filename(folder_name)}.png"
            
            # 生成唯一文件名
            base_name = clean_name
            copy_num = 1
            while os.path.exists(os.path.join(output_dir, clean_name)):
                clean_name = f"{os.path.splitext(base_name)[0]} ({copy_num}).png"
                copy_num += 1
                counter["duplicates"] += 1

            shutil.copy2(file_path, os.path.join(output_dir, clean_name))
            processed_names[file_path] = clean_name
            counter["copied"] += 1

            print(f"[{idx}/{len(merged_files)}] 已处理: {folder_name} -> {clean_name}")

        except Exception as e:
            counter["errors"] += 1
            print(f"处理失败: {file_path}\n错误信息: {str(e)}")

    # 统计报告和日志（保持不变）
    print("\n" + "="*50)
    print(f"扫描到 {counter['total_found']} 个合并图片")
    print(f"成功复制: {counter['copied']} 个")
    print(f"处理重复: {counter['duplicates']} 次")
    print(f"错误发生: {counter['errors']} 次")
    print(f"最终保存路径: {output_dir}")

    log_path = os.path.join(output_dir, "rename_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("原始路径 -> 新文件名\n")
        f.write("="*50 + "\n")
        for orig, new in processed_names.items():
            f.write(f"{orig} -> {new}\n")

if __name__ == "__main__":
    main_directory = r"D:\Lab\BEST2024\A2025.3.27\A3.27楼上"
    print("开始处理图片收集任务...")
    collect_images(main_directory)
    print("\n操作已完成，请检查 finalresult 文件夹")