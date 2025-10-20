
## 运行步骤 

启动虚拟环境
conda activate dataprocess
关闭虚拟环境
conda deactivate
使用run脚本运行程序
python -m run load /path/to/data
使用main函数运行程序
python -m src.main load --data-folder /path/to/data

## 目录

project_root/
│
├── config/                 # 配置文件目录
│   ├── paths.yaml         # 路径配置
│   ├── parameters.yaml    # 分析参数配置
│   └── database.yaml      # 数据库连接配置
│
├── src/                   # 源代码目录
│   ├── core/              # 核心功能模块
│   │   ├── data_manager.py    # 统一数据管理接口
│   │   ├── database.py       # 数据库操作封装
│   │   └── experiment.py     # 实验管理
│   │
│   ├── data_io/           # 数据输入输出模块
│   │   ├── tdms_reader_frequency_add.py    # 统一TDMS读取接口
│   │   ├── tdms_reader_frequency_one.py
│   │   ├── tdms_reader_frequency_add.py
│   │   └── tdms_reader_time.py
│   │
│   ├── preprocessing/     # 数据预处理模块
│   │   ├── background_subtraction.py
│   │   ├── signal_filtering.py
│   │   └── dc_removal.py
│   │
│   ├── analysis/          # 分析模块
│   │   ├── time_domain.py
│   │   ├── frequency_domain.py
│   │   ├── feature_extraction.py
│   │   └── peak_detection.py
│   │
│   │
│   ├── visualization/     # 可视化模块
│   │   ├── time_series_plots.py
│   │   ├── frequency_plots.py
│   │   ├── dft_images.py
│   │   └── summary_plots.py
│   │
│   ├── utils/             # 工具函数
│   │   ├── file_utils.py
│   │   ├── parallel_processing.py
│   │   └── logging_utils.py
│   │
│   └── main.py           # 主程序入口
│
├── data/                 # 数据目录（新增）
│   ├── raw/              # 原始数据
│   ├── processed/        # 处理后的数据
│   └── models/           # 训练好的模型
│
├── notebooks/            # Jupyter笔记本（用于探索性分析）
│
├── tests/                # 测试目录
│
└── requirements.txt      # 项目依赖