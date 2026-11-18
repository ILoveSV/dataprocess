# -*- coding: utf-8 -*-
"""
共享组件模块
包含可复用的GUI组件，避免循环导入问题
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QLineEdit, QListWidget, QAbstractItemView,
    QSizePolicy
)
from PyQt5.QtCore import pyqtSignal


class ExperimentStateMapper(QWidget):
    """实验状态对应关系组件

    每行包含：
    - 下拉菜单：从全局实验状态注册表选择"实验状态1"等
    - 输入框：用户手动填入补充信息
    同时保留通道选择功能（用于多通道数据选通道）。
    """

    state_changed = pyqtSignal()

    def __init__(self, label_text="A对应的实验状态", parent=None):
        super().__init__(parent)
        self._current_data = None
        self._label_text = label_text
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        ch_mode_row = QHBoxLayout()
        ch_mode_row.setContentsMargins(0, 0, 0, 0)
        self.channel_mode_combo = QComboBox()
        self.channel_mode_combo.addItem("全部通道", "all")
        self.channel_mode_combo.addItem("单通道", "single")
        self.channel_mode_combo.addItem("指定通道", "multi")
        self.channel_mode_combo.currentIndexChanged.connect(self._on_ch_mode_changed)
        ch_mode_row.addWidget(QLabel("通道模式:"))
        ch_mode_row.addWidget(self.channel_mode_combo)
        layout.addLayout(ch_mode_row)

        ch_row = QHBoxLayout()
        ch_row.setContentsMargins(0, 0, 0, 0)
        self.channel_label = QLabel("数据通道:")
        self.channel_combo = QComboBox()
        self.channel_combo.setMinimumWidth(120)
        self.channel_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.channel_combo.currentIndexChanged.connect(self._on_changed)
        ch_row.addWidget(self.channel_label)
        ch_row.addWidget(self.channel_combo, stretch=1)
        layout.addLayout(ch_row)

        self.channel_multi_list = QListWidget()
        self.channel_multi_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.channel_multi_list.setMaximumHeight(80)
        self.channel_multi_list.itemSelectionChanged.connect(self._on_changed)
        layout.addWidget(self.channel_multi_list)

        st_row = QHBoxLayout()
        st_row.setContentsMargins(0, 0, 0, 0)
        self.state_label = QLabel(self._label_text + ":")
        self.state_combo = QComboBox()
        self.state_combo.setMinimumWidth(160)
        self.state_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.state_combo.setEditable(False)
        self.state_combo.currentIndexChanged.connect(self._on_changed)
        self.state_combo.setEnabled(False)

        self.supplement_label = QLabel("补充说明:")
        self.supplement_edit = QLineEdit()
        self.supplement_edit.setPlaceholderText("可手动填入补充信息")
        self.supplement_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.supplement_edit.textChanged.connect(self._on_changed)

        st_row.addWidget(self.state_label)
        st_row.addWidget(self.state_combo, stretch=1)
        st_row.addWidget(self.supplement_label)
        st_row.addWidget(self.supplement_edit, stretch=1)
        layout.addLayout(st_row)
        self._on_ch_mode_changed()

    def _on_ch_mode_changed(self, *args):
        mode = self.channel_mode_combo.currentData()
        is_single = (mode == 'single')
        is_multi = (mode == 'multi')
        self.channel_label.setVisible(is_single)
        self.channel_combo.setVisible(is_single)
        self.channel_multi_list.setVisible(is_multi)
        self._on_changed()

    def _on_changed(self, *args):
        self.state_changed.emit()

    def set_data(self, data):
        if data is None:
            return
        self._current_data = data
        n = data.shape[1] if data.ndim > 1 else 1
        ch_names = [f"CH{i+1:02d}" for i in range(max(1, n))]
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        for nm in ch_names:
            self.channel_combo.addItem(nm)
        self.channel_combo.blockSignals(False)
        if self.channel_combo.count() > 0:
            self.channel_combo.setCurrentIndex(0)
        self.channel_multi_list.blockSignals(True)
        self.channel_multi_list.clear()
        for nm in ch_names:
            self.channel_multi_list.addItem(nm)
        self.channel_multi_list.blockSignals(False)
        self._on_changed()

    def refresh_states(self, state_names):
        """从全局注册表刷新实验状态下拉菜单"""
        self.state_combo.blockSignals(True)
        self.state_combo.clear()
        self.state_combo.addItem("（未选择）", "")
        for name in state_names:
            self.state_combo.addItem(name, name)
        self.state_combo.blockSignals(False)
        self.state_combo.setEnabled(len(state_names) > 0)

    def get_selected_state(self):
        """获取选中的实验状态名称"""
        return self.state_combo.currentData()

    def get_supplement(self):
        """获取补充说明文本"""
        return self.supplement_edit.text()

    def get_channel_mode(self):
        """获取通道模式"""
        return self.channel_mode_combo.currentData()

    def get_selected_channels(self):
        """获取选中的通道列表"""
        mode = self.get_channel_mode()
        if mode == 'all':
            n = self._current_data.shape[1] if self._current_data is not None and self._current_data.ndim > 1 else 1
            return [f"CH{i+1:02d}" for i in range(max(1, n))]
        elif mode == 'single':
            return [self.channel_combo.currentText()]
        elif mode == 'multi':
            return [item.text() for item in self.channel_multi_list.selectedItems()]
        return []

    def set_state(self, state_name):
        """设置当前选中的实验状态（用于Tab4推送关联）"""
        idx = self.state_combo.findData(state_name)
        if idx >= 0:
            self.state_combo.setCurrentIndex(idx)
            return True
        return False

    def get_selected_channel(self):
        return self.channel_combo.currentIndex()

    def get_channel_name(self):
        return self.channel_combo.currentText()

    def get_state_name(self):
        data = self.state_combo.currentData()
        return data if data else ""

    def get_display_name(self):
        """返回用于表格显示的名称：优先实验状态名，否则通道名+补充"""
        sn = self.get_state_name()
        if sn:
            sup = self.get_supplement()
            return f"{sn}({sup})" if sup else sn
        ch = self.get_channel_name()
        sup = self.get_supplement()
        return f"{ch}({sup})" if sup else ch