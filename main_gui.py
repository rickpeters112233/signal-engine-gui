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

# Project setup
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

# Simple front month resolver
def get_gold_front():
    now = datetime.now()
    m = now.month
    y = str(now.year)[-1]
    active = [2,4,6,8,10,12]
    next_m = next((x for x in active if x >= m), active[0])
    if next_m < m:
        y = str(now.year + 1)[-1]
    code = {2:'G',4:'J',6:'M',8:'Q',10:'V',12:'Z'}[next_m]
    return f"CON.F.US.GCE.{code}{y}"

class EngineThread(QThread):
    log = pyqtSignal(str)
    update = pyqtSignal(dict)

    def __init__(self, contract):
        super().__init__()
        self.contract = contract
        self.proc = None

    def run(self):
        cmd = [
            sys.executable, "main.py",
            "--contract_id", self.contract,
            "--mode", "realtime",
            "--provider", "topstepx"
            
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        for line in iter(self.proc.stdout.readline, ''):
            clean = line.strip()
            if not clean: continue
            self.log.emit(clean)

            data = {}
            lower = clean.lower()

            # Contract
            if "contract:" in lower or "con.f.us.gce" in lower:
                m = re.search(r'(CON\.F\.US\.GCE\.[A-Z]\d+)', clean) or \
                    re.search(r'([A-Z]{3}\d+)', clean)
                if m: data['contract'] = m.group(1)

            # Timestamp
            if "timestamp" in lower:
                m = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', clean)
                if m: data['ts'] = m.group()

            # Price
            if "price" in lower or "close" in lower or "last" in lower:
                m = re.search(r'[\d,]+\.?\d{1,2}', clean)
                if m: data['price'] = m.group()

            # Volume
            if "volume" in lower:
                m = re.search(r'(\d+)', clean)
                if m: data['volume'] = m.group(1)

            # Signal
            if "signal:" in lower:
                sig = clean.split(":",1)[1].strip()
                data['signal'] = sig.upper()

            # Directional / arrow
            if "directional=" in clean:
                try:
                    val = float(re.search(r'[-+]?\d*\.?\d+', clean).group())
                    data['direction_val'] = f"{val:+.2f}"
                    data['direction_sign'] = '↑' if val > 0 else '↓' if val < 0 else '→'
                except:
                    pass

            # Stability score (example)
            if "stability" in lower or "score" in lower:
                m = re.search(r'(\d{1,3})', clean)
                if m: data['score'] = int(m.group(1))

            if data:
                self.update.emit(data)

    def stop(self):
        if self.proc:
            self.proc.terminate()


class FastDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GESTALT")
        self.setGeometry(100, 100, 1280, 720)
        self.setStyleSheet("background-color: #0f0f1a; color: #e0e0ff;")

        # Tray
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        menu = QMenu()
        menu.addAction("Show", self.showNormal)
        menu.addAction("Exit", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(8)

        # Header bar
        header = QHBoxLayout()
        header.setSpacing(20)
        self.lbl_contract = QLabel("CONTRACT: Loading...")
        self.lbl_ts = QLabel("TIMESTAMP: —")
        self.lbl_price = QLabel("4449.8")
        self.lbl_vol = QLabel("VOLUME: 137")
        for lbl in [self.lbl_contract, self.lbl_ts, self.lbl_price, self.lbl_vol]:
            lbl.setStyleSheet("font-weight:bold; font-size:13px; padding:4px; background:#1a1a2e; border-radius:4px;")
        header.addWidget(self.lbl_contract)
        header.addWidget(self.lbl_ts)
        header.addStretch()
        header.addWidget(self.lbl_price)
        header.addWidget(self.lbl_vol)
        layout.addLayout(header)

        # Main cards row
        cards = QHBoxLayout()
        cards.setSpacing(12)

        # Signal card
        card1 = QGroupBox("Indicator based on current holdings")
        l1 = QVBoxLayout()
        self.sig_big = QLabel("HOLD")
        self.sig_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sig_big.setStyleSheet("font-size:32px; font-weight:bold; color:#ffcc00;")
        l1.addWidget(self.sig_big)
        l1.addWidget(QLabel("Signal History: 44"), alignment=Qt.AlignmentFlag.AlignCenter)
        card1.setLayout(l1)
        card1.setStyleSheet("QGroupBox {border:2px solid #444; border-radius:6px; padding:8px;}")
        cards.addWidget(card1)

        # Direction card
        card2 = QGroupBox("Predicted Market Direction Indicator")
        l2 = QHBoxLayout()
        self.dir_arrow = QLabel("↓")
        self.dir_arrow.setStyleSheet("font-size:48px; color:#ff4444;")
        self.dir_val = QLabel("-0.03")
        self.dir_val.setStyleSheet("font-size:24px;")
        l2.addWidget(self.dir_arrow)
        l2.addWidget(self.dir_val)
        card2.setLayout(l2)
        card2.setStyleSheet("QGroupBox {border:2px solid #444; border-radius:6px; padding:8px;}")
        cards.addWidget(card2)

        # Minor event
        card3 = QGroupBox("Minor Event Consider")
        l3 = QVBoxLayout()
        self.minor_dot = QLabel("●")
        self.minor_dot.setStyleSheet("font-size:48px; color:#44ff44;")
        l3.addWidget(self.minor_dot, alignment=Qt.AlignmentFlag.AlignCenter)
        l3.addWidget(QLabel("Purchase/Sale"), alignment=Qt.AlignmentFlag.AlignCenter)
        card3.setLayout(l3)
        card3.setStyleSheet("QGroupBox {border:2px solid #444; border-radius:6px; padding:8px;}")
        cards.addWidget(card3)

        layout.addLayout(cards)

        # Thresholds + score + events
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        # Stability thresholds
        thresh = QGroupBox("STABILITY SCORE THRESHOLDS")
        lt = QVBoxLayout()
        items = [
            ("85-100 Highly stable", "green"),
            ("70-84 Stable", "green"),
            ("50-69 Transitional", "yellow"),
            ("30-49 Unstable", "yellow"),
            ("0-29 Collapse", "red")
        ]
        for text, color in items:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{color};")
            lt.addWidget(lbl)
        thresh.setLayout(lt)
        thresh.setStyleSheet("QGroupBox {border:2px solid #444; border-radius:6px; padding:8px;}")
        bottom.addWidget(thresh)

        # Current score
        score = QGroupBox("Current Stability Score")
        ls = QVBoxLayout()
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0,100)
        self.score_bar.setValue(78)
        self.score_bar.setStyleSheet("""
            QProgressBar {background:#222; color:white; border:1px solid #444;}
            QProgressBar::chunk {background:#ffcc00;}
        """)
        ls.addWidget(self.score_bar)
        ls.addWidget(QLabel("Stability Trend ="))
        score.setLayout(ls)
        score.setStyleSheet("QGroupBox {border:2px solid #444; border-radius:6px; padding:8px;}")
        bottom.addWidget(score)

        # Major warning
        warn = QGroupBox("MAJOR EVENT WARNING 10 MIN")
        lw = QVBoxLayout()
        self.warn_dot = QLabel("FLASH")
        self.warn_dot.setStyleSheet("font-size:28px; color:#ff44ff; font-weight:bold;")
        lw.addWidget(self.warn_dot, alignment=Qt.AlignmentFlag.AlignCenter)
        warn.setLayout(lw)
        warn.setStyleSheet("QGroupBox {border:2px solid #ff44ff; border-radius:6px; padding:8px; background:rgba(255,68,255,0.08);}")
        bottom.addWidget(warn)

        # Major occurred
        occ = QGroupBox("MAJOR EVENT OCCURRED")
        lo = QVBoxLayout()
        lo.addWidget(QLabel("BOUGHT/SOLD SHARES AMOUNT ="))
        enter = QPushButton("ENTER")
        enter.setStyleSheet("background:#ffcc00; color:black; font-weight:bold; padding:8px;")
        lo.addWidget(enter)
        occ.setLayout(lo)
        occ.setStyleSheet("QGroupBox {border:2px solid #ff4444; border-radius:6px; padding:8px;}")
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

        self.engine = None
        self.contract = get_gold_front()

    def start_engine(self):
        if self.engine and self.engine.isRunning():
            return
        self.status.setText("Starting engine...")
        self.engine = EngineThread(self.contract)
        self.engine.log.connect(self.status.setText)
        self.engine.update.connect(self.apply_update)
        self.engine.start()

    def stop_engine(self):
        if self.engine:
            self.engine.stop()
        self.status.setText("Stopped")

    def apply_update(self, d):
        if 'contract' in d:
            self.lbl_contract.setText(f"CONTRACT: {d['contract']}")
        if 'ts' in d:
            self.lbl_ts.setText(f"TIMESTAMP: {d['ts']}")
        if 'price' in d:
            self.lbl_price.setText(d['price'])
        if 'volume' in d:
            self.lbl_vol.setText(f"VOLUME: {d['volume']}")
        if 'signal' in d:
            sig = d['signal']
            color = "#00ff00" if sig == "BUY" else "#ff4444" if sig == "SELL" else "#ffcc00"
            self.sig_big.setText(sig)
            self.sig_big.setStyleSheet(f"font-size:32px; font-weight:bold; color:{color};")
        if 'direction_val' in d:
            self.dir_val.setText(d['direction_val'])
            self.dir_arrow.setText(d['direction_sign'])
            color = "#00ff00" if "↑" in d['direction_sign'] else "#ff4444" if "↓" in d['direction_sign'] else "#ffcc00"
            self.dir_arrow.setStyleSheet(f"font-size:48px; color:{color};")
        if 'score' in d:
            v = d['score']
            self.score_bar.setValue(v)
            color = "#00ff00" if v >= 70 else "#ffcc00" if v >= 30 else "#ff4444"
            self.score_bar.setStyleSheet(f"QProgressBar::chunk {{background:{color};}}")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("GESTALT", "Running in background", QSystemTrayIcon.MessageIcon.Information)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(15,15,26))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220,220,255))
    palette.setColor(QPalette.ColorRole.Base, QColor(25,25,40))
    palette.setColor(QPalette.ColorRole.Text, QColor(220,220,255))
    palette.setColor(QPalette.ColorRole.Button, QColor(40,40,60))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220,220,255))
    app.setPalette(palette)

    w = FastDashboard()
    w.show()
    sys.exit(app.exec())
