#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

with open('time_freq_analysis.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Add diagnostic cell at the very beginning (after title)
diagnostic_cell = {
    'cell_type': 'code',
    'execution_count': None,
    'metadata': {},
    'outputs': [],
    'source': [
        '# 🔍 环境诊断\n',
        'import sys\n',
        'print(f\"Python路径: {sys.executable}\")\n',
        'print(f\"Python版本: {sys.version.split()[0]}\")\n',
        '\n',
        '# 检查关键依赖\n',
        'deps = {\"matplotlib\": \"matplotlib\", \"numpy\": \"numpy\", \"scipy\": \"scipy\", \"pywavelets\": \"pywt\"}\n',
        'for pkg, import_name in deps.items():\n',
        '    try:\n',
        '        mod = __import__(import_name)\n',
        '        print(f\"✓ {pkg}: {mod.__version__}\")\n',
        '    except ImportError as e:\n',
        '        print(f\"✗ {pkg}: 未安装 - {e}\")\n',
        '        print(f\"  请执行: pip install {pkg}\")\n',
        '\n',
        '# 自动安装缺失依赖\n',
        'import subprocess\n',
        'missing = []\n',
        'for pkg, import_name in deps.items():\n',
        '    try:\n',
        '        __import__(import_name)\n',
        '    except ImportError:\n',
        '        missing.append(pkg)\n',
        '\n',
        'if missing:\n',
        '    print(f\"\\n自动安装缺失依赖: {missing}\")\n',
        '    subprocess.check_call([sys.executable, \"-m\", \"pip\", \"install\"] + missing)\n',
        '    print(\"安装完成!\")\n',
        'else:\n',
        '    print(\"\\n✅ 所有依赖已就绪!\")'
    ]
}

# Insert at position 1 (after title)
nb['cells'].insert(1, diagnostic_cell)

with open('time_freq_analysis.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Notebook updated with diagnostic cell')
print('Total cells:', len(nb['cells']))