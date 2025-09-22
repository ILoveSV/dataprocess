
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
│   └── parameters.yaml    # 分析参数配置
│
├── src/                   # 源代码目录
│   ├── data_io/           # 数据输入输出模块
│   │   ├── tdms_reader_frequency_add.py
│   │   ├── tdms_reader_frequency_one.py
│   │   ├── tdms_reader_frequency.py
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
├── results/              # 结果输出目录
│   ├── time_domain/
│   ├── frequency_domain/
│   ├── images/
│   └── reports/
│
├── run.py
│
├── README.md
│
└── requirements.txt      # 项目依赖