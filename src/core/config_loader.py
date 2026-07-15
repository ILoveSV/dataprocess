from pathlib import Path
import logging

import yaml


logger = logging.getLogger('data_process')


def find_project_root(start_path=None):
    """Find the project root by walking upward until config/paths.yaml exists."""
    current = Path(start_path or __file__).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "config" / "paths.yaml").exists():
            return candidate

    raise FileNotFoundError("Could not find project root containing config/paths.yaml")


def load_config():
    """Load config/paths.yaml without hard-coding package depth."""
    project_root = find_project_root()
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    logger.info("Loaded paths config: %s", config_path)
    return config

