# ui/views/user_widgets.py
import logging
import datetime
import os

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSplitter,
    QButtonGroup,
    QSizePolicy,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize

from quicksftp.ui.components.terminal_widget import SSHPtyWidget
from quicksftp.ui.views.local_widgets import LocalFileWidget
from quicksftp.ui.views.remote_file_widget import RemoteFileWidget
from quicksftp.ui.views.transport_widgets import TransferSetupWidget
from quicksftp.ui.views.snippets_widget import QuickSnippetsWidget
from quicksftp.ui.views.directory_diff_dialog import DirectoryDiffDialog

logger = logging.getLogger(__name__)



class ControlWidget(QWidget):
    """
    左侧导航栏
    已彻底解耦，仅负责展示选项，不包含任何外部组件的调用逻辑
    """

    currentRowChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedWidth(48)  # 极其紧凑的 PyCharm/VSCode 风格侧边栏
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.btn_group.idClicked.connect(self.currentRowChanged.emit)

        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        self._items = [
            ("terminal", "SSH 终端"),
            ("folder", "文件浏览"),
            ("transfer", "传输管理"),
        ]

        for i, (icon_name, tooltip) in enumerate(self._items):
            btn = QPushButton()
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            layout.addWidget(btn)
            self.btn_group.addButton(btn, i)

        # 添加紧跟着最后一个按钮的快捷面板开关
        self.snippets_toggle_btn = QPushButton("⚡面板")
        self.snippets_toggle_btn.setCheckable(True)
        self.snippets_toggle_btn.setChecked(True)
        self.snippets_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snippets_toggle_btn.setToolTip("显示/隐藏快捷面板")
        layout.addWidget(self.snippets_toggle_btn)

        layout.addStretch()

        # 默认选中第一项并初始化主题
        self.btn_group.button(0).setChecked(True)
        self.update_theme(True)  # Default dark mode

    def update_theme(self, is_dark: bool):
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        icons_dir = os.path.join(base_dir, "assets", "icons")
        suffix = "_dark.svg" if is_dark else "_light.svg"

        for i, (icon_base, tooltip) in enumerate(self._items):
            btn = self.btn_group.button(i)
            icon_path = os.path.join(icons_dir, f"{icon_base}{suffix}")
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(24, 24))
            else:
                btn.setText(tooltip[0])

            # 极简图标按钮样式
            btn.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    background: transparent;
                    padding: 10px 0;
                }}
                QPushButton:checked {{
                    border-left: 3px solid {"#007acc" if is_dark else "#4a6da7"};
                    background: {"#37373d" if is_dark else "#e4e4e4"};
                }}
                QPushButton:hover:!checked {{
                    background: {"#2b2d2e" if is_dark else "#ebebeb"};
                }}
            """)
        
        self.snippets_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                padding: 10px 0;
                color: {"#888" if is_dark else "#555"};
            }}
            QPushButton:checked {{
                color: {"#fff" if is_dark else "#000"};
            }}
        """)

    def setCurrentRow(self, row: int):
        btn = self.btn_group.button(row)
        if btn:
            btn.setChecked(True)
            self.currentRowChanged.emit(row)


