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

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Auto-select current gold front month
def get_gold_contract():
    now = datetime.now()
    m = now.month
    y = str(now.year)[-1]
    active_months = {2:'G', 4:'J', 6:'M', 8:'Q', 10:'V', 12:'Z'}
    next_m = next((mm for mm in sorted(active_months) if mm >= m), 2)
    if next_m < m:
        y = str(now.year + 1)[-1]
    return f"CON.F.US.GCE.{active_months[next_m]}{y}"

class EngineThread(QThread):
    new_line = pyqtSignal(str)
    data_update = pyqtSignal(dict)

    def __init__(self, contract_id):
        super().__init__()
        self.contract_id = contract_id
        self.process = None

    def run(self):
        cmd = [
            sys.executable,
            "main.py",
            "--contract_id", self.contract_id,
            "--mode", "realtime",
            "--provider", "topstepx"
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        for line in iter(self.process.stdout.readline, ''):
            clean = line.strip()
            if not clean:
                continue
            self.new_line.emit(clean)

            update = {}

            # Contract / Ticker
            if re.search(r'(contract|ticker|symbol).*CON\.F\.US\.GCE', clean, re.I):
                m = re.search(r'(CON\.F\.US\.GCE\.[A-Z]\d+)', clean, re.I)
                if m:
                    update['contract'] = m.group(1)

            # Timestamp
            m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', clean)
            if m:
                update['timestamp'] = m.group(1)

            # Price
            m = re.search(r'(?:price|close|last|settle).*?([\d,]+\.?\d{1,2})', clean, re.I)
            if m:
                update['price'] = m.group(1)

            # Volume
            m = re.search(r'volume.*?(\d[\d,]*\d)', clean, re.I)
            if m:
                update['volume'] = m.group(1)

            # Signal
            if "signal:" in clean.lower():
                sig = clean.split(":", 1)[1].strip().upper()
                update['signal'] = sig

            # Direction
            m = re.search(r'directional.*?([-+]?\d*\.?\d+)', clean, re.I)
            if m:
                val = float(m.group(1))
                update['dir_value'] = f"{val:+.2f}"
                update['dir_sign'] = '↑' if val > 0 else '↓' if val < 0 else '→'

            if update:
                self.data_update.emit(update)

    def stop(self):
        if self.process:
            self.process.terminate()


class GestaltDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GESTALT - Tactical Market Intelligence")
        self.resize(1280, 720)

        # Dark theme
        app.setStyle(QStyleFactory.create("Fusion"))
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(15, 15, 25))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 255))
        pal.setColor(QPalette.ColorRole.Base, QColor(25, 25, 40))
        pal.setColor(QPalette.ColorRole.Text, QColor(230, 230, 255))
        pal.setColor(QPalette.ColorRole.Button, QColor(40, 40, 60))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(230, 230, 255))
        app.setPalette(pal)

        # System tray
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon))
        menu = QMenu()
        menu.addAction("Restore", self.showNormal)
        menu.addAction("Quit", app.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        header.setSpacing(15)

        self.lbl_contract = QLabel("CONTRACT: Loading...")
        self.lbl_timestamp = QLabel("TIMESTAMP: —")
        self.lbl_price = QLabel("Price: —")
        self.lbl_volume = QLabel("VOLUME: —")

        for lbl in [self.lbl_contract, self.lbl_timestamp, self.lbl_price, self.lbl_volume]:
            lbl.setStyleSheet("font-weight:bold; padding:6px; background:#1e1e35; border-radius:4px;")

        header.addWidget(self.lbl_contract)
        header.addWidget(self.lbl_timestamp)
        header.addStretch()
        header.addWidget(self.lbl_price)
        header.addWidget(self.lbl_volume)
        main_layout.addLayout(header)

        # Three main cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # Signal card
        signal_card = QGroupBox("Indicator based on current holdings")
        s_lay = QVBoxLayout()
        self.signal_main = QLabel("HOLD")
        self.signal_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signal_main.setStyleSheet("font-size:34px; font-weight:bold; color:#ffcc00;")
        s_lay.addWidget(self.signal_main)
        s_lay.addWidget(QLabel("Signal History: —"), alignment=Qt.AlignmentFlag.AlignCenter)
        signal_card.setLayout(s_lay)
        signal_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        cards_layout.addWidget(signal_card)

        # Direction card
        dir_card = QGroupBox("Predicted Market Direction Indicator")
        d_lay = QHBoxLayout()
        self.dir_arrow = QLabel("→")
        self.dir_arrow.setStyleSheet("font-size:52px; color:#ff4444;")
        self.dir_value = QLabel("-.03")
        self.dir_value.setStyleSheet("font-size:26px;")
        d_lay.addWidget(self.dir_arrow)
        d_lay.addWidget(self.dir_value)
        dir_card.setLayout(d_lay)
        dir_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        cards_layout.addWidget(dir_card)

        # Minor event
        minor_card = QGroupBox("Minor Event Consider")
        m_lay = QVBoxLayout()
        self.minor_circle = QLabel("●")
        self.minor_circle.setStyleSheet("font-size:52px; color:#44ff44;")
        m_lay.addWidget(self.minor_circle, alignment=Qt.AlignmentFlag.AlignCenter)
        m_lay.addWidget(QLabel("Purchase/Sale"), alignment=Qt.AlignmentFlag.AlignCenter)
        minor_card.setLayout(m_lay)
        minor_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        cards_layout.addWidget(minor_card)

        main_layout.addLayout(cards_layout)

        # Bottom row
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        # Stability thresholds
        thresh_card = QGroupBox("STABILITY SCORE THRESHOLDS")
        t_lay = QVBoxLayout()
        thresholds = [
            ("85-100 Highly stable", "#00ff00"),
            ("70-84 Stable", "#00ff00"),
            ("50-69 Transitional", "#ffcc00"),
            ("30-49 Unstable", "#ffcc00"),
            ("0-29 Collapse", "#ff4444")
        ]
        for text, color in thresholds:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{color};")
            t_lay.addWidget(lbl)
        thresh_card.setLayout(t_lay)
        thresh_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        bottom_row.addWidget(thresh_card)

        # Current score
        score_card = QGroupBox("Current Stability Score")
        s_lay = QVBoxLayout()
        self.score_progress = QProgressBar()
        self.score_progress.setRange(0, 100)
        self.score_progress.setValue(78)
        self.score_progress.setStyleSheet("""
            QProgressBar {background:#222; border:1px solid #444; color:white;}
            QProgressBar::chunk {background:#ffcc00;}
        """)
        s_lay.addWidget(self.score_progress)
        s_lay.addWidget(QLabel("Stability Trend ="))
        score_card.setLayout(s_lay)
        score_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        bottom_row.addWidget(score_card)

        # Major warning
        warn_card = QGroupBox("MAJOR EVENT WARNING 10 MIN")
        w_lay = QVBoxLayout()
        self.warn_label = QLabel("FLASH")
        self.warn_label.setStyleSheet("font-size:26px; color:#ff44ff; font-weight:bold;")
        w_lay.addWidget(self.warn_label, alignment=Qt.AlignmentFlag.AlignCenter)
        warn_card.setLayout(w_lay)
        warn_card.setStyleSheet("border:2px solid #ff44ff; border-radius:6px; padding:10px; background:rgba(255,68,255,0.08);")
        bottom_row.addWidget(warn_card)

        # Major occurred
        occ_card = QGroupBox("MAJOR EVENT OCCURRED")
        o_lay = QVBoxLayout()
        o_lay.addWidget(QLabel("BOUGHT/SOLD SHARES AMOUNT ="))
        btn_enter = QPushButton("ENTER")
        btn_enter.setStyleSheet("background:#ffcc00; color:black; font-weight:bold; padding:10px;")
        o_lay.addWidget(btn_enter)
        occ_card.setLayout(o_lay)
        occ_card.setStyleSheet("border:2px solid #ff4444; border-radius:6px; padding:10px;")
        bottom_row.addWidget(occ_card)

        main_layout.addLayout(bottom_row)

        # Controls
        ctrl = QHBoxLayout()
        btn_start = QPushButton("START")
        btn_start.clicked.connect(self.start_engine)
        btn_stop = QPushButton("STOP")
        btn_stop.clicked.connect(self.stop_engine)
        ctrl.addWidget(btn_start)
        ctrl.addWidget(btn_stop)
        main_layout.addLayout(ctrl)

        self.status_label = QLabel("Status: Ready")
        main_layout.addWidget(self.status_label)

        # Engine
        self.engine_thread = None
        self.contract = get_gold_contract()

        # Initial header
        self.lbl_contract.setText(f"CONTRACT: {self.contract}")
        self.lbl_timestamp.setText(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def start_engine(self):
        if self.engine_thread and self.engine_thread.isRunning():
            return
        self.status_label.setText("Engine starting...")
        self.engine_thread = EngineThread(self.contract)
        self.engine_thread.new_line.connect(self.status_label.setText)
        self.engine_thread.data_update.connect(self.update_ui)
        self.engine_thread.start()

    def stop_engine(self):
        if self.engine_thread:
            self.engine_thread.stop()
        self.status_label.setText("Engine stopped")

    def update_ui(self, data):
        if 'contract' in data:
            self.lbl_contract.setText(f"CONTRACT: {data['contract']}")
        if 'timestamp' in data:
            self.lbl_timestamp.setText(f"TIMESTAMP: {data['timestamp']}")
        if 'price' in data:
            self.lbl_price.setText(data['price'])
        if 'volume' in data:
            self.lbl_volume.setText(f"VOLUME: {data['volume']}")
        if 'signal' in data:
            sig = data['signal']
            color = "#00ff00" if sig == "BUY" else "#ff4444" if sig == "SELL" else "#ffcc00"
            self.signal_main.setText(sig)
            self.signal_main.setStyleSheet(f"font-size:34px; font-weight:bold; color:{color};")
        if 'dir_value' in data:
            self.dir_value.setText(data['dir_value'])
            self.dir_arrow.setText(data['dir_sign'])
            color = "#00ff00" if data['dir_sign'] == '↑' else "#ff4444" if data['dir_sign'] == '↓' else "#ffcc00"
            self.dir_arrow.setStyleSheet(f"font-size:52px; color:{color};")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("GESTALT", "Minimized to tray", QSystemTrayIcon.MessageIcon.Information)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GestaltDashboard()
    window.show()
    sys.exit(app.exec())
