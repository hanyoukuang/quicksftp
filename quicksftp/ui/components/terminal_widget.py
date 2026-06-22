"""SSH pseudo-terminal widget using pyqterminal native PySide6 rendering.

Architecture:
    asyncssh stdout → TerminalBridge.run() → output Signal → terminal feed()
    Keyboard → InputHandler.encode() → TerminalBridge.on_input() → asyncssh stdin
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Slot, Signal, Qt, QTimer, QEvent
from PySide6.QtGui import QKeyEvent, QAction
from PySide6.QtWidgets import QMenu

from quicksftp.core.session import SSHSFTPInfo
from pyqterminal import PyqTerminal
from quicksftp.core.settings import SettingsManager

logger = logging.getLogger(__name__)

LOG_DIR = Path.home() / ".config" / "quicksftp" / "logs"


class TerminalBridge(QObject):
    """Async bridge between asyncssh SSHClientProcess and the terminal widget.

    Runs an async loop in the background QThread that reads from SSH stdout
    and emits data via the ``output`` signal. Keyboard input is received
    via the ``on_input`` slot and forwarded to SSH stdin.
    """

    output = Signal(str)

    def __init__(self, info: SSHSFTPInfo):
        super().__init__()
        self.info = info
        self._log_file = None
        self._logging_enabled = False

    def enable_logging(self) -> str:
        site = f"{self.info.username}@{self.info.host}"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = str(LOG_DIR / f"{site}_{ts}.log")
        self._log_file = open(path, "w", encoding="utf-8")
        self._logging_enabled = True
        logger.info(f"Terminal logging started: {path}")
        return path

    def disable_logging(self):
        self._logging_enabled = False
        if self._log_file:
            self._log_file.close()
            self._log_file = None

    def _write_to_log(self, data: str):
        if self._logging_enabled and self._log_file:
            try:
                self._log_file.write(data)
                self._log_file.flush()
            except Exception:
                self._logging_enabled = False

    @Slot(int, int)
    def start(self, cols: int, rows: int):
        """Called by the widget once it has computed accurate dimensions.

        1. Resizes the asyncssh PTY to match the widget dimensions.
        2. Starts the background read loop that pumps SSH stdout → ``output``.
        """
        if self.info.loop.is_running() and getattr(self.info, "process", None):
            self.info.loop.call_soon_threadsafe(
                self.info.process.change_terminal_size, cols, rows
            )
        asyncio.run_coroutine_threadsafe(self.run(), self.info.loop)

    async def run(self):
        while True:
            try:
                data = await self.info.process.stdout.read(8192)
                if data:
                    self.output.emit(data)
                    self._write_to_log(data)
                else:
                    break
            except Exception as e:
                logger.error(f"Terminal read error: {e}")
                break

    def close_log(self):
        self.disable_logging()

    @Slot(str)
    def on_input(self, data: str):
        """Forward keyboard input to the SSH process stdin."""
        if self.info.loop.is_running() and getattr(self.info, "process", None):
            asyncio.run_coroutine_threadsafe(self._write_stdin(data), self.info.loop)

    async def _write_stdin(self, data: str):
        try:
            self.info.process.stdin.write(data)
            await self.info.process.stdin.drain()
        except Exception as e:
            logger.error(f"Terminal write error: {e}")

    @Slot(int, int)
    def resize(self, cols: int, rows: int):
        """Propagate terminal resize to the asyncssh PTY."""
        if self.info.loop.is_running() and getattr(self.info, "process", None):
            self.info.loop.call_soon_threadsafe(
                self.info.process.change_terminal_size, cols, rows
            )


class SSHPtyWidget(PyqTerminal):
    """SSH pseudo-terminal view."""

    def __init__(self, info: SSHSFTPInfo):
        font_family = SettingsManager.get("font_family")
        font_size = SettingsManager.get("font_size", 14)
        super().__init__(rows=24, cols=80, font_family=font_family, font_size=font_size)
        self.info = info

        # ── I/O bridge (asyncssh ↔ terminal widget) ────────────────────
        self.bridge = TerminalBridge(self.info)

        # SSH output → terminal display
        self.bridge.output.connect(self._on_ssh_output)

        # Terminal input → SSH
        self.keyPressed.connect(self._send_input)
        self.resized.connect(self._on_resized)

    # ── SSH I/O ──────────────────────────────────────────────────────────

    def _on_ssh_output(self, data: str):
        """Receive SSH stdout and feed it to the terminal renderer."""
        self.write(data)

    def _send_input(self, data: str):
        """Send raw bytes / text to asyncssh stdin."""
        self.bridge.on_input(data)

    def _start_bridge(self):
        """Start the terminal bridge once the event loop is running.

        Called via a single-shot timer to ensure the widget is fully
        laid out before sending dimensions to asyncssh.
        """
        self.bridge.start(self.cols, self.rows)

    def showEvent(self, event):
        """Trigger bridge startup when the widget becomes visible."""
        super().showEvent(event)
        QTimer.singleShot(0, self._start_bridge)

    def _on_resized(self, rows: int, cols: int):
        """Propagate terminal resize to the asyncssh PTY."""
        if self.info.loop.is_running() and getattr(self.info, "process", None):
            self.info.loop.call_soon_threadsafe(
                self.info.process.change_terminal_size, cols, rows
            )

    # ── Context menu (Chinese + icons) ────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        copy_action = QAction("📋 复制", menu)
        copy_action.setShortcut("Ctrl+Shift+C")
        copy_action.triggered.connect(self.copy_selection)
        copy_action.setEnabled(bool(self.selection_start))
        menu.addAction(copy_action)

        paste_action = QAction("📋 粘贴", menu)
        paste_action.setShortcut("Ctrl+Shift+V")
        paste_action.triggered.connect(self.paste_clipboard)
        menu.addAction(paste_action)

        menu.addSeparator()

        zoom_in = QAction("🔍 放大", menu)
        zoom_in.setShortcut("Ctrl++")
        zoom_in.triggered.connect(
            lambda: self.set_font_size(self.terminal_font.pointSize() + 1)
        )
        menu.addAction(zoom_in)

        zoom_out = QAction("🔎 缩小", menu)
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(
            lambda: self.set_font_size(self.terminal_font.pointSize() - 1)
        )
        menu.addAction(zoom_out)

        zoom_reset = QAction("↩️ 重置缩放", menu)
        zoom_reset.setShortcut("Ctrl+0")
        zoom_reset.triggered.connect(
            lambda: self.set_font_size(SettingsManager.get("font_size", 14))
        )
        menu.addAction(zoom_reset)

        menu.exec(event.globalPos())

    # ── Focus (prevent Tab from triggering Qt focus navigation) ─────────

    def event(self, event: QEvent):
        """Intercept Tab/Backtab before Qt's focus-navigation handler."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key_Tab:
                self.keyPressEvent(event)
                return True
            if key == Qt.Key_Backtab:
                synthetic = QKeyEvent(
                    QEvent.Type.KeyPress,
                    Qt.Key_Tab,
                    event.modifiers() | Qt.ShiftModifier,
                    event.text(),
                    event.isAutoRepeat(),
                    event.count(),
                )
                self.keyPressEvent(synthetic)
                return True
        return super().event(event)

    # ── Keyboard (override for zoom shortcuts) ───────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()

        # ── Zoom shortcuts ─────────────────────────────────────────
        zoom_mod = bool(mods & Qt.ControlModifier)
        if sys.platform != "darwin":
            zoom_mod = zoom_mod and bool(mods & Qt.ShiftModifier)
        if zoom_mod and key in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus):
            delta = 1 if key != Qt.Key_Minus else -1
            self.set_font_size(self.terminal_font.pointSize() + delta)
            return
        if zoom_mod and key == Qt.Key_0:
            self.set_font_size(SettingsManager.get("font_size", 14))
            return

        super().keyPressEvent(event)