class UserSFTPWidget(QWidget):
    def __init__(self, sftp_tab_widget):
        super().__init__()
        self.sftp_tab_widget = sftp_tab_widget
        self.info = sftp_tab_widget.info
        self.transfer_dialog = None

        # --- 左侧：全新的本地文件面板 ---
        self.local_file_widget = LocalFileWidget(self.sftp_tab_widget)

        # --- 右侧：原有的远端文件面板 ---
        self.remote_file_widget = RemoteFileWidget(sftp_tab_widget)
        self.back_button = QPushButton("⬆️ 返回上级")

        # 将 QLineEdit 改为可编辑的 QComboBox
        self.path_combo = QComboBox()
        self.path_combo.setEditable(True)  # 允许用户直接在框内输入路径

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索本目录 (回车)")
        self.search_edit.setClearButtonEnabled(True)  # 右侧自带清除 X 按钮
        self.search_edit.setFixedWidth(160)

        # 初始化当前路径
        current_path = self.info.realpath(".")
        self.path_combo.addItem(current_path)
        self.path_combo.setCurrentText(current_path)

        self.get_button = QPushButton("⬇️ 下载")
        self.put_button = QPushButton("⬆️ 上传")

        self.show_hidden_btn = QPushButton("👁️ 显示隐藏")
        self.show_hidden_btn.setCheckable(True)

        self.diff_btn = QPushButton("📊 目录比较")

        self.init_ui()
        self.remote_file_widget.refresh()

    def init_ui(self):
        self.remote_file_widget.set_menu()
        self.remote_file_widget.path_change_msg.connect(self.display_path)

        self.path_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setFixedWidth(140)

        # 组装右侧（远端）的顶栏
        remote_hbox = QHBoxLayout()
        remote_hbox.setContentsMargins(0, 0, 0, 5)
        remote_hbox.setSpacing(6)
        
        # Navigation
        remote_hbox.addWidget(self.back_button)
        remote_hbox.addWidget(self.path_combo)
        
        # Actions
        remote_hbox.addWidget(self.put_button)
        remote_hbox.addWidget(self.get_button)
        remote_hbox.addWidget(self.diff_btn)
        remote_hbox.addWidget(self.show_hidden_btn)
        
        # Search
        remote_hbox.addSpacing(10)
        remote_hbox.addWidget(self.search_edit)

        remote_vbox = QVBoxLayout()
        remote_vbox.setContentsMargins(0, 0, 0, 0)
        remote_vbox.addLayout(remote_hbox)
        remote_vbox.addWidget(self.remote_file_widget)

        remote_container = QWidget()
        remote_container.setLayout(remote_vbox)

        # QSplitter 组装左右布局
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.local_file_widget)
        self.splitter.addWidget(remote_container)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)

        # 信号绑定
        self.back_button.clicked.connect(self.back_parent_path)
        self.get_button.clicked.connect(self.get)
        self.put_button.clicked.connect(self.put)

        # 绑定 ComboBox 的激活信号（回车或点击下拉选项）
        self.path_combo.activated.connect(self.on_path_combo_activated)
        self.show_hidden_btn.toggled.connect(self.toggle_hidden_files)
        self.search_edit.returnPressed.connect(self.on_search)
        self.search_edit.textChanged.connect(self.on_search_text_changed)

        self.diff_btn.clicked.connect(self._show_diff)

    def back_parent_path(self):
        try:
            self.info.chdir("..")
            self.remote_file_widget.refresh()
            self.display_path(self.info.realpath("."))
        except Exception as e:
            logger.warning(f"Failed to go back: {e}")

    def on_search(self):
        keyword = self.search_edit.text().strip()
        if keyword:
            self.remote_file_widget.search(keyword)
        else:
            self.remote_file_widget.refresh()

    def on_search_text_changed(self, text):
        """用户点击清空按钮时，立即恢复当前目录的默认视图"""
        if not text.strip():
            self.remote_file_widget.refresh()

    def on_path_combo_activated(self):
        """当用户在输入框按回车，或在下拉列表中选择历史路径时触发"""
        path = self.path_combo.currentText().strip()
        if not path:
            return
        try:
            # 尝试切换底层目录
            self.info.chdir(path)
            # 获取进入后的绝对路径
            new_path = self.info.realpath(".")
            # 刷新文件列表
            self.remote_file_widget.refresh()
            # 更新下拉框显示并加入历史
            self.display_path(new_path)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"无法切换到路径 {path}:\n{e}")
            # 失败后，恢复输入框为当前的实际合法路径
            self.display_path(self.info.getcwd())

    def toggle_hidden_files(self, checked: bool):
        self.remote_file_widget.show_hidden = checked
        self.remote_file_widget.refresh()

    def get(self):
        """打开下载参数配置面板"""
        if self.transfer_dialog is not None:
            self.transfer_dialog.close()
            self.transfer_dialog.deleteLater()

        self.transfer_dialog = TransferSetupWidget(self.sftp_tab_widget, mode="GET")
        self.transfer_dialog.show()

    def put(self):
        """打开上传参数配置面板"""
        if self.transfer_dialog is not None:
            self.transfer_dialog.close()
            self.transfer_dialog.deleteLater()

        self.transfer_dialog = TransferSetupWidget(self.sftp_tab_widget, mode="PUT")
        self.transfer_dialog.show()


    @Slot(str)
    def display_path(self, path: str):
        self.path_combo.blockSignals(True)
        if self.path_combo.findText(path) == -1:
            self.path_combo.insertItem(0, path)
        self.path_combo.setCurrentText(path)
        self.path_combo.blockSignals(False)

    def _show_diff(self):
        local_idx = self.local_file_widget.tree.rootIndex()
        local_dir = self.local_file_widget.model.filePath(local_idx)

        local_files = {}
        try:
            for entry in os.scandir(local_dir):
                if entry.name in (".", ".."):
                    continue
                size = -1 if entry.is_dir() else entry.stat().st_size
                local_files[entry.name] = {"size": size}
        except Exception as e:
            logger.warning(f"Local file scan failed for dir diff: {e}")

        remote_files = {}
        try:
            raw_entries = getattr(self.remote_file_widget, "last_raw_entries", [])
            for entry in raw_entries:
                is_dir = entry.attrs.type == 2
                size_val = -1 if is_dir else getattr(entry.attrs, "size", 0)
                mtime_val = getattr(entry.attrs, "mtime", 0)
                mtime_str = datetime.datetime.fromtimestamp(mtime_val).strftime("%Y-%m-%d %H:%M:%S") if mtime_val else ""
                
                remote_files[entry.filename] = {
                    "size": size_val,
                    "time": mtime_str,
                }
        except Exception as e:
            logger.warning(f"Remote file read failed for dir diff: {e}")

        dialog = DirectoryDiffDialog(self, local_files, remote_files)
        dialog.exec()


