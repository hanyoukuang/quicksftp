import pyte
from PySide6.QtWidgets import QWidget, QApplication, QScrollBar
from PySide6.QtGui import (
    QPainter,
    QFont,
    QFontMetrics,
    QColor,
    QFontDatabase,
    QKeySequence,
)
from PySide6.QtCore import Qt, QRect, Signal


class PyqTerminal(QWidget):
    resized = Signal(int, int)  # rows, cols
    keyPressed = Signal(str)  # For sending input to PTY

    def __init__(self, parent=None, rows=24, cols=80, font_family=None, font_size=14):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.padding = 8
        self.scroll_offset = 0

        self.setFocusPolicy(Qt.WheelFocus)  # Allow widget to receive keyboard events

        # Setup Pyte
        self.screen = pyte.HistoryScreen(self.cols, self.rows, history=10000)
        self.stream = pyte.Stream(self.screen)

        # Setup Font
        if font_family is None:
            self.terminal_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            self.terminal_font.setPointSize(font_size)
        else:
            self.terminal_font = QFont(font_family, font_size)
        self.terminal_font.setStyleHint(QFont.Monospace)
        self.setFont(self.terminal_font)

        self._color_cache = {}
        self._font_cache = {}
        self._update_metrics()

        # Basic 16 colors mapping
        self.color_map = {
            "black": QColor(0, 0, 0),
            "red": QColor(205, 0, 0),
            "green": QColor(0, 205, 0),
            "brown": QColor(205, 205, 0),
            "blue": QColor(0, 0, 238),
            "magenta": QColor(205, 0, 205),
            "cyan": QColor(0, 205, 205),
            "white": QColor(229, 229, 229),
        }
        self.default_bg = QColor(0, 0, 0)
        self.default_fg = QColor(229, 229, 229)

        # Selection state
        self.selection_start = None  # (row, col)
        self.selection_end = None  # (row, col)
        self._last_mouse_grid = None
        self._scroll_accum_y = 0

        self._raw_buffer = ""  # For OSC 52 interception

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)  # Track mouse for TUI motion events

        # Scrollbar
        self.scrollbar = QScrollBar(Qt.Vertical, self)
        self.scrollbar.valueChanged.connect(self._on_scroll_bar)
        self.scrollbar.hide()

    def _update_metrics(self):
        self._font_cache.clear()
        self.metrics = QFontMetrics(self.terminal_font)
        self.char_width = self.metrics.horizontalAdvance("W")
        self.char_height = self.metrics.height()
        self.ascent = self.metrics.ascent()
        self.setMinimumSize(
            self.cols * self.char_width + 2 * self.padding,
            self.rows * self.char_height + 2 * self.padding,
        )

    def write(self, data: str):
        self._raw_buffer += data

        while True:
            idx = self._raw_buffer.find("\x1b]52;")
            if idx == -1:
                safe_len = len(self._raw_buffer)
                for i in range(1, 7):
                    if self._raw_buffer.endswith("\x1b]52;"[:i]):
                        safe_len = len(self._raw_buffer) - i
                        break

                if safe_len > 0:
                    self.stream.feed(self._raw_buffer[:safe_len])
                    self._raw_buffer = self._raw_buffer[safe_len:]
                break
            else:
                if idx > 0:
                    self.stream.feed(self._raw_buffer[:idx])
                    self._raw_buffer = self._raw_buffer[idx:]

                term_idx = self._raw_buffer.find("\x07")
                term_idx2 = self._raw_buffer.find("\x1b\\")

                if term_idx == -1 and term_idx2 == -1:
                    break

                if term_idx != -1 and term_idx2 != -1:
                    end_idx = min(term_idx, term_idx2)
                    term_len = 1 if end_idx == term_idx else 2
                elif term_idx != -1:
                    end_idx = term_idx
                    term_len = 1
                else:
                    end_idx = term_idx2
                    term_len = 2

                payload = self._raw_buffer[6:end_idx]
                parts = payload.split(";", 1)
                if len(parts) == 2:
                    try:
                        import base64

                        b64_data = parts[1]
                        b64_data += "=" * ((4 - len(b64_data) % 4) % 4)
                        decoded_text = base64.b64decode(b64_data).decode("utf-8")
                        QApplication.clipboard().setText(decoded_text)
                    except Exception:
                        pass

                self._raw_buffer = self._raw_buffer[end_idx + term_len :]

        if self.screen.dirty:
            if self.scroll_offset > 0:
                self.scroll_offset = 0
                self._update_scrollbar()
                self.update()
            else:
                for y in self.screen.dirty:
                    rect = QRect(
                        self.padding,
                        y * self.char_height + self.padding,
                        self.width() - 2 * self.padding,
                        self.char_height,
                    )
                    self.update(rect)
            self.screen.dirty.clear()
            self._update_scrollbar()

    def _update_scrollbar(self):
        total = len(self.screen.history.top)
        if total == 0:
            self.scrollbar.hide()
            return
        self.scrollbar.show()
        # Disconnect momentarily to avoid recursive updates
        self.scrollbar.blockSignals(True)
        self.scrollbar.setRange(0, total)
        self.scrollbar.setPageStep(self.rows)
        self.scrollbar.setValue(total - self.scroll_offset)
        self.scrollbar.blockSignals(False)

    def _on_scroll_bar(self, val):
        total = len(self.screen.history.top)
        self.scroll_offset = total - val
        self.update()

    def _scroll_history(self, delta):
        total = len(self.screen.history.top)
        if total == 0:
            return
        self.scroll_offset = max(0, min(total, self.scroll_offset + delta))
        self.scrollbar.blockSignals(True)
        self.scrollbar.setValue(total - self.scroll_offset)
        self.scrollbar.blockSignals(False)
        self.update()

    def clear(self):
        self.screen.reset()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scrollbar.setGeometry(self.width() - 12, 0, 12, self.height())
        self._recalculate_size()

    def _recalculate_size(self):
        new_cols = (self.width() - 2 * self.padding) // self.char_width
        new_rows = (self.height() - 2 * self.padding) // self.char_height

        if new_cols != self.cols or new_rows != self.rows:
            new_cols = max(1, new_cols)
            new_rows = max(1, new_rows)

            self.cols = new_cols
            self.rows = new_rows
            self.screen.resize(self.rows, self.cols)
            self.resized.emit(self.rows, self.cols)

    def set_font_size(self, size: int):
        size = max(6, min(72, size))
        if self.terminal_font.pointSize() == size:
            return
        self.terminal_font.setPointSize(size)
        self.setFont(self.terminal_font)
        self._update_metrics()
        self._recalculate_size()
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.set_font_size(self.terminal_font.pointSize() + 1)
            elif delta < 0:
                self.set_font_size(self.terminal_font.pointSize() - 1)
            event.accept()
            return

        # If TUI wants mouse events, report wheel as buttons 4/5
        modes = self.screen.mode
        track_press = (
            (1000 << 5) in modes or (1002 << 5) in modes or (1003 << 5) in modes
        )
        sgr_mode = (1006 << 5) in modes

        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return

        if not track_press:
            self._scroll_accum_y += delta
            step = 30
            while self._scroll_accum_y >= step:
                self._scroll_accum_y -= step
                self._scroll_history(1)
            while self._scroll_accum_y <= -step:
                self._scroll_accum_y += step
                self._scroll_history(-1)
            event.accept()
            return

        self._scroll_accum_y += delta
        # Accumulate delta for smooth trackpad scrolling (standard wheel click is ~120)
        step = 60

        row, col = self._mouse_to_grid(event.position())
        cx, cy = col + 1, row + 1

        while self._scroll_accum_y >= step:
            self._scroll_accum_y -= step
            cb = 64  # UP
            if sgr_mode:
                self.keyPressed.emit(f"\x1b[<{cb};{cx};{cy}M")
            else:
                self.keyPressed.emit(
                    f"\x1b[M{chr(32 + cb)}{chr(32 + cx)}{chr(32 + cy)}"
                )

        while self._scroll_accum_y <= -step:
            self._scroll_accum_y += step
            cb = 65  # DOWN
            if sgr_mode:
                self.keyPressed.emit(f"\x1b[<{cb};{cx};{cy}M")
            else:
                self.keyPressed.emit(
                    f"\x1b[M{chr(32 + cb)}{chr(32 + cx)}{chr(32 + cy)}"
                )

        event.accept()
        return

    # --- Mouse and Selection ---
    def _mouse_to_grid(self, pos):
        col = int((pos.x() - self.padding) // self.char_width)
        row = int((pos.y() - self.padding) // self.char_height)
        return max(0, min(self.rows - 1, row)), max(0, min(self.cols - 1, col))

    def _send_mouse_event(self, event, is_press=False, is_release=False, is_move=False):
        modes = self.screen.mode
        # In pyte, DEC private modes are shifted left by 5 bits
        track_press = (
            (1000 << 5) in modes or (1002 << 5) in modes or (1003 << 5) in modes
        )
        track_drag = (1002 << 5) in modes or (1003 << 5) in modes
        track_move = (1003 << 5) in modes
        sgr_mode = (1006 << 5) in modes

        # Override tracking if Shift is held (allows local selection even in TUI)
        if event.modifiers() & Qt.ShiftModifier:
            return False

        if not track_press:
            return False

        if is_move and not event.buttons() and not track_move:
            return True
        if is_move and event.buttons() and not track_drag:
            return True

        row, col = self._mouse_to_grid(event.position())
        cx, cy = col + 1, row + 1

        # Default to 'no button'
        cb = 3

        if is_press or is_release:
            if event.button() == Qt.LeftButton:
                cb = 0
            elif event.button() == Qt.MiddleButton:
                cb = 1
            elif event.button() == Qt.RightButton:
                cb = 2
        else:  # is_move
            if event.buttons() & Qt.LeftButton:
                cb = 0
            elif event.buttons() & Qt.MiddleButton:
                cb = 1
            elif event.buttons() & Qt.RightButton:
                cb = 2

        if is_release and not sgr_mode:
            cb = 3  # X11 format uses 3 for all releases

        if is_move:
            cb += 32  # Motion modifier

        if event.modifiers() & Qt.AltModifier:
            cb += 8
        if event.modifiers() & Qt.ControlModifier:
            cb += 16

        if sgr_mode:
            suffix = "M" if (is_press or is_move) else "m"
            self.keyPressed.emit(f"\x1b[<{cb};{cx};{cy}{suffix}")
        else:
            cx, cy = min(223, cx), min(223, cy)
            self.keyPressed.emit(f"\x1b[M{chr(32 + cb)}{chr(32 + cx)}{chr(32 + cy)}")

        return True

    def mousePressEvent(self, event):
        self._last_mouse_grid = self._mouse_to_grid(event.position())
        if self._send_mouse_event(event, is_press=True):
            return

        if event.button() == Qt.LeftButton:
            self.selection_start = self._mouse_to_grid(event.position())
            self.selection_end = self.selection_start
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._last_mouse_grid = self._mouse_to_grid(event.position())
        if self._send_mouse_event(event, is_release=True):
            return

        # Copy automatically on select release
        if (
            self.selection_start
            and self.selection_end
            and self.selection_start != self.selection_end
        ):
            self.copy_selection(clear=False)

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        grid_pos = self._mouse_to_grid(event.position())
        if getattr(self, "_last_mouse_grid", None) == grid_pos:
            return
        self._last_mouse_grid = grid_pos

        if self._send_mouse_event(event, is_move=True):
            return

        if event.buttons() & Qt.LeftButton:
            self.selection_end = grid_pos
            self.update()
        super().mouseMoveEvent(event)

    def _get_selection_range(self):
        if not self.selection_start or not self.selection_end:
            return None
        r1, c1 = self.selection_start
        r2, c2 = self.selection_end
        if (r1, c1) > (r2, c2):
            r1, c1, r2, c2 = r2, c2, r1, c1
        return (r1, c1), (r2, c2)

    def _is_selected(self, row, col, sel_range):
        if not sel_range:
            return False
        (r1, c1), (r2, c2) = sel_range
        if r1 < row < r2:
            return True
        if row == r1 == r2:
            return c1 <= col <= c2
        if row == r1:
            return col >= c1
        if row == r2:
            return col <= c2
        return False

    def copy_selection(self, clear=True):
        sel_range = self._get_selection_range()
        if not sel_range:
            return
        (r1, c1), (r2, c2) = sel_range
        lines = []
        N = len(self.screen.history.top)

        for r in range(r1, r2 + 1):
            L = N - self.scroll_offset + r
            if L < 0:
                continue  # Out of bounds
            if L < N:
                line = self.screen.history.top[L]
            elif L - N < self.rows:
                line = self.screen.buffer[L - N]
            else:
                continue  # Out of bounds

            start_c = c1 if r == r1 else 0
            end_c = c2 if r == r2 else self.cols - 1

            text = ""
            for c in range(start_c, end_c + 1):
                if line[c].data != "":  # Ignore double cell empty placeholders
                    text += line[c].data
            lines.append(text.rstrip())

        QApplication.clipboard().setText("\n".join(lines))

        if clear:
            self.selection_start = None
            self.selection_end = None
            self.update()

    def paste_clipboard(self):
        text = QApplication.clipboard().text()
        if text:
            # Send pasted text to the PTY
            self.keyPressed.emit(text)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
            return
        if event.matches(QKeySequence.Paste):
            self.paste_clipboard()
            return

        key = event.key()
        text = event.text()

        # Basic key mapping for PTY interaction
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            self.keyPressed.emit("\r")
        elif key == Qt.Key_Backspace:
            self.keyPressed.emit("\x7f")  # standard for bash/zsh
        elif key == Qt.Key_Up:
            self.keyPressed.emit("\x1b[A")
        elif key == Qt.Key_Down:
            self.keyPressed.emit("\x1b[B")
        elif key == Qt.Key_Right:
            self.keyPressed.emit("\x1b[C")
        elif key == Qt.Key_Left:
            self.keyPressed.emit("\x1b[D")
        elif key == Qt.Key_Tab:
            self.keyPressed.emit("\t")
        elif key == Qt.Key_Escape:
            self.keyPressed.emit("\x1b")
        elif text:
            self.keyPressed.emit(text)
        else:
            super().keyPressEvent(event)

    # --- Colors & Rendering ---
    def _get_color(self, pyte_color, is_bg=False):
        key = (pyte_color, is_bg)
        if key in self._color_cache:
            return self._color_cache[key]

        if pyte_color == "default":
            res = self.default_bg if is_bg else self.default_fg
        elif pyte_color in self.color_map:
            res = self.color_map[pyte_color]
        elif len(pyte_color) == 6:
            try:
                res = QColor(f"#{pyte_color}")
            except Exception:
                res = self.default_bg if is_bg else self.default_fg
        else:
            res = self.default_bg if is_bg else self.default_fg

        self._color_cache[key] = res
        return res

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.terminal_font)

        clip_rect = event.rect()
        painter.fillRect(clip_rect, self.default_bg)
        sel_range = self._get_selection_range()

        # Calculate dirty rows based on clipping rect
        min_y = max(0, (clip_rect.top() - self.padding) // self.char_height)
        max_y = min(
            self.rows - 1,
            (clip_rect.bottom() - self.padding + self.char_height - 1)
            // self.char_height,
        )

        N = len(self.screen.history.top)

        # Pass 1: Draw all backgrounds (Batched!)
        for y in range(min_y, max_y + 1):
            L = N - self.scroll_offset + y
            if L < N:
                line = self.screen.history.top[L]
            else:
                line = self.screen.buffer[L - N]

            start_x = 0
            current_bg = None

            for x in range(self.cols):
                char = line[x]
                bg_color = self._get_color(char.bg, is_bg=True)
                if char.reverse:
                    bg_color = self._get_color(char.fg, is_bg=False)
                if self._is_selected(y, x, sel_range):
                    fg_temp = self._get_color(char.fg, is_bg=False)
                    if char.reverse:
                        fg_temp = self._get_color(char.bg, is_bg=True)
                    bg_color = fg_temp

                if bg_color != current_bg:
                    if current_bg is not None and current_bg != self.default_bg:
                        painter.fillRect(
                            QRect(
                                self.padding + start_x * self.char_width,
                                self.padding + y * self.char_height,
                                (x - start_x) * self.char_width,
                                self.char_height,
                            ),
                            current_bg,
                        )
                    start_x = x
                    current_bg = bg_color

            if current_bg is not None and current_bg != self.default_bg:
                painter.fillRect(
                    QRect(
                        self.padding + start_x * self.char_width,
                        self.padding + y * self.char_height,
                        (self.cols - start_x) * self.char_width,
                        self.char_height,
                    ),
                    current_bg,
                )

        # Pass 2: Draw all foreground text
        last_pen_color = None
        last_font_key = None

        for y in range(min_y, max_y + 1):
            L = N - self.scroll_offset + y
            if L < N:
                line = self.screen.history.top[L]
            else:
                line = self.screen.buffer[L - N]

            for x in range(self.cols):
                char = line[x]

                if char.data != " " and char.data != "":
                    rect = QRect(
                        self.padding + x * self.char_width,
                        self.padding + y * self.char_height,
                        self.char_width,
                        self.char_height,
                    )

                    fg_color = self._get_color(char.fg, is_bg=False)
                    if char.reverse:
                        fg_color = self._get_color(char.bg, is_bg=True)
                    if self._is_selected(y, x, sel_range):
                        bg_temp = self._get_color(char.bg, is_bg=True)
                        if char.reverse:
                            bg_temp = self._get_color(char.fg, is_bg=False)
                        fg_color = bg_temp

                    # Custom rendering for block elements
                    if char.data == "\u2588":
                        painter.fillRect(rect, fg_color)
                        continue
                    elif char.data == "\u2580":
                        painter.fillRect(
                            QRect(
                                rect.left(),
                                rect.top(),
                                rect.width(),
                                (rect.height() + 1) // 2,
                            ),
                            fg_color,
                        )
                        continue
                    elif char.data == "\u2584":
                        hh = (rect.height() + 1) // 2
                        painter.fillRect(
                            QRect(
                                rect.left(),
                                rect.top() + hh,
                                rect.width(),
                                rect.height() - hh,
                            ),
                            fg_color,
                        )
                        continue
                    elif char.data == "\u258c":
                        painter.fillRect(
                            QRect(
                                rect.left(),
                                rect.top(),
                                (rect.width() + 1) // 2,
                                rect.height(),
                            ),
                            fg_color,
                        )
                        continue
                    elif char.data == "\u2590":
                        hw = (rect.width() + 1) // 2
                        painter.fillRect(
                            QRect(
                                rect.left() + hw,
                                rect.top(),
                                rect.width() - hw,
                                rect.height(),
                            ),
                            fg_color,
                        )
                        continue

                    # Dynamic Font Styling (Cached)
                    font_key = (
                        char.bold,
                        char.italics,
                        char.underscore,
                        char.strikethrough,
                    )
                    if font_key != last_font_key:
                        if font_key == (False, False, False, False):
                            painter.setFont(self.terminal_font)
                        else:
                            if font_key not in self._font_cache:
                                f = QFont(self.terminal_font)
                                f.setBold(char.bold)
                                f.setItalic(char.italics)
                                f.setUnderline(char.underscore)
                                f.setStrikeOut(char.strikethrough)
                                self._font_cache[font_key] = f
                            painter.setFont(self._font_cache[font_key])
                        last_font_key = font_key

                    # Pen State
                    if fg_color != last_pen_color:
                        painter.setPen(fg_color)
                        last_pen_color = fg_color

                    is_wide = x + 1 < self.cols and line[x + 1].data == ""
                    if is_wide:
                        char_real_width = self.metrics.horizontalAdvance(char.data)
                        x_offset = (
                            rect.left() + (self.char_width * 2 - char_real_width) / 2
                        )
                        painter.drawText(x_offset, rect.top() + self.ascent, char.data)
                    else:
                        painter.drawText(
                            rect.left(), rect.top() + self.ascent, char.data
                        )

        cursor = self.screen.cursor
        if (
            self.scroll_offset == 0
            and not cursor.hidden
            and min_y <= cursor.y <= max_y
            and 0 <= cursor.x < self.cols
        ):
            cursor_rect = QRect(
                self.padding + cursor.x * self.char_width,
                self.padding + cursor.y * self.char_height,
                self.char_width,
                self.char_height,
            )
            painter.fillRect(cursor_rect, QColor(255, 255, 255, 128))
