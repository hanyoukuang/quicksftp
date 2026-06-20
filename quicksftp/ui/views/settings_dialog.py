import logging
from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QFileDialog,
    QDialogButtonBox,
    QFormLayout,
    QCheckBox,
)

from quicksftp.core.settings import SettingsManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统设置")
        self.setMinimumWidth(400)

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Temporary download directory
        self.temp_dir_edit = QLineEdit()
        self.temp_dir_btn = QPushButton("浏览...")
        self.temp_dir_btn.clicked.connect(self.browse_temp_dir)

        temp_dir_layout = QHBoxLayout()
        temp_dir_layout.addWidget(self.temp_dir_edit)
        temp_dir_layout.addWidget(self.temp_dir_btn)
        form_layout.addRow("临时文件下载位置:", temp_dir_layout)

        # Font family
        self.font_combo = QComboBox()
        # Populate with fixed-pitch (monospace) fonts first if possible
        db = QFontDatabase()
        fonts = db.families()
        self.font_combo.addItems(fonts)
        form_layout.addRow("终端字体:", self.font_combo)

        # Font size
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 72)
        form_layout.addRow("终端文字大小:", self.size_spin)

        # Monitor setting
        self.monitor_checkbox = QCheckBox("在终端下方显示服务器实时资源状态 (类似 FinalShell)")
        form_layout.addRow("监控面板:", self.monitor_checkbox)

        layout.addLayout(form_layout)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def browse_temp_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择临时下载目录", self.temp_dir_edit.text()
        )
        if directory:
            self.temp_dir_edit.setText(directory)

    def load_settings(self):
        settings = SettingsManager.load()

        self.temp_dir_edit.setText(settings.get("temp_download_dir", ""))

        font_family = settings.get("font_family", "Courier New")
        idx = self.font_combo.findText(font_family)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        else:
            self.font_combo.setCurrentText(font_family)

        self.size_spin.setValue(settings.get("font_size", 14))
        self.monitor_checkbox.setChecked(settings.get("enable_monitor", False))

    def accept(self):
        settings = {
            "temp_download_dir": self.temp_dir_edit.text(),
            "font_family": self.font_combo.currentText(),
            "font_size": self.size_spin.value(),
            "enable_monitor": self.monitor_checkbox.isChecked(),
        }
        SettingsManager.save(settings)
        self.settings_changed.emit()
        super().accept()
