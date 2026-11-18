# -*- coding: utf-8 -*-
"""
实验状态管理模块
- 全局实验状态注册表
- 实验状态定义（TC12/TC34）
- 报告BLOCK序号生成
"""
import os
import json
from datetime import datetime


# ========================
# 全局实验状态注册表
# ========================

class ExperimentStateRegistry:
    """全局实验状态注册表（单例）

    管理所有由 Tab5 生成的实验状态，供 Tab1/2/3/4 引用。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._states = []
            cls._instance._counter = 0
        return cls._instance

    def add_state(self, state):
        """添加一个实验状态

        state: dict，至少包含 'id', 'name', 'block_no', 'type'(TC12/TC34), 'params'
        """
        self._counter += 1
        state.setdefault('id', self._counter)
        state.setdefault('name', f"实验状态{self._counter}")
        state.setdefault('block_no', f"{state['name']}{datetime.now().strftime('%Y%m%d%H%M')}处理数据")
        self._states.append(state)
        return state

    def get_all_states(self):
        return list(self._states)

    def get_state_names(self):
        """返回所有实验状态名称列表，供下拉菜单使用"""
        return [s['name'] for s in self._states]

    def get_state_by_name(self, name):
        for s in self._states:
            if s['name'] == name:
                return s
        return None

    def get_state_by_id(self, state_id):
        for s in self._states:
            if s['id'] == state_id:
                return s
        return None

    def remove_state(self, state_id):
        """根据ID删除一个实验状态"""
        for i, s in enumerate(self._states):
            if s['id'] == state_id:
                return self._states.pop(i)
        return None

    def clear(self):
        self._states.clear()
        self._counter = 0

    def to_markdown_table(self, names=None):
        """将指定实验状态转为 markdown 表格

        names: 指定状态名列表，None则全部
        """
        if not self._states:
            return "（暂无实验状态记录）"

        rows = []
        for s in self._states:
            if names is not None and s['name'] not in names:
                continue
            rows.append(s)

        if not rows:
            return "（未找到匹配的实验状态）"

        # 收集所有参数键
        all_keys = ['序号', '状态名称', '类型']
        param_keys = []
        for s in rows:
            for k in s.get('params', {}).keys():
                if k not in param_keys:
                    param_keys.append(k)
        all_keys.extend(param_keys)

        lines = []
        lines.append("| " + " | ".join(all_keys) + " |")
        lines.append("| " + " | ".join(["---"] * len(all_keys)) + " |")
        for s in rows:
            vals = [
                str(s.get('id', '')),
                s.get('name', ''),
                s.get('type', ''),
            ]
            p = s.get('params', {})
            for k in param_keys:
                v = p.get(k, '')
                vals.append(str(v) if v != '' else '-')
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)


# 全局单例
STATE_REGISTRY = ExperimentStateRegistry()


# ========================
# 报告BLOCK管理
# ========================

class ReportBlock:
    """一个报告BLOCK"""

    def __init__(self, source_tab, title, content_md, images=None):
        """
        source_tab: 来源Tab名（如 'Tab1时域相似性'）
        title: BLOCK标题
        content_md: markdown内容
        images: 图片路径列表（可选）
        """
        self.source_tab = source_tab
        self.title = title
        self.content_md = content_md
        self.images = images or []
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def to_markdown(self):
        parts = []
        parts.append(f"## {self.title}")
        parts.append("")
        parts.append(f"> 来源: {self.source_tab} | 生成时间: {self.created_at}")
        parts.append("")
        parts.append(self.content_md)
        return "\n".join(parts)


class ReportManager:
    """全局报告BLOCK管理器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._blocks = []
            cls._instance._report_dir = ''
        return cls._instance

    def add_block(self, block):
        self._blocks.append(block)
        return block

    @property
    def blocks(self):
        """获取所有BLOCK的列表"""
        return list(self._blocks)

    def get_all_blocks(self):
        return list(self._blocks)

    def remove_block(self, index):
        if 0 <= index < len(self._blocks):
            self._blocks.pop(index)

    def clear(self):
        self._blocks.clear()

    def set_report_dir(self, report_dir):
        """设置报告保存目录"""
        self._report_dir = report_dir

    def get_report_dir(self):
        """获取报告保存目录"""
        return self._report_dir

    def to_full_markdown(self):
        if not self._blocks:
            return "# 实验报告\n\n（暂无内容）\n"
        parts = ["# NPMEMS_TC12 实验报告", ""]
        parts.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        parts.append("")
        parts.append("---")
        parts.append("")
        for i, b in enumerate(self._blocks, 1):
            parts.append(f"### BLOCK {i}")
            parts.append("")
            parts.append(b.to_markdown())
            parts.append("")
            parts.append("---")
            parts.append("")
        return "\n".join(parts)

    def to_markdown(self):
        """导出完整报告Markdown的别名方法"""
        return self.to_full_markdown()


REPORT_MANAGER = ReportManager()


# ========================
# 激励策略辅助
# ========================

WAVE_ORDER_LABELS = {
    1: '一阶波',
    2: '二阶波',
    3: '三阶波',
    4: '四阶波',
}


def format_wave_strategy(order, params):
    """格式化激励策略为字符串

    order: 1~4
    params: dict，键为 V1,T1,[V2,T2,...],T0
    """
    label = WAVE_ORDER_LABELS.get(order, f'{order}阶波')
    parts = [label, '激励策略: ']
    segs = []
    i = 1
    while True:
        vk = f'V{i}'
        tk = f'T{i}'
        if vk in params and tk in params:
            segs.append(f"V{i}={params[vk]}, T{i}={params[tk]}")
            i += 1
        else:
            break
    t0 = params.get('T0', '')
    if segs:
        parts.append(' | '.join(segs))
    if t0 != '':
        parts.append(f" 重复周期T0={t0}")
    return ''.join(parts)
