#!/usr/bin/env python3
"""
Gestalt Signal Engine - Desktop GUI (Replacement for deleted main_gui.py)
Uses PyQt6 + threading to run realtime pipeline without blocking UI.
Shows live indicators, status, logs. Keeps WS server running.
"""

import sys
import os
import subprocess
import json
import asyncio
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QStatusBar
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QPalette

import websockets
from dotenv import load_dotenv

# Add project root to path so imports work
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))
os.chdir(project_root)

# Import your engine pieces - adjust if names changed
try:
    from orchestration.pipeline import PipelineOrchestrator  # main engine class
    from api.topstep import TopstepXDataProvider             # provider
except ImportError:
    # Fallback if imports differ - you may need to adjust these
    print("Warning: Could not import orchestration or api modules. GUI will run but pipeline may fail.")

load_dotenv()

class EngineRunner(QThread):
    """Runs the main pipeline in background thread"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    data_signal = pyqtSignal(dict)   # live feature/signal data

    def __init__(self, contract_id, mode="realtime", provider="topstepx"):
        super().__init__()
        self.contract_id = contract_id
        self.mode = mode
        self.provider = provider
        self.running = False
        self.process = None

    def run(self):
        self.running = True
        self.log_signal.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Starting engine thread...")

        try:
            # Option A: Spawn main.py as subprocess (easiest, reuses existing code)
            cmd = [
                sys.executable, "main.py",
                "--contract_id", self.contract_id,
                "--mode", self.mode,
                "--provider", self.provider,
                "--no-browser"   # prevent browser open if any
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
                if not self.running:
                    break
                clean_line = line.strip()
                if clean_line:
                    self.log_signal.emit(clean_line)

                    # Parse interesting lines for UI
                    if "Authentication successful" in clean_line:
                        self.status_signal.emit("🟢 Authenticated")
                    elif "Signal: BUY" in clean_line:
                        self.data_signal.emit({"signal": "BUY", "color": "green"})
                    elif "Signal: SELL" in clean_line:
                        self.data_signal.emit({"signal": "SELL", "color": "red"})
                    elif "phi_sigma=" in clean_line:
                        try:
                            phi = float(clean_line.split("phi_sigma=")[1].split(",")[0])
                            self.data_signal.emit({"phi_sigma": phi})
                        except:
                            pass

            self.process.wait()
        except Exception as e:
            self.log_signal.emit(f"Engine error: {str(e)}")
        finally:
            self.status_signal.emit("🔴 Stopped")

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()


class LiveWSMonitor(QThread):
    """Lightweight WS client to get latest data if needed"""
    data_signal = pyqtSignal(dict)

    def run(self):
        async def monitor():
            uri = "ws://localhost:8765/ws"
            while True:
                try:
                    async with websockets.connect(uri, ping_interval=10) as ws:
                        while True:
                            msg = await ws.recv()
                            try:
                                data = json.loads(msg)
                                self.data_signal.emit(data)
                            except:
                                pass
                except Exception as e:
                    await asyncio.sleep(2)  # reconnect delay

        asyncio.run(monitor())


class SignalGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestalt Signal Engine - Desktop GUI")
        self.setGeometry(200, 200, 1000, 700)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

        # Style
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 40))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        self.setPalette(palette)

        central = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header
        header = QLabel("Gestalt Real-Time Signal Engine")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Controls
        controls = QHBoxLayout()
        self.start_btn = QPushButton("START LIVE STREAM")
        self.start_btn.setFixedHeight(50)
        self.start_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self.toggle_engine)
        controls.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setFixedHeight(50)
        self.stop_btn.setStyleSheet("background-color: #c62828; color: white;")
        self.stop_btn.clicked.connect(self.stop_engine)
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.stop_btn)

        layout.addLayout(controls)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("🔴 Engine STOPPED")
        self.status_label.setStyleSheet("font-size: 14px; color: #ff9800;")
        status_layout.addWidget(self.status_label)

        self.signal_label = QLabel("Signal: —")
        self.signal_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        status_layout.addWidget(self.signal_label)

        self.phi_label = QLabel("Phi Sigma: —")
        status_layout.addWidget(self.phi_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Log viewer
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        self.log_view.setMaximumHeight(250)
        layout.addWidget(QLabel("Engine Logs:"))
        layout.addWidget(self.log_view)

        central.setLayout(layout)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Ready | Contract: CON.F.US.GCE.Z25 | Provider: TopstepX")

        # Engine runner
        self.engine = None

        # Timer for UI refresh
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)

        # Contract config (hardcoded for now - can make UI input later)
        self.contract_id = "CON.F.US.GCE.Z25"

    def toggle_engine(self):
        if self.engine is None or not self.engine.isRunning():
            self.start_engine()
        else:
            self.stop_engine()

    def start_engine(self):
        self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] Launching pipeline...")
        self.status_label.setText("🟡 Starting...")
        self.start_btn.setText("Running...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.engine = EngineRunner(
            contract_id=self.contract_id,
            mode="realtime",
            provider="topstepx"
        )
        self.engine.log_signal.connect(self.log_view.append)
        self.engine.status_signal.connect(self.status_label.setText)
        self.engine.data_signal.connect(self.update_data)
        self.engine.start()

        # Optional: start WS monitor if direct parsing from logs isn't enough
        # self.ws_monitor = LiveWSMonitor()
        # self.ws_monitor.data_signal.connect(self.update_data)
        # self.ws_monitor.start()

    def stop_engine(self):
        if self.engine:
            self.engine.stop()
            self.engine.wait(5000)
        self.status_label.setText("🔴 STOPPED")
        self.start_btn.setText("START LIVE STREAM")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log_view.append("Engine stopped.")

    def update_data(self, data):
        if "signal" in data:
            sig = data["signal"]
            color = data.get("color", "white")
            self.signal_label.setText(f"Signal: {sig}")
            self.signal_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
        if "phi_sigma" in data:
            self.phi_label.setText(f"Phi Sigma: {data['phi_sigma']:.4f}")

    def update_ui(self):
        # Can add more periodic checks here (e.g. port check)
        pass

    def closeEvent(self, event):
        self.stop_engine()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SignalGUI()
    window.show()
    sys.exit(app.exec())main_gui.py