class TerminalPanel(QWidget):
    """新的主容器：组合原有的 SSH 终端(左) 和 快捷命令面板(右)"""

    def __init__(self, info):
        super().__init__()
        self.info = info
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. 实例化原有终端组件
        self.ssh_pty_widget = SSHPtyWidget(self.info)

        # Monitor widget
        from quicksftp.ui.views.monitor_widget import SystemMonitorWidget
        self.monitor_widget = SystemMonitorWidget(self.info)

        # Left Vertical Splitter
        self.left_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_v_splitter.addWidget(self.ssh_pty_widget)
        self.left_v_splitter.addWidget(self.monitor_widget)
        self.left_v_splitter.setStretchFactor(0, 10)
        self.left_v_splitter.setStretchFactor(1, 1)

        # 2. 生成站点的唯一标识 (例如 root@192.168.1.10:22)
        site_id = f"{self.info.username}@{self.info.host}:{self.info.port}"

        # 3. 实例化新增的快捷面板 (传入站点标识)
        self.snippets_widget = QuickSnippetsWidget(site_id)

        # 4. 将命令写入到终端输入流
        self.snippets_widget.command_triggered.connect(
            self.ssh_pty_widget.bridge.on_input
        )

        self.splitter.addWidget(self.snippets_widget)
        self.splitter.addWidget(self.left_v_splitter)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        layout.addWidget(self.splitter)
        self._apply_settings()

    def toggle_snippets(self, checked: bool):
        self.snippets_widget.setVisible(checked)
        if checked:
            total = self.splitter.width()
            snippet_w = int(total * 0.3)
            self.splitter.setSizes([snippet_w, total - snippet_w])

    def _apply_settings(self):
        from quicksftp.core.settings import SettingsManager
        enabled = SettingsManager.get("enable_monitor", False)
        self.monitor_widget.set_enabled(enabled)
