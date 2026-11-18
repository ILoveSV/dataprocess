#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

with open('time_freq_analysis.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Set kernel to signal_proc
nb['metadata']['kernelspec'] = {
    'display_name': 'Python (Signal Processing)',
    'language': 'python',
    'name': 'signal_proc'
}

# Add auto-install cell at the top
install_cell = {
    'cell_type': 'code',
    'execution_count': None,
    'metadata': {},
    'outputs': [],
    'source': [
        '# 0. 自动安装依赖（如缺失）\n',
        'import subprocess\n',
        'import sys\n',
        '\n',
        'required_packages = [\'matplotlib\', \'numpy\', \'scipy\', \'pywavelets\']\n',
        'missing = []\n',
        'for pkg in required_packages:\n',
        '    try:\n',
        '        __import__(pkg.replace(\'pywavelets\', \'pywt\'))\n',
        '    except ImportError:\n',
        '        missing.append(pkg)\n',
        '\n',
        'if missing:\n',
        '    print(f\'安装缺失依赖: {missing}\')\n',
        '    subprocess.check_call([sys.executable, \'-m\', \'pip\', \'install\'] + missing)\n',
        'else:\n',
        '    print(\'所有依赖已安装\')'
    ]
}

# Insert at position 1 (after title)
nb['cells'].insert(1, install_cell)

with open('time_freq_analysis.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Notebook updated with auto-install cell and kernel metadata')
print('Total cells:', len(nb['cells']))