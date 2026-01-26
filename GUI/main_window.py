import sys
import PySide6
import pyqtgraph as pg
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
                             QGroupBox, QGridLayout, QMessageBox)
from PySide6.QtCore import Slot, Qt # <--- CHANGED
# Import the new View module
from .plotting import DashboardPlots


class TactileTestUI(QMainWindow):
    def __init__(self, coordinator):
        super().__init__()
        self.coord = coordinator
        self.setWindowTitle("Tactile Sensor Characterization Suite")
        self.resize(1200, 800)

        # --- DATA BUFFERS ---
        self.time_data = []
        self.force_data = []
        self.sensor_data = []

        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ================= LEFT COLUMN (CONTROLS) =================
        left_panel = QVBoxLayout()
        # noinspection PyUnresolvedReferences
        left_panel.setAlignment(Qt.AlignTop)

        left_container = QWidget()
        left_container.setLayout(left_panel)
        left_container.setFixedWidth(300)
        main_layout.addWidget(left_container)

        # 1. Status Display
        self.grp_status = QGroupBox("System Status")
        stat_layout = QVBoxLayout()

        self.lbl_status = QLabel("READY")
        # noinspection PyUnresolvedReferences
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: green; border: 1px solid gray; padding: 5px;")

        self.lbl_phase = QLabel("Phase: IDLE")
        self.lbl_phase.setStyleSheet("font-size: 14px; font-weight: bold; color: gray;")

        self.lbl_force = QLabel("Fz: 0.000 N")
        self.lbl_force.setStyleSheet("font-size: 20px; color: blue; font-weight: bold;")

        stat_layout.addWidget(self.lbl_status)
        stat_layout.addWidget(self.lbl_phase)
        stat_layout.addWidget(self.lbl_force)
        self.grp_status.setLayout(stat_layout)
        left_panel.addWidget(self.grp_status)

        # 2. Parameters
        self.grp_params = QGroupBox("Test Parameters")
        p_layout = QGridLayout()

        self.spin_depth = self._add_param(p_layout, "Max Depth (mm):", 2.0, 0, 0.1, 20.0)
        self.spin_speed = self._add_param(p_layout, "Speed (mm/s):", 0.5, 1, 0.01, 5.0)
        self.spin_hold = self._add_param(p_layout, "Peak Hold (s):", 1.0, 2, 0.0, 60.0)

        self.spin_cycles = QSpinBox()
        self.spin_cycles.setRange(1, 50)
        self.spin_cycles.setValue(3)
        p_layout.addWidget(QLabel("Cycles:"), 3, 0)
        p_layout.addWidget(self.spin_cycles, 3, 1)

        self.grp_params.setLayout(p_layout)
        left_panel.addWidget(self.grp_params)

        # 3. Control Buttons
        self.grp_ctrl = QGroupBox("Controls")
        c_layout = QVBoxLayout()

        self.btn_start = QPushButton("START TEST")
        self.btn_start.setFixedHeight(50)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        self.btn_start.clicked.connect(self.on_start)

        self.btn_stop = QPushButton("EMERGENCY STOP")
        self.btn_stop.setFixedHeight(50)
        self.btn_stop.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; font-size: 14px;")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)

        c_layout.addWidget(self.btn_start)
        c_layout.addWidget(self.btn_stop)
        self.grp_ctrl.setLayout(c_layout)
        left_panel.addWidget(self.grp_ctrl)

        # ================= RIGHT COLUMN (PLOTS) =================
        # REFACTOR: Usage of DashboardPlots
        self.plots = DashboardPlots()
        main_layout.addWidget(self.plots)

        # --- SIGNALS ---
        self.coord.sig_status.connect(self.update_status)
        self.coord.sig_progress.connect(self.update_progress)
        self.coord.sig_data.connect(self.update_data)
        self.coord.sig_finished.connect(self.on_finished)
        self.coord.sig_error.connect(self.on_error)

    @staticmethod
    def _add_param(layout, text, default, row, min_val, max_val):
        label = QLabel(text)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSingleStep(0.1)
        layout.addWidget(label, row, 0)
        layout.addWidget(spin, row, 1)
        return spin

    def reset_buffers(self):
        self.time_data = []
        self.force_data = []
        self.sensor_data = []

    def on_start(self):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.grp_params.setEnabled(False)

        self.reset_buffers()
        # REFACTOR: Clear the view
        self.plots.clear()

        params = {
            'depth': self.spin_depth.value(),
            'speed': self.spin_speed.value(),
            'hold_time': self.spin_hold.value(),
            'cycles': self.spin_cycles.value(),
            'step_size': 0.1
        }
        self.coord.start_experiment(params)

    def on_stop(self):
        self.coord.stop()
        self.lbl_status.setText("STOPPING...")

    @pyqtSlot(str)
    def update_status(self, msg):
        self.lbl_status.setText(msg)
        if "Finding Surface" in msg:
            self.lbl_status.setStyleSheet("color: orange; font-weight: bold; border: 1px solid orange;")
        else:
            self.lbl_status.setStyleSheet("color: blue; border: 1px solid blue;")

    @pyqtSlot(int)
    def update_progress(self, val):
        pass

    @pyqtSlot(str)
    def on_error(self, err_msg):
        self.lbl_status.setText("ERROR")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold; border: 2px solid red;")
        QMessageBox.critical(self, "Experiment Error", err_msg)
        self.on_finished()

    @pyqtSlot()
    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.grp_params.setEnabled(True)
        self.lbl_status.setText("FINISHED")
        self.lbl_status.setStyleSheet("color: green; font-weight: bold; border: 2px solid green;")
        self.lbl_phase.setText("Phase: IDLE")

    @pyqtSlot(dict)
    def update_data(self, d):
        t = d['Time']
        f = d['Force']
        phase = d['Phase']
        s_vals = d['Sensor']

        # 1. Update Labels
        self.lbl_force.setText(f"Fz: {f:.3f} N")
        self.lbl_phase.setText(f"Phase: {phase}")

        # 2. Append Data locally
        self.time_data.append(t)
        self.force_data.append(f)

        # Initialize sensor lists on first packet
        if not self.sensor_data:
            self.sensor_data = [[] for _ in s_vals]
            # REFACTOR: Initialize curves in View
            # We assume s_vals corresponds to channels 0...N
            col_names = [f"Ch {i}" for i in range(len(s_vals))]
            self.plots.init_sensor_curves(len(s_vals), col_names)

        for i, val in enumerate(s_vals):
            if i < len(self.sensor_data):
                self.sensor_data[i].append(val)

        # 3. Update Plots (View)
        self.plots.update_plots(self.time_data, self.force_data, self.sensor_data)