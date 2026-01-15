
## 运行步骤 

启动虚拟环境
conda activate dataprocess
关闭虚拟环境
conda deactivate
使用run脚本运行程序
python -m run load /path/to/data
使用main函数运行程序
python -m src.main load(此处为输入的argument) 
配置地址文件
rawpath.yaml将日期改为相应的文件名，如2025.11.11采集数据保存在2025.11.11文件夹下，即可读取该文件夹的内容

## 目录

project_root/
│
├── config/                # 配置文件目录
│   ├── paths.yaml         # 实际读取的路径配置，自动更新，不要更改此文件
│   ├── rawpath.yaml       # 路径生成模板，手动更改此文件
│   ├── logging.yaml       # 日志配置
│   └── parameters.yaml    # 分析参数配置
│
├── src/                   # 源代码目录
│   ├── core/              # 核心功能模块                （暂不使用）
│   │   ├── data_manager.py   # 统一数据管理接口
│   │   ├── database.py       # 数据库操作封装
│   │   └── experiment.py     # 实验管理
│   │
│   ├── data_io/           # 数据输入输出模块
│   │   ├── sql_tdms_reader.py                  # 不使用，sql存储
│   │   ├── tdms_reader_time.py                 # 1.生成时间-电压CSV文件
│   │   ├── tdms_reader_frequency_average.py    # 2.将每个CSV文件进行FFT变换
│   │   ├── tdms_reader_frequency_one.py        # 不使用
│   │   └── tdms_reader_frequency.py            # 3.平均所有数据输出一个FFT文件
│   │
│   ├── preprocessing/     # 数据预处理模块               （暂不使用）
│   │   ├── background_subtraction.py
│   │   ├── signal_filtering.py
│   │   └── dc_removal.py
│   │
│   ├── analysis/          # 分析模块                     （暂不使用）
│   │   ├── time_domain.py
│   │   ├── frequency_domain.py
│   │   ├── feature_extraction.py
│   │   └── peak_detection.py
│   │
│   ├── visualization/     # 可视化模块
│   │   ├── time_series_plots.py
│   │   ├── frequency_plots.py
│   │   ├── dft_images.py
│   │   └── summary_plots.py
│   │
│   ├── utils/             # 工具模块
│   │   ├── file_utils.py                        # 路径配置文件生成
│   │   └── logging_utils.py                     # 启动日志模块
│   │
│   └── main.py           # 主程序入口
│
├── data/                 # 数据目录（新增）
│   ├── raw/              # 原始数据
│   ├── processed/        # 处理后的数据
│   └── models/           # 训练好的模型
│
├── logs/                 # 日志存放文件夹
│
└── requirements.txt      # 项目依赖