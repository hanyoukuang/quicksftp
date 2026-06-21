import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox, QLabel

from quicksftp.ui.views.sftp_tab_widget import SFTPTabWidget
from quicksftp.ui.views.site_manager import SiteManagerWidget
from quicksftp.ui.views.port_forward_dialog import PortForwardDialog
from quicksftp.ui.views.settings_dialog import SettingsDialog
from quicksftp.core.settings import SettingsManager
from quicksftp.core.config import get_data_path


class MainWindow(QMainWindow):
    """
    全局主窗口，承载多标签页的 SFTP/SSH 会话
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickSFTP - 多会话终端")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(int(screen.width() * 0.7), int(screen.height() * 0.65))

        # 1. 初始化中心 TabWidget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)  # 允许标签页关闭
        self.tab_widget.tabCloseRequested.connect(self.close_tab)  # 绑定关闭事件
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tab_widget)

        # 2. 初始化底部状态栏
        self.status_bar = self.statusBar()
        self.status_label = QLabel(" ⚡ 准备就绪 ")
        self.status_bar.addWidget(self.status_label)
        
        from quicksftp.ui.views.monitor_widget import SystemMonitorWidget
        self.monitor_widget = SystemMonitorWidget(None)
        self.status_bar.addWidget(self.monitor_widget, 1)
        self.monitor_widget.setVisible(False)

        # 2. 顶部工具栏 (随时唤出站点管理器)
        toolbar = self.addToolBar("主控制栏")
        new_session_action = QAction("🔌 新建连接", self)
        new_session_action.triggered.connect(self.open_site_manager)
        toolbar.addAction(new_session_action)

        self.dark_mode_action = QAction("🌙 暗色模式", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.triggered.connect(self._toggle_dark_mode)
        toolbar.addAction(self.dark_mode_action)

        port_fwd_action = QAction("🔗 端口转发", self)
        port_fwd_action.triggered.connect(self._open_port_forward)
        toolbar.addAction(port_fwd_action)

        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        self._dark_mode = False
        self._apply_theme()

        self.site_manager = None
        self._port_fwd_dialog = None

    def _on_tab_changed(self, index: int):
        if index == -1:
            self.status_label.setText(" ⚡ 准备就绪 - 没有打开的连接 ")
            self.monitor_widget.setVisible(False)
            self.monitor_widget.set_info(None)
            return

        widget = self.tab_widget.widget(index)
        if hasattr(widget, "info"):
            host = widget._host
            user = widget._username
            port = widget._port
            state = (
                "🟢 已连接"
                if getattr(widget, "_health_status", True)
                else "🔴 连接断开"
            )
            self.status_label.setText(f" {state} | {user}@{host}:{port} ")
            
            self.monitor_widget.set_info(widget.info)
            enabled = SettingsManager.get("enable_monitor", False)
            self.monitor_widget.set_enabled(enabled)

    def _open_port_forward(self):
        current = self.tab_widget.currentWidget()
        if not current or not hasattr(current, "info"):
            return
        if self._port_fwd_dialog is None:
            self._port_fwd_dialog = PortForwardDialog(self, session=current.info)
        else:
            self._port_fwd_dialog._session = current.info
        self._port_fwd_dialog.show()
        self._port_fwd_dialog.raise_()
        self._port_fwd_dialog.activateWindow()

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self.apply_global_settings)
        dialog.exec()

    def apply_global_settings(self):
        # Update existing terminals
        font_family = SettingsManager.get("font_family")
        font_size = SettingsManager.get("font_size")
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, "terminal_panel"):
                pty = tab.terminal_panel.ssh_pty_widget
                pty.terminal_font.setFamily(font_family)
                pty.set_font_size(font_size)
                
        # Update monitor visibility
        if self.tab_widget.count() > 0:
            enabled = SettingsManager.get("enable_monitor", False)
            self.monitor_widget.set_enabled(enabled)

    def _toggle_dark_mode(self, checked: bool):
        self._dark_mode = checked
        self.dark_mode_action.setText("☀️ 亮色模式" if checked else "🌙 暗色模式")
        self._apply_theme()

    def _apply_theme(self):
        # Update control widgets in all tabs
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, "control_widget") and hasattr(
                tab.control_widget, "update_theme"
            ):
                tab.control_widget.update_theme(self._dark_mode)

        if not self._dark_mode:
            # 明确设置亮色模式样式
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #f5f5f5; color: #333; }
                QTabWidget::pane { background: #ffffff; border: none; border-top: 1px solid #ddd; }
                QTabBar { background: #ececec; }
                QTabBar::tab { background: #ececec; color: #666; padding: 4px 12px; font-size: 12px; border: none; border-right: 1px solid #ddd; }
                QTabBar::tab:selected { background: #ffffff; color: #000; border-top: 2px solid #4a6da7; border-right: 1px solid #ddd; border-left: 1px solid #ddd; }
                QTabBar::tab:hover:!selected { background: #e4e4e4; }
                QToolBar { background: #ececec; border: none; border-bottom: 1px solid #ddd; padding: 4px; spacing: 10px; }
                QToolButton { font-size: 14px; padding: 6px 12px; border-radius: 4px; color: #333; }
                QToolButton:hover { background: #dcdcdc; }
                QStatusBar { background: #ececec; color: #333; border-top: 1px solid #ddd; }
                QStatusBar QLabel { padding: 0 5px; }
                QLineEdit, QComboBox, QSpinBox { background: #fff; color: #333; border: 1px solid #aaa; border-radius: 2px; padding: 2px; }
                QPushButton { background: #e0e0e0; color: #333; padding: 4px 10px; border-radius: 3px; border: 1px solid #ccc; }
                QPushButton:hover { background: #d0d0d0; }
                QListWidget, QTreeView { background: #fff; color: #333; border: none; }
                QListWidget::item:selected, QTreeView::item:selected { background: #4a6da7; color: #fff; }
                QHeaderView::section { background: #ececec; color: #333; border: none; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc; padding: 4px; }
                QProgressBar { background: #fff; border: 1px solid #ccc; text-align: center; }
                QProgressBar::chunk { background: #4a9; }
                QSplitter::handle { background: transparent; }
                QMenu { background: #f5f5f5; color: #333; border: 1px solid #ccc; }
                QMenu::item:selected { background: #4a6da7; color: #fff; }
                QDialog { background: #f5f5f5; }
                
                /* Light Mode Scrollbar */
                QScrollBar:vertical { border: none; background: transparent; width: 10px; margin: 0px; }
                QScrollBar::handle:vertical { background: rgba(0,0,0,0.2); min-height: 20px; border-radius: 5px; }
                QScrollBar::handle:vertical:hover { background: rgba(0,0,0,0.4); }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
                
                QScrollBar:horizontal { border: none; background: transparent; height: 10px; margin: 0px; }
                QScrollBar::handle:horizontal { background: rgba(0,0,0,0.2); min-width: 20px; border-radius: 5px; }
                QScrollBar::handle:horizontal:hover { background: rgba(0,0,0,0.4); }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
            """)
            return

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e1e; color: #cccccc; }
            QTabWidget::pane { background: #1e1e1e; border: none; border-top: 1px solid #333; }
            QTabBar { background: #252526; }
            QTabBar::tab { background: #2d2d2d; color: #969696; padding: 4px 12px; font-size: 12px; border: none; border-right: 1px solid #252526; }
            QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-top: 2px solid #007acc; }
            QTabBar::tab:hover:!selected { background: #2b2d2e; }
            QToolBar { background: #252526; border: none; border-bottom: 1px solid #333; padding: 4px; spacing: 10px; }
            QToolButton { font-size: 14px; padding: 6px 12px; border-radius: 4px; color: #cccccc; }
            QToolButton:hover { background: #333333; color: #ffffff; }
            QStatusBar { background: #007acc; color: #ffffff; border: none; }
            QStatusBar QLabel { padding: 0 5px; }
            QLineEdit, QComboBox, QSpinBox { background: #3c3c3c; color: #fff; border: 1px solid #555; border-radius: 2px; padding: 2px; }
            QPushButton { background: transparent; color: #cccccc; padding: 4px 10px; border-radius: 3px; border: 1px solid #3c3c3c; }
            QPushButton:hover { background: #3c3c3c; color: #ffffff; }
            QListWidget, QTreeView { background: #1e1e1e; color: #cccccc; border: none; }
            QListWidget::item:selected, QTreeView::item:selected { background: #37373d; }
            QHeaderView::section { background: #252526; color: #cccccc; border: none; border-right: 1px solid #333; border-bottom: 1px solid #333; padding: 4px; }
            QProgressBar { background: #3c3c3c; border: 1px solid #555; text-align: center; }
            QProgressBar::chunk { background: #007acc; }
            QSplitter::handle { background: transparent; }
            QMenu { background: #252526; color: #cccccc; border: 1px solid #454545; }
            QMenu::item:selected { background: #094771; }
            QDialog { background: #252526; }
            
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.1);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.2);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                border: none;
                background: transparent;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255,255,255,0.1);
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(255,255,255,0.2);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)

        # 启动时自动打开一次站点管理器

    def open_site_manager(self):
        """打开或激活站点管理器"""
        # 1. 如果窗口已经存在且可见，说明用户正在操作，直接将其前置激活
        if self.site_manager is not None and self.site_manager.isVisible():
            self.site_manager.activateWindow()
            return

        # 2. 如果窗口实例存在但不可见（被用户点X关闭了），则彻底清理旧实例
        if self.site_manager is not None:
            self.site_manager.deleteLater()
        self.site_manager = None

        self._port_fwd_dialog = None

        # 3. 每次都重新实例化一个全新的站点管理器，确保数据库连接是全新且活跃的
        self.site_manager = SiteManagerWidget()
        self.site_manager.setParent(self)
        self.site_manager.setWindowFlags(Qt.WindowType.Window)
        self.site_manager.session_requested.connect(self.create_new_session)

        self.site_manager.show()
        self.site_manager.activateWindow()

    def create_new_session(self, params: dict):
        """
        接收到连接参数，创建新的 SFTPTabWidget 实例并加入标签页
        """
        host = params.get("host")
        username = params.get("username")
        tab_name = f"{username}@{host}"

        try:
            # 实例化会话 (这会启动新的 core.session 和 event_loop)
            new_sftp_tab = SFTPTabWidget(**params)

            # 将其添加为一个新的 Tab
            index = self.tab_widget.addTab(new_sftp_tab, tab_name)
            self.tab_widget.setCurrentIndex(index)  # 自动跳转到新开的标签页
            
            # 同步当前的主题状态到新标签页
            new_sftp_tab.control_widget.update_theme(self._dark_mode)

            # (可选) 连接成功后自动隐藏站点管理器
            self.site_manager.hide()

        except Exception as e:
            err_type = type(e).__name__
            error_msg = str(e)
            
            if err_type == "PermissionDenied":
                error_msg = "认证失败：请检查用户名、密码或私钥是否正确。\n(服务器拒绝了连接请求)"
            elif err_type in ("TimeoutError", "ConnectionError") or "timeout" in error_msg.lower():
                error_msg = f"网络超时：{error_msg}\n(请检查服务器 IP、端口以及防火墙设置)"
            elif "Connection refused" in error_msg:
                error_msg = "连接被拒绝：目标服务器不存在或未开放对应端口。"
                
            QMessageBox.critical(self, "连接失败", f"无法连接到 {tab_name}:\n\n{error_msg}")

    def closeEvent(self, event):
        """
        拦截主窗口关闭事件。在程序退出前，依次安全关闭所有标签页，
        确保后台的 SSH QThread 被正确终止，避免 "Destroyed while thread is still running" 错误。
        """
        # 只要还有标签页打开，就一直关闭第0个标签页
        while self.tab_widget.count() > 0:
            self.close_tab(0)

        # 如果站点管理器还开着，也一并清理
        if self.site_manager is not None:
            self.site_manager.close()
            self.site_manager.deleteLater()

        # 资源清理完毕，允许主窗口正常关闭
        event.accept()

    # ==========================================================

    def close_tab(self, index: int):
        """
        关闭指定的标签页，并释放底层网络资源
        """
        # 1. 获取该标签页对应的 SFTPTabWidget 实例
        widget = self.tab_widget.widget(index)

        if widget:
            # 2. 手动调用其 close()，触发 sftp_view.py 中你写好的 closeEvent 销毁连接资源
            widget.close()

            # 3. 从 UI 容器中移除并彻底清理内存
            self.tab_widget.removeTab(index)
            widget.deleteLater()


def setup_logging():
    log_dir = get_data_path("logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "quicksftp.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件日志：最多保留5个备份，每个5MB
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 控制台日志
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)


def main():
    try:
        import winuvloop
        winuvloop.install()
    except ImportError:
        pass

    setup_logging()

    app = QApplication(sys.argv)

    # 全局样式：让界面看起来更紧凑专业 (可选)
    app.setStyle("Fusion")

    main_window = MainWindow()
    main_window.show()
    main_window.open_site_manager()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
