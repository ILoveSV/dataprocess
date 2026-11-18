#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试优化版notebook（无GUI）"""

import json, time, sys
import matplotlib
matplotlib.use('Agg')  # 无GUI后端

with open('time_freq_analysis.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

namespace = {}
start = time.time()
errors = []

for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        try:
            exec(src, namespace)
        except Exception as e:
            errors.append((i, type(e).__name__, str(e)[:80]))

elapsed = time.time() - start

print('\n' + '='*50)
print(f'优化版测试结果')
print('='*50)
print(f'总耗时: {elapsed:.2f}秒')
print(f'错误数: {len(errors)}')
if errors:
    for idx, ename, evalue in errors:
        print(f'  Cell {idx}: {ename} - {evalue}')
else:
    print('✅ 所有cells通过!')
print('='*50)