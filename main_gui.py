import sys
import os
import subprocess
import re
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QProgressBar, QSystemTrayIcon, QMenu, QStyleFactory, QStyle
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont

# Change to your project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Auto front-month gold contract (Feb 2026 = G26 as of Jan 15, 2026)
def get_gold_contract():
    now = datetime.now()
    month = now.month
    year_digit = str(now.year)[-1]
    active = {2: 'G', 4: 'J', 6: 'M', 8: 'Q', 10: 'V', 12: 'Z'}
    next_month = next((m for m in sorted(active) if m >= month), min(active))
    if next_month < month:
        year_digit = str(now.year + 1)[-1]
    return f"CON.F.US.GCE.{active[next_month]}{year_digit}"

class EngineThread(QThread):
    log_line = pyqtSignal(str)
    data_update = pyqtSignal(dict)

    def __init__(self, contract_id):
        super().__init__()
        self.contract_id = contract_id
        self.proc = None

    def run(self):
        cmd = [
            sys.executable,
            "main.py",
            "--contract_id", self.contract_id,
            "--mode", "realtime",
            "--provider", "topstepx"
        ]

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        for line in iter(self.proc.stdout.readline, ''):
            clean = line.strip()
            if not clean:
                continue
            self.log_line.emit(clean)

            update = {}
            lower = clean.lower()

            # Contract variations
            if any(k in lower for k in ["contract", "ticker", "symbol", "con.f.us.gce"]):
                m = re.search(r'(CON\.F\.US\.GCE\.[A-Z]\d+)', clean, re.I)
                if m:
                    update['contract'] = m.group(1)

            # Timestamp
            m = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', clean)
            if m:
                update['timestamp'] = m.group()

            # Price (last/close)
            m = re.search(r'(?:price|close|last|settle).*?([\d,]+\.?\d{1,2})', clean, re.I)
            if m:
                update['price'] = m.group(1)

            # Volume
            m = re.search(r'volume.*?(\d[\d,]*\d)', clean, re.I)
            if m:
                update['volume'] = m.group(1)

            # Signal
            if "signal:" in lower:
                sig = clean.split(":", 1)[1].strip().upper()
                update['signal'] = sig

            # Direction / arrow
            m = re.search(r'directional.*?([-+]?\d*\.?\d+)', clean, re.I)
            if m:
                val = float(m.group(1))
                update['dir_value'] = f"{val:+.2f}"
                update['dir_sign'] = '↑' if val > 0 else '↓' if val < 0 else '→'

            if update:
                self.data_update.emit(update)

    def stop(self):
        if self.proc:
            self.proc.terminate()


class GestaltDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GESTALT")
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

        # Tray icon - no warning
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon))
        menu = QMenu()
        menu.addAction("Restore", self.showNormal)
        menu.addAction("Quit", app.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self.lbl_contract = QLabel(f"CONTRACT: {get_gold_contract()}")
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
        layout.addLayout(header)

        # Three main cards
        cards = QHBoxLayout()
        cards.setSpacing(12)

        # Signal
        signal_card = QGroupBox("Indicator based on current holdings")
        s_lay = QVBoxLayout()
        self.sig_big = QLabel("HOLD")
        self.sig_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sig_big.setStyleSheet("font-size:34px; font-weight:bold; color:#ffcc00;")
        s_lay.addWidget(self.sig_big)
        s_lay.addWidget(QLabel("Signal History: —"), alignment=Qt.AlignmentFlag.AlignCenter)
        signal_card.setLayout(s_lay)
        signal_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        cards.addWidget(signal_card)

        # Direction
        dir_card = QGroupBox("Predicted Market Direction Indicator")
        d_lay = QHBoxLayout()
        self.dir_arrow = QLabel("→")
        self.dir_arrow.setStyleSheet("font-size:52px; color:#ff4444;")
        self.dir_value = QLabel("-.03")
        d_lay.addWidget(self.dir_arrow)
        d_lay.addWidget(self.dir_value)
        dir_card.setLayout(d_lay)
        dir_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        cards.addWidget(dir_card)

        # Minor event
        minor_card = QGroupBox("Minor Event Consider")
        m_lay = QVBoxLayout()
        self.minor_circle = QLabel("●")
        self.minor_circle.setStyleSheet("font-size:52px; color:#44ff44;")
        m_lay.addWidget(self.minor_circle, alignment=Qt.AlignmentFlag.AlignCenter)
        m_lay.addWidget(QLabel("Purchase/Sale"), alignment=Qt.AlignmentFlag.AlignCenter)
        minor_card.setLayout(m_lay)
        minor_card.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        cards.addWidget(minor_card)

        layout.addLayout(cards)

        # Bottom row
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        # Thresholds
        thresh = QGroupBox("STABILITY SCORE THRESHOLDS")
        t_lay = QVBoxLayout()
        items = [
            ("85-100 Highly stable", "#00ff00"),
            ("70-84 Stable", "#00ff00"),
            ("50-69 Transitional", "#ffcc00"),
            ("30-49 Unstable", "#ffcc00"),
            ("0-29 Collapse", "#ff4444")
        ]
        for txt, col in items:
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color:{col};")
            t_lay.addWidget(lbl)
        thresh.setLayout(t_lay)
        thresh.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        bottom.addWidget(thresh)

        # Current score
        score = QGroupBox("Current Stability Score")
        s_lay = QVBoxLayout()
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(78)
        self.score_bar.setStyleSheet("QProgressBar {background:#222; border:1px solid #444; color:white;} QProgressBar::chunk {background:#ffcc00;}")
        s_lay.addWidget(self.score_bar)
        s_lay.addWidget(QLabel("Stability Trend ="))
        score.setLayout(s_lay)
        score.setStyleSheet("border:2px solid #444; border-radius:6px; padding:10px;")
        bottom.addWidget(score)

        # Major warning
        warn = QGroupBox("MAJOR EVENT WARNING 10 MIN")
        w_lay = QVBoxLayout()
        self.warn_dot = QLabel("FLASH")
        self.warn_dot.setStyleSheet("font-size:26px; color:#ff44ff; font-weight:bold;")
        w_lay.addWidget(self.warn_dot, alignment=Qt.AlignmentFlag.AlignCenter)
        warn.setLayout(w_lay)
        warn.setStyleSheet("border:2px solid #ff44ff; border-radius:6px; padding:10px; background:rgba(255,68,255,0.08);")
        bottom.addWidget(warn)

        # Major occurred
        occ = QGroupBox("MAJOR EVENT OCCURRED")
        o_lay = QVBoxLayout()
        o_lay.addWidget(QLabel("BOUGHT/SOLD SHARES AMOUNT ="))
        btn = QPushButton("ENTER")
        btn.setStyleSheet("background:#ffcc00; color:black; font-weight:bold; padding:10px;")
        o_lay.addWidget(btn)
        occ.setLayout(o_lay)
        occ.setStyleSheet("border:2px solid #ff4444; border-radius:6px; padding:10px;")
        bottom.addWidget(occ)

        layout.addLayout(bottom)

        # Controls
        ctrl = QHBoxLayout()
        start = QPushButton("START")
        start.clicked.connect(self.start_engine)
        stop = QPushButton("STOP")
        stop.clicked.connect(self.stop_engine)
        ctrl.addWidget(start)
        ctrl.addWidget(stop)
        layout.addLayout(ctrl)

        self.status = QLabel("Status: Ready")
        layout.addWidget(self.status)

        # Engine
        self.engine = None

    def start_engine(self):
        if self.engine and self.engine.isRunning():
            return
        self.status.setText("Starting...")
        self.engine = EngineThread(get_gold_contract())
        self.engine.log_line.connect(self.status.setText)
        self.engine.data_update.connect(self.update_data)
        self.engine.start()

    def stop_engine(self):
        if self.engine:
            self.engine.stop()
        self.status.setText("Stopped")

    def update_data(self, d):
        if 'contract' in d:
            self.lbl_contract.setText(f"CONTRACT: {d['contract']}")
        if 'timestamp' in d:
            self.lbl_timestamp.setText(f"TIMESTAMP: {d['timestamp']}")
        if 'price' in d:
            self.lbl_price.setText(d['price'])
        if 'volume' in d:
            self.lbl_volume.setText(f"VOLUME: {d['volume']}")
        if 'signal' in d:
            color = "#00ff00" if d['signal'] == "BUY" else "#ff4444" if d['signal'] == "SELL" else "#ffcc00"
            self.signal_main.setText(d['signal'])
            self.signal_main.setStyleSheet(f"font-size:34px; font-weight:bold; color:{color};")
        if 'dir_value' in d:
            self.dir_value.setText(d['dir_value'])
            self.dir_arrow.setText(d['dir_sign'])
            color = "#00ff00" if d['dir_sign'] == '↑' else "#ff4444" if d['dir_sign'] == '↓' else "#ffcc00"
            self.dir_arrow.setStyleSheet(f"font-size:52px; color:{color};")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("GESTALT", "Minimized to tray")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = GestaltDashboard()
    win.show()
    sys.exit(app.exec())
