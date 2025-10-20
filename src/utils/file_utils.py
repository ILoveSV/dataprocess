import yaml
from pathlib import Path
import logging

logger = logging.getLogger('data_process')

def generate_paths_config():
    """
    生成paths.yaml配置文件
    
    Args:
        template_path (str): 模板文件路径，包含date和work_dir参数
        output_dir (str): 输出目录
    """
    # 从模板文件中读取配置
    project_root = Path(__file__).resolve().parent.parent.parent
    template_path = project_root / "config" / "rawpath.yaml"
    with open(template_path, 'r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
    
    # 获取date和work_dir参数
    date = config_data.get("date", "")
    work_dir = config_data.get("work_dir", "")
    if not date or not work_dir:
        logger.error("模板文件中缺少date或work_dir参数")
        return None
    
    # 读取原始模板内容进行替换
    with open(template_path, 'r', encoding='utf-8') as file:
        template_content = file.read()
    config_content = template_content.replace("${date}", date).replace("${work_dir}", work_dir)
    # 确保输出目录存在
    output_path = project_root / "config" / "paths.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 写入生成的配置
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(config_content)
    logger.info(f"paths.yaml 生成成功: {output_path}")


#if __name__ == "__main__":
#    generate_paths_config()