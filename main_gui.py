import sys
import os
import subprocess
import re
from datetime import datetime
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QProgressBar, QSystemTrayIcon, QMenu, QStyleFactory, QStyle
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Auto front month gold
def get_gold_contract():
    now = datetime.now()
    m = now.month
    y = str(now.year)[-1]
    active = {2:'G',4:'J',6:'M',8:'Q',10:'V',12:'Z'}
    nm = next((mm for mm in sorted(active) if mm >= m), min(active))
    if nm < m:
        y = str(now.year + 1)[-1]
    return f"CON.F.US.GCE.{active[nm]}{y}"

class EngineThread(QThread):
    log = pyqtSignal(str)
    data = pyqtSignal(dict)

    def __init__(self, contract):
        super().__init__()
        self.contract = contract
        self.proc = None
        self._stop_requested = False

    def run(self):
        cmd = [
            sys.executable, "main.py",
            "--contract_id", self.contract,
            "--mode", "realtime",
            "--provider", "topstepx"
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, universal_newlines=True)

        for line in iter(self.proc.stdout.readline, ''):
            if self._stop_requested:
                break
            clean = line.strip()
            if not clean: continue
            self.log.emit(clean)

            d = {}
            low = clean.lower()

            if any(x in low for x in ["contract", "ticker", "con.f.us.gce"]):
                m = re.search(r'(CON\.F\.US\.GCE\.[A-Z]\d+)', clean, re.I)
                if m: d['contract'] = m.group(1)

            m = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', clean)
            if m: d['ts'] = m.group()

            m = re.search(r'(?:price|close|last).*?([\d,]+\.?\d+)', clean, re.I)
            if m: d['price'] = m.group(1)

            m = re.search(r'volume.*?(\d[\d,]*\d)', clean, re.I)
            if m: d['vol'] = m.group(1)

            if "signal:" in low:
                sig = clean.split(":",1)[1].strip().upper()
                d['signal'] = sig

            m = re.search(r'directional.*?([-+]?\d*\.?\d+)', clean, re.I)
            if m:
                v = float(m.group(1))
                d['dir_val'] = f"{v:+.2f}"
                d['dir_arrow'] = '↑' if v > 0 else '↓' if v < 0 else '→'

            if d:
                self.data.emit(d)

    def stop(self):
        self._stop_requested = True
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

class GestaltDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GESTALT")
        self.resize(1300, 850)

        # Dark theme
        app.setStyle(QStyleFactory.create("Fusion"))
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(10,10,20))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(240,240,255))
        pal.setColor(QPalette.ColorRole.Base, QColor(20,20,35))
        pal.setColor(QPalette.ColorRole.Text, QColor(240,240,255))
        app.setPalette(pal)

        # Tray
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon))
        menu = QMenu()
        menu.addAction("Restore", self.showNormal)
        menu.addAction("Exit", self.full_exit)
        self.tray.setContextMenu(menu)
        self.tray.show()

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(10,10,10,10)
        main_lay.setSpacing(8)

        # Header
        header = QHBoxLayout()
        self.contract_lbl = QLabel(f"CONTRACT: {get_gold_contract()}")
        self.ts_lbl = QLabel("TIMESTAMP: —")
        self.price_lbl = QLabel("Price: —")
        self.vol_lbl = QLabel("VOLUME: —")

        for lbl in [self.contract_lbl, self.ts_lbl, self.price_lbl, self.vol_lbl]:
            lbl.setStyleSheet("font-weight:bold; padding:8px; background:#0d1a2e; border-radius:4px; color:#88ff88;")

        header.addWidget(self.contract_lbl)
        header.addWidget(self.ts_lbl)
        header.addStretch()
        header.addWidget(self.price_lbl)
        header.addWidget(self.vol_lbl)
        main_lay.addLayout(header)

        # Three cards row
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        sig_card = QGroupBox("Indicator based on current holdings")
        s_lay = QVBoxLayout()
        self.sig = QLabel("HOLD")
        self.sig.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sig.setStyleSheet("font-size:36px; font-weight:bold; color:#ffdd00;")
        s_lay.addWidget(self.sig)
        s_lay.addWidget(QLabel("Signal History: —"), alignment=Qt.AlignmentFlag.AlignCenter)
        sig_card.setLayout(s_lay)
        sig_card.setStyleSheet("border:2px solid #444; border-radius:8px; background:#1a1a2e;")
        row1.addWidget(sig_card)

        dir_card = QGroupBox("Predicted Market Direction Indicator")
        d_lay = QHBoxLayout()
        self.arrow = QLabel("→")
        self.arrow.setStyleSheet("font-size:60px; color:#ff4444;")
        self.dir_val = QLabel("-.03")
        d_lay.addWidget(self.arrow)
        d_lay.addWidget(self.dir_val)
        dir_card.setLayout(d_lay)
        dir_card.setStyleSheet("border:2px solid #444; border-radius:8px; background:#1a1a2e;")
        row1.addWidget(dir_card)

        minor_card = QGroupBox("Minor Event Consider")
        m_lay = QVBoxLayout()
        self.minor = QLabel("●")
        self.minor.setStyleSheet("font-size:60px; color:#44ff44;")
        m_lay.addWidget(self.minor, alignment=Qt.AlignmentFlag.AlignCenter)
        m_lay.addWidget(QLabel("Purchase/Sale"), alignment=Qt.AlignmentFlag.AlignCenter)
        minor_card.setLayout(m_lay)
        minor_card.setStyleSheet("border:2px solid #444; border-radius:8px; background:#1a1a2e;")
        row1.addWidget(minor_card)

        main_lay.addLayout(row1)

        # Bottom row
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        thresh = QGroupBox("STABILITY SCORE THRESHOLDS")
        t_lay = QVBoxLayout()
        thresholds = [
            ("85-100 Highly stable", "#00ff00", "✓"),
            ("70-84 Stable", "#00ff00", "✓"),
            ("50-69 Transitional", "#ffdd00", "!"),
            ("30-49 Unstable", "#ffdd00", "⚠"),
            ("0-29 Collapse", "#ff4444", "X")
        ]
        for txt, col, icon in thresholds:
            lbl = QLabel(f"{icon} {txt}")
            lbl.setStyleSheet(f"color:{col};")
            t_lay.addWidget(lbl)
        thresh.setLayout(t_lay)
        thresh.setStyleSheet("border:2px solid #444; border-radius:8px; background:#1a1a2e;")
        bottom.addWidget(thresh)

        score = QGroupBox("Current Stability Score")
        s_lay = QVBoxLayout()
        self.bar = QProgressBar()
        self.bar.setRange(0,100)
        self.bar.setValue(78)
        self.bar.setStyleSheet("QProgressBar{background:#222;border:1px solid #444;color:white;} QProgressBar::chunk{background:#ffdd00;}")
        s_lay.addWidget(self.bar)
        s_lay.addWidget(QLabel("Stability Trend ="))
        score.setLayout(s_lay)
        score.setStyleSheet("border:2px solid #444; border-radius:8px; background:#1a1a2e;")
        bottom.addWidget(score)

        warn = QGroupBox("MAJOR EVENT WARNING 10 MIN")
        w_lay = QVBoxLayout()
        self.flash_lbl = QLabel("FLASH")
        self.flash_lbl.setStyleSheet("font-size:24px; color:#ff44ff; font-weight:bold;")
        w_lay.addWidget(self.flash_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        warn.setLayout(w_lay)
        warn.setStyleSheet("border:2px solid #ff44ff; border-radius:8px; background:rgba(255,68,255,0.1);")
        bottom.addWidget(warn)

        occ = QGroupBox("MAJOR EVENT OCCURRED")
        o_lay = QVBoxLayout()
        o_lay.addWidget(QLabel("BOUGHT/SOLD SHARES AMOUNT ="))
        btn = QPushButton("ENTER")
        btn.setStyleSheet("background:#ffdd00; color:black; font-weight:bold; padding:12px;")
        o_lay.addWidget(btn)
        occ.setLayout(o_lay)
        occ.setStyleSheet("border:2px solid #ff4444; border-radius:8px; background:#1a1a2e;")
        bottom.addWidget(occ)

        main_lay.addLayout(bottom)

        # Controls + status
        ctrl = QHBoxLayout()
        start_btn = QPushButton("START")
        start_btn.clicked.connect(self.start_engine)
        stop_btn = QPushButton("STOP & EXIT")
        stop_btn.clicked.connect(self.stop_and_exit)
        ctrl.addWidget(start_btn)
        ctrl.addWidget(stop_btn)
        main_lay.addLayout(ctrl)

        self.status = QLabel("Status: Ready")
        self.status.setStyleSheet("font-weight:bold; color:#88ff88; padding:8px;")
        main_lay.addWidget(self.status)

        self.engine = None

    def start_engine(self):
        if self.engine and self.engine.isRunning():
            return
        self.status.setText("CONNECTED - Live Stream Active")
        self.status.setStyleSheet("font-weight:bold; color:#00ff00; background:#1e3a1e; padding:8px; border-radius:6px;")
        self.engine = EngineThread(get_gold_contract())
        self.engine.log.connect(self.status.setText)
        self.engine.data.connect(self.update_ui)
        self.engine.start()

    def stop_and_exit(self):
        self.status.setText("STOPPING & EXITING...")
        self.status.setStyleSheet("font-weight:bold; color:#ff6666; background:#3a1e1e; padding:8px; border-radius:6px;")

        if self.engine:
            self.engine.stop()
            time.sleep(1.5)  # give time for termination
            self.engine.wait()

        self.status.setText("FULLY STOPPED & EXITING")
        QTimer.singleShot(1200, app.quit)

    def update_ui(self, d):
        if 'contract' in d:
            self.contract_lbl.setText(f"CONTRACT: {d['contract']}")
        if 'ts' in d:
            self.ts_lbl.setText(f"TIMESTAMP: {d['ts']}")
        if 'price' in d:
            self.price_lbl.setText(d['price'])
        if 'vol' in d:
            self.vol_lbl.setText(f"VOLUME: {d['vol']}")
        if 'signal' in d:
            color = "#00ff00" if d['signal'] == "BUY" else "#ff4444" if d['signal'] == "SELL" else "#ffdd00"
            self.sig.setText(d['signal'])
            self.sig.setStyleSheet(f"font-size:36px; font-weight:bold; color:{color};")
        if 'dir_val' in d:
            self.dir_val.setText(d['dir_val'])
            self.arrow.setText(d['dir_arrow'])
            color = "#00ff00" if d['dir_arrow'] == '↑' else "#ff4444" if d['dir_arrow'] == '↓' else "#ffdd00"
            self.arrow.setStyleSheet(f"font-size:60px; color:{color};")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("GESTALT", "Minimized to tray")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = GestaltDashboard()
    w.show()
    sys.exit(app.exec())
