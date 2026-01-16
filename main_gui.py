import sys
import os
import subprocess
import re
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QProgressBar, QSystemTrayIcon, QMenu, QStyleFactory
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont
from dotenv import load_dotenv
import win32gui, win32con  # from pywin32 - for tray notifications

# Project path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
load_dotenv()

# Auto front-month function (from earlier)
from datetime import datetime

GOLD_ACTIVE_MONTHS = {
    2: 'G', 4: 'J', 6: 'M', 8: 'Q', 10: 'V', 12: 'Z'
}

def get_current_gold_front_month_id():
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    year_digit = str(current_year)[-1]

    next_month = None
    for m in sorted(GOLD_ACTIVE_MONTHS.keys()):
        if m >= current_month:
            next_month = m
            break

    if next_month is None:
        next_month = min(GOLD_ACTIVE_MONTHS.keys())
        year_digit = str(current_year + 1)[-1]

    month_code = GOLD_ACTIVE_MONTHS[next_month]
    contract_id = f"CON.F.US.GCE.{month_code}{year_digit}"
    return contract_id

class EngineThread(QThread):
    log_signal = pyqtSignal(str)
    data_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)

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
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        for line in iter(self.proc.stdout.readline, ''):
            if not self.running:
                break
            clean_line = line.strip()
            self.log_signal.emit(clean_line)

            # Parse key values from engine output
            data = {}
            if "phi_sigma=" in clean_line:
                data['phi_sigma'] = float(re.search(r'phi_sigma=([\d\.]+)', clean_line).group(1))
            if "directional=" in clean_line:
                data['directional'] = float(re.search(r'directional=([\d\.]+)', clean_line).group(1))
            if "CVD" in clean_line:
                data['cvd_status'] = re.search(r'Status: (\w+)', clean_line).group(1) if re.search(r'Status: (\w+)', clean_line) else ''
                data['cvd_momentum'] = re.search(r'Momentum: (\w+)', clean_line).group(1) if re.search(r'Momentum: (\w+)', clean_line) else ''
            if "TF_mod" in clean_line:
                data['tf_mod'] = clean_line  # Full line or extract value
            if "TF_crit" in clean_line:
                data['tf_crit'] = clean_line  # Text only, no color
            if "TVI" in clean_line:
                data['tvi'] = clean_line  # Extract if needed
            if "Signal: " in clean_line:
                data['signal'] = clean_line.split("Signal: ")[1]
            if data:
                self.data_signal.emit(data)

        self.status_signal.emit("Stopped")
        self.proc.wait()

    def stop(self):
        self.running = False
        if self.proc:
            self.proc.terminate()
            self.proc.wait()

class GestaltGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestalt Signal Engine - Futures Trader Dashboard")
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowIcon(QIcon())  # Add icon if you have one

        # Dark theme (Fusion style + palette)
        app.setStyle(QStyleFactory.create("Fusion"))
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        app.setPalette(palette)

        # Tray icon for minimize
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon())  # Set icon
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Restore")
        restore_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(app.quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_clicked)
        self.tray_icon.setVisible(True)

        # Central widget + layout
        central = QWidget()
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Top header bar (contract, timestamp, price, volume)
        header_layout = QHBoxLayout()
        self.contract_label = QLabel("Contract: Loading...")
        self.contract_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.contract_label)

        self.timestamp_label = QLabel("Timestamp: N/A")
        header_layout.addWidget(self.timestamp_label)

        self.price_label = QLabel("Price: N/A")
        self.price_label.setStyleSheet("color: cyan;")
        header_layout.addWidget(self.price_label)

        self.volume_label = QLabel("Volume: N/A")
        header_layout.addWidget(self.volume_label)

        main_layout.addLayout(header_layout)

        # Main panels row 1
        panels_row1 = QHBoxLayout()
        main_layout.addLayout(panels_row1)

        # Signal panel
        signal_group = QGroupBox("Indicator Based on Current Holdings")
        signal_layout = QVBoxLayout()
        self.signal_label = QLabel("HOLD")
        self.signal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signal_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.signal_label.setStyleSheet("color: yellow;")  # Default HOLD
        signal_layout.addWidget(self.signal_label)
        self.signal_history = QLabel("Signal History: N/A")
        signal_layout.addWidget(self.signal_history)
        signal_group.setLayout(signal_layout)
        panels_row1.addWidget(signal_group)

        # Predicted Direction
        direction_group = QGroupBox("Predicted Market Direction Indicator")
        direction_layout = QVBoxLayout()
        self.direction_arrow = QLabel("→")  # Or use QPixmap for arrow image
        self.direction_arrow.setFont(QFont("Arial", 14))
        self.direction_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.direction_arrow.setStyleSheet("color: red;")
        direction_layout.addWidget(self.direction_arrow)
        self.direction_value = QLabel("0.00")
        self.direction_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        direction_layout.addWidget(self.direction_value)
        direction_group.setLayout(direction_layout)
        panels_row1.addWidget(direction_group)

        # Minor Event
        minor_group = QGroupBox("Minor Event Consider")
        minor_layout = QVBoxLayout()
        self.minor_circle = QLabel("○")  # Circle symbol
        self.minor_circle.setFont(QFont("Arial", 24))
        self.minor_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.minor_circle.setStyleSheet("color: green;")
        minor_layout.addWidget(self.minor_circle)
        self.minor_text = QLabel("Purchase/Sale")
        minor_layout.addWidget(self.minor_text)
        minor_group.setLayout(minor_layout)
        panels_row1.addWidget(minor_group)

        # Stability Thresholds (left column)
        stability_group = QGroupBox("Stability Score Thresholds")
        stability_layout = QVBoxLayout()
        thresholds = [
            "85-100 Highly Stable (GREEN)",
            "70-84 Stable (GREEN)",
            "50-69 Transitional (YELLOW)",
            "30-49 Unstable (YELLOW)",
            "0-29 Collapse (RED)"
        ]
        for thresh in thresholds:
            label = QLabel(thresh)
            if "GREEN" in thresh:
                label.setStyleSheet("color: green;")
            elif "YELLOW" in thresh:
                label.setStyleSheet("color: yellow;")
            elif "RED" in thresh:
                label.setStyleSheet("color: red;")
            stability_layout.addWidget(label)
        stability_group.setLayout(stability_layout)
        main_layout.addWidget(stability_group)

        # Row for current score, major warnings
        bottom_row = QHBoxLayout()
        main_layout.addLayout(bottom_row)

        # Current Stability Score
        current_score_group = QGroupBox("Current Stability Score")
        score_layout = QVBoxLayout()
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(78)  # Default
        self.score_bar.setFormat("%v")
        self.score_bar.setStyleSheet("""
            QProgressBar { background-color: #353535; color: white; border: 1px solid #555; }
            QProgressBar::chunk { background-color: yellow; }  # Dynamic
        """)
        score_layout.addWidget(self.score_bar)
        self.score_trend = QLabel("Stability Trend: N/A")
        score_layout.addWidget(self.score_trend)
        current_score_group.setLayout(score_layout)
        bottom_row.addWidget(current_score_group)

        # Major Event Warning
        warning_group = QGroupBox("Major Event Warning 10 MIN")
        warning_layout = QVBoxLayout()
        self.warning_circle = QLabel("○")
        self.warning_circle.setFont(QFont("Arial", 24))
        self.warning_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_circle.setStyleSheet("color: magenta;")
        warning_layout.addWidget(self.warning_circle)
        self.warning_text = QLabel("Flash")
        warning_layout.addWidget(self.warning_text)
        warning_group.setLayout(warning_layout)
        bottom_row.addWidget(warning_group)

        # Major Event Occurred
        occurred_group = QGroupBox("Major Event Occurred")
        occurred_layout = QVBoxLayout()
        self.occurred_text = QLabel("Bought/Sold Shares Amount: N/A")
        occurred_layout.addWidget(self.occurred_text)
        enter_btn = QPushButton("ENTER")
        enter_btn.setStyleSheet("background-color: yellow; color: black;")
        enter_btn.clicked.connect(self.enter_action)  # Hook to your trade logic
        occurred_layout.addWidget(enter_btn)
        occurred_group.setLayout(occurred_layout)
        bottom_row.addWidget(occurred_group)

        # Indicator details section (all computed results)
        indicators_group = QGroupBox("All Computed Indicators")
        indicators_layout = QVBoxLayout()
        self.phi_sigma = QLabel("Phi Sigma: N/A")
        indicators_layout.addWidget(self.phi_sigma)
        self.directional = QLabel("Directional SVC_Delta: N/A")
        indicators_layout.addWidget(self.directional)
        self.cvd = QLabel("CVD Status: N/A | Momentum: N/A")
        indicators_layout.addWidget(self.cvd)
        self.tf_mod = QLabel("TF_mod: N/A")
        indicators_layout.addWidget(self.tf_mod)
        self.tf_crit = QLabel("TF_crit: N/A")  # No color
        indicators_layout.addWidget(self.tf_crit)
        self.tvi = QLabel("TVI Enhanced: N/A")
        indicators_layout.addWidget(self.tvi)
        indicators_group.setLayout(indicators_layout)
        main_layout.addWidget(indicators_group)

        # Controls
        controls_layout = QHBoxLayout()
        start_btn = QPushButton("Start Stream")
        start_btn.clicked.connect(self.start_engine)
        controls_layout.addWidget(start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_engine)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        main_layout.addLayout(controls_layout)

        # Status label
        self.status_label = QLabel("Status: Stopped")
        main_layout.addWidget(self.status_label)

        # Engine
        self.engine = None
        self.contract_id = get_current_gold_front_month_id()  # Auto front-month

        # Timer for UI refresh (e.g., flash animations)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(1000)  # 1s updates

    def start_engine(self):
        self.status_label.setText("Starting...")
        self.stop_btn.setEnabled(True)
        self.engine = EngineThread(self.contract_id)
        self.engine.log_signal.connect(self.process_log)
        self.engine.data_signal.connect(self.update_data)
        self.engine.status_signal.connect(self.status_label.setText)
        self.engine.start()

    def stop_engine(self):
        if self.engine:
            self.engine.stop()
        self.status_label.setText("Stopped")
        self.stop_btn.setEnabled(False)

    def update_data(self, data):
        # Update indicators with colors
        if 'phi_sigma' in data:
            val = data['phi_sigma']
            self.phi_sigma.setText(f"Phi Sigma: {val:.4f}")
            color = 'green' if val > 0 else 'red'
            self.phi_sigma.setStyleSheet(f"color: {color};")
        if 'directional' in data:
            val = data['directional']
            self.directional.setText(f"Directional SVC_Delta: {val:.4f}")
            color = 'green' if val > 0 else 'red'
            self.directional.setStyleSheet(f"color: {color};")
            self.direction_value.setText(f"{val:.2f}")
            arrow = '↑' if val > 0 else '↓' if val < 0 else '→'
            self.direction_arrow.setText(arrow)
            self.direction_arrow.setStyleSheet(f"color: {color};")
        if 'cvd_status' in data:
            status = data['cvd_status']
            momentum = data['cvd_momentum']
            self.cvd.setText(f"CVD Status: {status} | Momentum: {momentum}")
            color = 'green' if 'BULLISH' in status else 'red' if 'BEARISH' in status else 'yellow'
            self.cvd.setStyleSheet(f"color: {color};")
        if 'tf_mod' in data:
            self.tf_mod.setText(f"TF_mod: {data['tf_mod']}")
            # Color based on value if needed
        if 'tf_crit' in data:
            self.tf_crit.setText(f"TF_crit: {data['tf_crit']}")  # No color
        if 'tvi' in data:
            self.tvi.setText(f"TVI Enhanced: {data['tvi']}")
        if 'signal' in data:
            sig = data['signal']
            self.signal_label.setText(sig)
            color = 'green' if sig == 'BUY' else 'red' if sig == 'SELL' else 'yellow'
            self.signal_label.setStyleSheet(f"color: {color};")

        # Update score bar (assume stability from CVD or phi)
        # Example: Use phi or directional for score (customize)
        score = 78  # Placeholder - map from your data
        self.score_bar.setValue(score)
        chunk_color = 'green' if score >= 70 else 'yellow' if score >= 30 else 'red'
        self.score_bar.setStyleSheet(f"""
            QProgressBar::chunk {{ background-color: {chunk_color}; }}
        """)

        # Contract/price/volume/timestamp from logs
        # Parse from clean_line in process_log if needed

    def process_log(self, line):
        # Additional parsing for header info
        if "Contract:" in line:
            self.contract_label.setText(line)
        if "Timestamp:" in line:
            self.timestamp_label.setText(line)
        if "Price:" in line:
            self.price_label.setText(line)
        if "Volume:" in line:
            self.volume_label.setText(line)
        # Major event triggers
        if "Major Event" in line:
            self.warning_circle.setStyleSheet("color: red;")
            self.tray_icon.showMessage("Major Event", "Warning: Event in 10 min", QSystemTrayIcon.MessageIcon.Warning)

    def refresh_ui(self):
        # Flash for warnings (e.g., toggle visibility)
        pass  # Implement flash animation if needed

    def enter_action(self):
        # Your trade entry logic here (e.g., open dialog)
        print("ENTER clicked - execute trade")

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("Gestalt Dashboard", "Minimized to tray", QSystemTrayIcon.MessageIcon.Information)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GestaltGUI()
    window.show()
    sys.exit(app.exec())
