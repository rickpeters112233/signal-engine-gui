import sys
import os
import subprocess
import re
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QProgressBar, QSystemTrayIcon, QMenu, QStyleFactory
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont
from dotenv import load_dotenv
import win32gui, win32con  # pip install pywin32 for tray balloons

# Setup project path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
load_dotenv()

# Auto front-month gold (as before)
from datetime import datetime
GOLD_ACTIVE_MONTHS = {2: 'G', 4: 'J', 6: 'M', 8: 'Q', 10: 'V', 12: 'Z'}

def get_current_gold_front_month_id():
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    year_digit = str(current_year)[-1]
    next_month = next((m for m in sorted(GOLD_ACTIVE_MONTHS) if m >= current_month), min(GOLD_ACTIVE_MONTHS))
    if next_month == min(GOLD_ACTIVE_MONTHS) and next_month < current_month:
        year_digit = str(current_year + 1)[-1]
    month_code = GOLD_ACTIVE_MONTHS[next_month]
    return f"CON.F.US.GCE.{month_code}{year_digit}"

class EngineThread(QThread):
    log = pyqtSignal(str)
    data = pyqtSignal(dict)
    status = pyqtSignal(str)

    def __init__(self, contract_id):
        super().__init__()
        self.contract_id = contract_id
        self.proc = None
        self.running = False

    def run(self):
        self.running = True
        cmd = [
            sys.executable, "main.py",
            "--contract_id", self.contract_id,
            "--mode", "realtime",
            "--provider", "topstepx",
            "--no-browser"
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        for line in iter(self.proc.stdout.readline, ''):
            if not self.running:
                break
            clean = line.strip()
            self.log.emit(clean)

            parsed = {}
            if "Contract:" in clean:
                parsed['contract'] = clean.split("Contract:")[1].strip()
            if "Timestamp:" in clean:
                parsed['timestamp'] = clean.split("Timestamp:")[1].strip()
            if "Price:" in clean or "close=" in clean:
                price_match = re.search(r'[\d,]+\.?\d*', clean)
                parsed['price'] = price_match.group() if price_match else 'N/A'
            if "Volume:" in clean:
                parsed['volume'] = clean.split("Volume:")[1].strip()
            # Indicators (expand as your log format evolves)
            if "phi_sigma=" in clean:
                parsed['phi_sigma'] = float(re.search(r'phi_sigma=([\d\.]+)', clean).group(1))
            if "directional=" in clean:
                parsed['directional'] = float(re.search(r'directional=([\d\.]+)', clean).group(1))
            if "Signal:" in clean:
                parsed['signal'] = clean.split("Signal:")[1].strip()
            if 'cvd_status' in clean or 'CVD' in clean:
                # Add similar parsing
                pass
            if parsed:
                self.data.emit(parsed)

        self.status.emit("Stopped")

    def stop(self):
        self.running = False
        if self.proc:
            self.proc.terminate()

class GestaltDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GESTALT - Tactical Market Intelligence")
        self.setGeometry(200, 100, 1200, 800)

        # Dark theme
        app.setStyle(QStyleFactory.create("Fusion"))
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(20, 20, 30))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 45))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 55))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        app.setPalette(palette)

        # Tray icon (fix warning)
        self.tray = QSystemTrayIcon(self)
        # Use built-in Qt icon or provide your own .ico/.png
        icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)  # fallback
        self.tray.setIcon(icon)
        tray_menu = QMenu()
        tray_menu.addAction("Restore", self.showNormal)
        tray_menu.addAction("Quit", app.quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

        # Main layout
        central = QWidget()
        main_layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # Header (primary metrics)
        header = QHBoxLayout()
        self.contract_lbl = QLabel("CONTRACT: Loading...")
        self.timestamp_lbl = QLabel("TIMESTAMP: N/A")
        self.price_lbl = QLabel("Price: N/A")
        self.volume_lbl = QLabel("Volume: N/A")
        for lbl in [self.contract_lbl, self.timestamp_lbl, self.price_lbl, self.volume_lbl]:
            lbl.setStyleSheet("font-weight: bold; color: #00ffff;")
            header.addWidget(lbl)
        main_layout.addLayout(header)

        # Main panels (row 1)
        row1 = QHBoxLayout()
        main_layout.addLayout(row1)

        # Signal based on current holdings
        signal_grp = QGroupBox("Indicator based on current holdings")
        signal_lay = QVBoxLayout()
        self.signal_big = QLabel("HOLD")
        self.signal_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signal_big.setStyleSheet("font-size: 28px; font-weight: bold; color: yellow;")
        signal_lay.addWidget(self.signal_big)
        self.signal_history = QLabel("Signal History: 44")
        signal_lay.addWidget(self.signal_history)
        signal_grp.setLayout(signal_lay)
        row1.addWidget(signal_grp)

        # Predicted Market Direction
        direction_grp = QGroupBox("Predicted Market Direction Indicator")
        direction_lay = QVBoxLayout()
        self.direction_arrow = QLabel("→")
        self.direction_arrow.setFont(QFont("Arial", 40))
        self.direction_arrow.setStyleSheet("color: red;")
        direction_lay.addWidget(self.direction_arrow, alignment=Qt.AlignmentFlag.AlignCenter)
        self.direction_val = QLabel("-0.03")
        direction_lay.addWidget(self.direction_val, alignment=Qt.AlignmentFlag.AlignCenter)
        direction_grp.setLayout(direction_lay)
        row1.addWidget(direction_grp)

        # Minor Event
        minor_grp = QGroupBox("Minor Event Consider")
        minor_lay = QVBoxLayout()
        self.minor_circle = QLabel("●")
        self.minor_circle.setFont(QFont("Arial", 40))
        self.minor_circle.setStyleSheet("color: green;")
        minor_lay.addWidget(self.minor_circle, alignment=Qt.AlignmentFlag.AlignCenter)
        self.minor_text = QLabel("Purchase/Sale")
        minor_lay.addWidget(self.minor_text, alignment=Qt.AlignmentFlag.AlignCenter)
        minor_grp.setLayout(minor_lay)
        row1.addWidget(minor_grp)

        # Stability Thresholds
        stability_grp = QGroupBox("Stability Score Thresholds")
        stability_lay = QVBoxLayout()
        thresholds = [
            "85-100 Highly stable (GREEN)",
            "70-84 Stable (GREEN)",
            "50-69 Transitional (YELLOW)",
            "30-49 Unstable (YELLOW)",
            "0-29 Collapse (RED)"
        ]
        for t in thresholds:
            lbl = QLabel(t)
            color = 'green' if 'GREEN' in t else 'yellow' if 'YELLOW' in t else 'red'
            lbl.setStyleSheet(f"color: {color};")
            stability_lay.addWidget(lbl)
        stability_grp.setLayout(stability_lay)
        main_layout.addWidget(stability_grp)

        # Bottom row
        bottom = QHBoxLayout()
        main_layout.addLayout(bottom)

        # Current Stability Score
        score_grp = QGroupBox("Current Stability Score")
        score_lay = QVBoxLayout()
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(78)
        self.score_bar.setStyleSheet("QProgressBar::chunk { background-color: yellow; }")
        score_lay.addWidget(self.score_bar)
        self.trend_lbl = QLabel("Stability Trend: N/A")
        score_lay.addWidget(self.trend_lbl)
        score_grp.setLayout(score_lay)
        bottom.addWidget(score_grp)

        # Major Event Warning
        warning_grp = QGroupBox("MAJOR EVENT WARNING 10 MIN")
        warning_lay = QVBoxLayout()
        self.warning_circle = QLabel("●")
        self.warning_circle.setFont(QFont("Arial", 40))
        self.warning_circle.setStyleSheet("color: magenta;")
        warning_lay.addWidget(self.warning_circle, alignment=Qt.AlignmentFlag.AlignCenter)
        warning_grp.setLayout(warning_lay)
        bottom.addWidget(warning_grp)

        # Major Event Occurred
        occurred_grp = QGroupBox("MAJOR EVENT OCCURRED")
        occurred_lay = QVBoxLayout()
        self.occurred_lbl = QLabel("BOUGHT/SOLD SHARES AMOUNT: N/A")
        occurred_lay.addWidget(self.occurred_lbl)
        enter_btn = QPushButton("ENTER")
        enter_btn.setStyleSheet("background-color: yellow; color: black; font-weight: bold;")
        occurred_lay.addWidget(enter_btn)
        occurred_grp.setLayout(occurred_lay)
        bottom.addWidget(occurred_grp)

        # Controls
        ctrl_lay = QHBoxLayout()
        start_btn = QPushButton("START STREAM")
        start_btn.clicked.connect(self.start_engine)
        ctrl_lay.addWidget(start_btn)
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.clicked.connect(self.stop_engine)
        self.stop_btn.setEnabled(False)
        ctrl_lay.addWidget(self.stop_btn)
        main_layout.addLayout(ctrl_lay)

        self.status = QLabel("Status: Stopped")
        main_layout.addWidget(self.status)

        # Engine & auto contract
        self.engine = None
        self.contract_id = get_current_gold_front_month_id()

    def start_engine(self):
        self.status.setText("Launching stream...")
        self.stop_btn.setEnabled(True)
        self.engine = EngineThread(self.contract_id)
        self.engine.log.connect(self.update_from_log)
        self.engine.data.connect(self.update_indicators)
        self.engine.status.connect(self.status.setText)
        self.engine.start()

    def stop_engine(self):
        if self.engine:
            self.engine.stop()
        self.status.setText("Stopped")
        self.stop_btn.setEnabled(False)

    def update_from_log(self, line):
        if "Contract:" in line:
            self.contract_lbl.setText(line)
        if "Timestamp:" in line:
            self.timestamp_lbl.setText(line)
        if "Price:" in line or "close=" in line:
            price_match = re.search(r'[\d,.]+', line)
            if price_match:
                self.price_lbl.setText(f"Price: {price_match.group()}")
        if "Volume:" in line:
            self.volume_lbl.setText(line)

        # Major warning trigger example
        if "Major Event Warning" in line:
            self.warning_circle.setStyleSheet("color: red;")
            self.tray.showMessage("GESTALT ALERT", "Major Event Warning 10 MIN", QSystemTrayIcon.MessageIcon.Warning)

    def update_indicators(self, data):
        # Signal
        if 'signal' in data:
            sig = data['signal']
            color = 'green' if sig == 'BUY' else 'red' if sig == 'SELL' else 'yellow'
            self.signal_big.setText(sig)
            self.signal_big.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color};")

        # Direction
        if 'directional' in data:
            val = data['directional']
            color = 'green' if val > 0 else 'red' if val < 0 else 'yellow'
            arrow = '↑' if val > 0 else '↓' if val < 0 else '→'
            self.direction_arrow.setText(arrow)
            self.direction_arrow.setStyleSheet(f"color: {color}; font-size: 40px;")
            self.direction_val.setText(f"{val:.2f}")

        # Stability score (placeholder mapping - adjust to your real score)
        score = 78  # Replace with parsed value when available
        self.score_bar.setValue(score)
        chunk_color = 'green' if score >= 70 else 'yellow' if score >= 30 else 'red'
        self.score_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {chunk_color}; }}")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("GESTALT", "Minimized to system tray", QSystemTrayIcon.MessageIcon.Information)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GestaltDashboard()
    window.show()
    sys.exit(app.exec())
