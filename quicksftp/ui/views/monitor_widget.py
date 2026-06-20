import asyncio
import logging
from PySide6.QtCore import QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QFrame
)

logger = logging.getLogger(__name__)

class MonitorSignals(QObject):
    data_updated = Signal(dict)

class SystemMonitorWidget(QFrame):
    """服务器实时资源监控面板 (类似 FinalShell)"""
    def __init__(self, info):
        super().__init__()
        self.info = info
        self.signals = MonitorSignals()
        self.signals.data_updated.connect(self.update_ui)
        
        self.setObjectName("SystemMonitor")
        self.setFixedHeight(30)
        
        # UI Setup
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        
        # CPU
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFormat("CPU: %p%")
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFixedHeight(14)
        self.cpu_bar.setFixedWidth(120)
        
        # Memory
        self.mem_bar = QProgressBar()
        self.mem_bar.setFormat("RAM: %p%")
        self.mem_bar.setRange(0, 100)
        self.mem_bar.setFixedHeight(14)
        self.mem_bar.setFixedWidth(120)
        
        # Disk
        self.disk_bar = QProgressBar()
        self.disk_bar.setFormat("Disk: %p%")
        self.disk_bar.setRange(0, 100)
        self.disk_bar.setFixedHeight(14)
        self.disk_bar.setFixedWidth(120)
        
        # Network
        self.net_label = QLabel("⬆️ 0 B/s  ⬇️ 0 B/s")
        self.net_label.setFixedWidth(200)
        
        layout.addWidget(self.cpu_bar)
        layout.addWidget(self.mem_bar)
        layout.addWidget(self.disk_bar)
        layout.addWidget(self.net_label)
        layout.addStretch()
        
        # Polling
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_data)
        
        self._is_running = False
        self._last_rx = 0
        self._last_tx = 0
        self._last_time = 0

    def set_enabled(self, enabled: bool):
        self.setVisible(enabled)
        if enabled:
            if not self._is_running:
                self._is_running = True
                self._timer.start(2000)
                self._poll_data()
        else:
            self._is_running = False
            self._timer.stop()

    def _poll_data(self):
        if not self.info.connect_is_ready or not hasattr(self.info, 'loop'):
            return
        
        # 使用 linux 命令快速抓取信息
        cmd = """
        UNAME=$(uname)
        if [ "$UNAME" = "Darwin" ]; then
            echo "===CPU==="
            echo "Mac"
            ps -A -o %cpu | awk '{s+=$1} END {print s}'
            sysctl -n hw.ncpu
            echo "===MEM==="
            echo "Mac"
            sysctl -n hw.memsize
            PAGE_SIZE=$(vm_stat | grep "page size of" | grep -o "[0-9]*")
            if [ -z "$PAGE_SIZE" ]; then PAGE_SIZE=4096; fi
            vm_stat | tr -d '.' | awk -v ps=$PAGE_SIZE '
            /Pages active:/ {a=$3}
            /Pages wired down:/ {w=$4}
            /Pages occupied by compressor:/ {c=$5}
            END {print (a+w+c)*ps}'
            echo "===DISK==="
            df -m / | tail -1
            echo "===NET==="
            echo "Mac"
            netstat -ib | awk '/en0/ && !/Link/ {print $7, $10}' | head -1
        else
            echo "===CPU==="
            cat /proc/stat | grep '^cpu '
            echo "===MEM==="
            cat /proc/meminfo | grep -E '^MemTotal|^MemAvailable'
            echo "===DISK==="
            df -m / | tail -1
            echo "===NET==="
            cat /proc/net/dev | grep -v 'lo:' | awk '{rx+=$2; tx+=$10} END {print rx, tx}'
        fi
        """
        asyncio.run_coroutine_threadsafe(self._async_fetch(cmd), self.info.loop)

    async def _async_fetch(self, cmd):
        try:
            if not getattr(self.info, "connection", None):
                return
            result = await self.info.connection.run(cmd, timeout=3)
            out = result.stdout
            if not out:
                return
            
            data = {}
            parts = out.split("===")
            for i in range(len(parts)):
                part = parts[i]
                if part == "CPU" and i+1 < len(parts):
                    content = parts[i+1]
                    lines = content.strip().split('\n')
                    if lines and lines[0] == "Mac":
                        if len(lines) >= 3:
                            used = float(lines[1])
                            total = int(lines[2]) * 100
                            if total > 0:
                                data['cpu_pct'] = min((used / total) * 100, 100)
                    else:
                        lines = content.strip().split()
                        if len(lines) >= 8:
                            user, nice, system, idle = map(int, lines[1:5])
                            total = sum(map(int, lines[1:8]))
                            data['cpu_raw'] = (total - idle, total)
                elif part == "MEM" and i+1 < len(parts):
                    content = parts[i+1]
                    lines = content.strip().split('\n')
                    if lines and lines[0] == "Mac":
                        if len(lines) >= 3:
                            mem_total = int(lines[1])
                            mem_used = int(lines[2])
                            if mem_total > 0:
                                data['mem'] = (mem_used / mem_total) * 100
                    else:
                        mem_total = mem_avail = 0
                        for line in lines:
                            if 'MemTotal' in line:
                                mem_total = int(line.split()[1])
                            elif 'MemAvailable' in line:
                                mem_avail = int(line.split()[1])
                        if mem_total > 0:
                            data['mem'] = (mem_total - mem_avail) / mem_total * 100
                elif part == "DISK" and i+1 < len(parts):
                    content = parts[i+1]
                    lines = content.strip().split()
                    if len(lines) >= 5:
                        for item in lines:
                            if '%' in item:
                                data['disk'] = int(item.replace('%', ''))
                                break
                elif part == "NET" and i+1 < len(parts):
                    content = parts[i+1]
                    lines = content.strip().split('\n')
                    if lines and lines[0] == "Mac":
                        if len(lines) >= 2:
                            vals = lines[1].strip().split()
                            if len(vals) >= 2:
                                data['net'] = (int(vals[0]), int(vals[1]))
                    else:
                        vals = content.strip().split()
                        if len(vals) == 2:
                            data['net'] = (int(vals[0]), int(vals[1]))
            
            self.signals.data_updated.emit(data)
        except Exception as e:
            logger.debug(f"Monitor fetch error: {e}")

    def update_ui(self, data):
        if 'cpu_pct' in data:
            self.cpu_bar.setValue(int(data['cpu_pct']))
        elif 'cpu_raw' in data:
            used, total = data['cpu_raw']
            if hasattr(self, '_last_cpu'):
                last_used, last_total = self._last_cpu
                d_used = used - last_used
                d_total = total - last_total
                if d_total > 0:
                    pct = (d_used / d_total) * 100
                    self.cpu_bar.setValue(int(pct))
            self._last_cpu = (used, total)
            
        if 'mem' in data:
            self.mem_bar.setValue(int(data['mem']))
            
        if 'disk' in data:
            self.disk_bar.setValue(data['disk'])
            
        if 'net' in data:
            import time
            rx, tx = data['net']
            now = time.time()
            if self._last_time > 0:
                dt = now - self._last_time
                if dt > 0:
                    rx_speed = (rx - self._last_rx) / dt
                    tx_speed = (tx - self._last_tx) / dt
                    self.net_label.setText(f"⬆️ {self._format_speed(tx_speed)}  ⬇️ {self._format_speed(rx_speed)}")
            self._last_rx = rx
            self._last_tx = tx
            self._last_time = now

    def _format_speed(self, bps):
        if bps < 1024:
            return f"{bps:.1f} B/s"
        elif bps < 1024 * 1024:
            return f"{bps/1024:.1f} KB/s"
        else:
            return f"{bps/(1024*1024):.1f} MB/s"
