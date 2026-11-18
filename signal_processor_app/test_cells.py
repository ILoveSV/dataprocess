#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import traceback

with open('time_freq_analysis.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print('=' * 60)
print('Testing each code cell individually')
print('=' * 60)

# Create a shared namespace for execution
namespace = {}
errors = []

for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        print(f'\n--- Cell {i} ---')
        try:
            exec(src, namespace)
            print('✓ PASSED')
        except Exception as e:
            print('✗ FAILED:', type(e).__name__)
            print('  Error:', str(e)[:100])
            errors.append((i, type(e).__name__, str(e)))

print('\n' + '=' * 60)
print(f'Total errors: {len(errors)}')
if errors:
    print('Failed cells:')
    for idx, ename, evalue in errors:
        print(f'  Cell {idx}: {ename} - {evalue[:50]}')
else:
    print('All cells passed!')