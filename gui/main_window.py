import json
import threading

import numpy as np
from PySide6.QtCore import Slot, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
                               QGroupBox, QGridLayout, QMessageBox, QTextEdit, QProgressBar,
                               QCheckBox, QAbstractSpinBox, QComboBox, QScrollArea, QFrame,
                               QGraphicsDropShadowEffect, QSizePolicy, QToolButton)

from core import hardware_config as hwcfg
from interfaces.load_cell import ILoadCell
from interfaces.motion_stage import IMotionStage
from interfaces.tactile_sensor import ITactileSensor
from .plotting import DashboardPlots


class TactileTestUI(QMainWindow):
    def __init__(self, coordinator):
        super().__init__()
        self.coord = coordinator
        self.setWindowTitle("Tactile Sensor Suite v11.0")
        self.resize(1280, 950)
        self.setWindowState(Qt.WindowMaximized)

        self.time_data, self.force_data, self.sensor_data = [], [], []
        self.is_searching = False
        self._buffer_rate_hz = 0.0
        self._max_points = 0
        self._trim_threshold = 0
        self._hardware_cfg = hwcfg.load_config()
        self._active_hw_snapshot = None
        self._checking_connections = False
        self._check_thread = None
        self._conn_timeout_ms = 8000

        # UI Timer: Fixed at 20Hz for stable visuals without starving the sampler
        # This is decoupled from the Logging Rate (50Hz-100Hz)
        self.ui_timer = QTimer()
        self.ui_timer.setTimerType(Qt.PreciseTimer)
        self.ui_timer.timeout.connect(self.refresh_ui)
        self.ui_timer.start(50)

        # --- CSS (Kept from previous iteration) ---
        self.setStyleSheet("""
            QMainWindow { background-color: #F8FBFF; }
            QWidget { font-family: 'Segoe UI', sans-serif; font-size: 10pt; color: #1F2A36; }
            #central { background-color: #F8FBFF; }
            #sidebar { background-color: #F8FBFF; }
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,230), stop:1 rgba(245,250,255,200));
                border: 1px solid rgba(255,255,255,220);
                border-radius: 14px;
                margin-top: 16px;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 2px 8px;
                color: #1E2A36;
                font-weight: 600;
                font-size: 10pt;
                background: rgba(255,255,255,220);
                border: 1px solid rgba(255,255,255,240);
                border-radius: 8px;
            }
            QLabel { color: #1F2A36; }
            QDoubleSpinBox, QSpinBox { min-height: 34px; padding-left: 8px; border: 1px solid #B0BEC5; border-radius: 6px; background: rgba(255,255,255,230); }
            QDoubleSpinBox::up-button, QSpinBox::up-button { width: 34px; border-left: 1px solid #BDC3C7; background: #D6EAF8; }
            QDoubleSpinBox::down-button, QSpinBox::down-button { width: 34px; border-left: 1px solid #BDC3C7; background: #FADBD8; }
            QComboBox { min-height: 34px; padding-left: 8px; border: 1px solid #B0BEC5; border-radius: 6px; background: rgba(255,255,255,230); color: #1E272E; }
            QComboBox::drop-down { width: 30px; border-left: 1px solid #B0BEC5; background: #D6EAF8; }
            QComboBox QAbstractItemView { background: rgba(255,255,255,245); color: #1E272E; selection-background-color: #CFE3F5; selection-color: #1E272E; }
            QComboBox[required="true"] { border: 2px solid #E67E22; background: rgba(255,245,238,230); }
            QTextEdit { background-color: rgba(255,255,255,230); border: 1px solid rgba(200,215,230,200); border-radius: 6px; font-family: Consolas; font-size: 9pt; }
            QPushButton { border-radius: 6px; min-height: 40px; font-weight: 600; border: 1px solid #BDC3C7; background-color: #ECF0F1; color: #2C3E50; }
            QPushButton#btn_primary { background-color: #2980B9; color: white; border: none; }
            QPushButton#btn_success { background-color: #27AE60; color: white; border: none; }
            QPushButton#btn_danger { background-color: #C0392B; color: white; border: none; }
            QPushButton#btn_warn { background-color: #F39C12; color: white; border: none; }
            QPushButton#btn_disabled { background-color: #BDC3C7; color: #7F8C8D; border: none; }
            QPushButton:hover { background-color: #E1EDF7; }
            QPushButton:pressed { background-color: #CFE3F5; }
            QPushButton#btn_primary:pressed { background-color: #1F6FA0; }
            QPushButton#btn_success:pressed { background-color: #1F8A4D; }
            QPushButton#btn_danger:pressed { background-color: #A93226; }
            QPushButton#btn_warn:pressed { background-color: #D68910; }
            QPushButton[flash="ok"] { background-color: #2ECC71; color: #FFFFFF; }
            QPushButton[flash="warn"] { background-color: #F39C12; color: #FFFFFF; }
            QPushButton[flash="info"] { background-color: #3498DB; color: #FFFFFF; }
            QToolButton { border: 1px solid rgba(180,195,210,160); border-radius: 6px; padding: 1px; background: rgba(255,255,255,200); color: #2980B9; }
            QToolButton:hover { background: rgba(230,240,250,220); }
            QToolButton:pressed { background: rgba(210,225,240,220); }
            QMessageBox { background-color: #F8FBFF; color: #1F2A36; }
            QMessageBox QLabel { color: #1F2A36; }
            QMessageBox QPushButton { background-color: #ECF0F1; color: #2C3E50; }
            QScrollArea { border: none; background: #F8FBFF; }
            QScrollArea::viewport { background: #F8FBFF; }
            QScrollArea > QWidget { background: #F8FBFF; }
            QAbstractScrollArea::corner { background: #F8FBFF; }
            QScrollBar:vertical { width: 10px; background: rgba(230,238,246,180); margin: 2px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #B5C6D6; min-height: 20px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #9FB3C7; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # --- SIDEBAR ---
        left_panel = QWidget()
        left_panel.setFixedWidth(400)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        scroll_content = QWidget()
        scroll_content.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(scroll_content)
        sidebar_layout.setContentsMargins(10, 6, 10, 10)
        sidebar_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setWidget(scroll_content)
        scroll.setFixedWidth(400)
        left_layout.addWidget(scroll, stretch=1)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 0, 10, 10)
        footer_layout.setSpacing(8)
        left_layout.addWidget(footer, stretch=0)

        main_layout.addWidget(left_panel)

        # 0. HARDWARE
        self.grp_hw, l_hw, self.lbl_hw_summary, self.hw_content, self.hw_toggle = self._create_section("Hardware",
                                                                                                       QVBoxLayout)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Simulation", "sim")
        self.cmb_mode.addItem("Auto Detect", "auto")
        self.cmb_mode.addItem("Manual", "manual")
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        self._cap_combo_width(self.cmb_mode)
        mode_row.addWidget(self.cmb_mode)
        l_hw.addLayout(mode_row)

        self.lbl_sim_info = QLabel("Simulation mode: mock drivers only.")
        self.lbl_sim_info.setWordWrap(True)
        l_hw.addWidget(self.lbl_sim_info)

        self.auto_panel = QGroupBox("Auto Detect")
        auto_layout = QGridLayout(self.auto_panel)
        auto_layout.setVerticalSpacing(6)
        auto_layout.setColumnStretch(1, 1)
        self.lbl_auto_stage = QLabel("-")
        self.lbl_auto_load_cell = QLabel("-")
        self.lbl_auto_sensor = QLabel("-")
        self.lbl_auto_status = QLabel("")
        self.lbl_auto_status.setWordWrap(True)
        self.badge_auto_stage = self._make_status_badge()
        self.badge_auto_load_cell = self._make_status_badge()
        self.badge_auto_sensor = self._make_status_badge()
        auto_layout.addWidget(QLabel("Detected Stage:"), 0, 0)
        auto_layout.addWidget(self.lbl_auto_stage, 0, 1)
        auto_layout.addWidget(self.badge_auto_stage, 0, 2)
        auto_layout.addWidget(QLabel("Detected Load Cell:"), 1, 0)
        auto_layout.addWidget(self.lbl_auto_load_cell, 1, 1)
        auto_layout.addWidget(self.badge_auto_load_cell, 1, 2)
        auto_layout.addWidget(QLabel("Detected Sensor:"), 2, 0)
        auto_layout.addWidget(self.lbl_auto_sensor, 2, 1)
        auto_layout.addWidget(self.badge_auto_sensor, 2, 2)
        self.btn_auto_rescan = QPushButton("Rescan")
        self.btn_auto_rescan.clicked.connect(lambda: self._run_auto_detect())
        auto_layout.addWidget(self.btn_auto_rescan, 3, 0)
        auto_layout.addWidget(self.lbl_auto_status, 3, 1, 1, 2)
        l_hw.addWidget(self.auto_panel)

        self.test_type_panel = QGroupBox("Test Selection")
        test_type_layout = QGridLayout(self.test_type_panel)
        test_type_layout.setVerticalSpacing(6)
        test_type_layout.setColumnStretch(1, 1)
        self.cmb_test_type = QComboBox()
        self.cmb_test_type.addItem("Uniaxial Test", "Uni")
        self.cmb_test_type.addItem("Triaxial Test", "Tri")
        self._cap_combo_width(self.cmb_test_type)
        self.cmb_test_type.currentIndexChanged.connect(self._on_test_type_changed)
        test_type_layout.addWidget(QLabel("Test Type:"), 0, 0)
        test_type_layout.addWidget(self.cmb_test_type, 0, 1)
        l_hw.addWidget(self.test_type_panel)

        self.manual_panel = QGroupBox("Manual Selection")
        manual_layout = QGridLayout(self.manual_panel)
        manual_layout.setVerticalSpacing(6)
        manual_layout.setColumnStretch(1, 1)
        self.cmb_stage_driver = QComboBox()
        self.cmb_load_cell_driver = QComboBox()
        self.cmb_sensor_driver = QComboBox()
        self._cap_combo_width(self.cmb_stage_driver)
        self._cap_combo_width(self.cmb_load_cell_driver)
        self._cap_combo_width(self.cmb_sensor_driver)
        self.badge_stage = self._make_status_badge()
        self.badge_load_cell = self._make_status_badge()
        self.badge_sensor = self._make_status_badge()
        manual_layout.addWidget(QLabel("Stage Driver:"), 0, 0)
        manual_layout.addWidget(self.cmb_stage_driver, 0, 1)
        manual_layout.addWidget(self.badge_stage, 0, 2)
        manual_layout.addWidget(QLabel("Load Cell Driver:"), 1, 0)
        manual_layout.addWidget(self.cmb_load_cell_driver, 1, 1)
        manual_layout.addWidget(self.badge_load_cell, 1, 2)
        manual_layout.addWidget(QLabel("Sensor Driver:"), 2, 0)
        manual_layout.addWidget(self.cmb_sensor_driver, 2, 1)
        manual_layout.addWidget(self.badge_sensor, 2, 2)
        l_hw.addWidget(self.manual_panel)

        self.sensor_panel = QGroupBox("Sensor Connection")
        sensor_layout = QGridLayout(self.sensor_panel)
        sensor_layout.setVerticalSpacing(6)
        sensor_layout.setColumnStretch(1, 1)
        self.cmb_sensor_port = QComboBox()
        self.cmb_sensor_port.setEditable(True)
        self._cap_combo_width(self.cmb_sensor_port)
        sensor_layout.addWidget(QLabel("Sensor Port:"), 0, 0)
        sensor_layout.addWidget(self.cmb_sensor_port, 0, 1)
        self.cmb_sensor_baud = QComboBox()
        self.cmb_sensor_baud.setEditable(True)
        self._cap_combo_width(self.cmb_sensor_baud)
        for rate in [9600, 19200, 38400, 57600, 115200, 12800, 230400, 460800, 921600]:
            self.cmb_sensor_baud.addItem(str(rate))
        sensor_layout.addWidget(QLabel("Sensor Baud:"), 1, 0)
        sensor_layout.addWidget(self.cmb_sensor_baud, 1, 1)
        self.btn_port_refresh = QPushButton("Scan Ports")
        self.btn_port_refresh.clicked.connect(lambda: self._refresh_serial_ports())
        sensor_layout.addWidget(self.btn_port_refresh, 2, 0)
        self.btn_port_suggest = QPushButton("Suggest Port")
        self.btn_port_suggest.clicked.connect(lambda: self._suggest_serial_port())
        sensor_layout.addWidget(self.btn_port_suggest, 2, 1)
        l_hw.addWidget(self.sensor_panel)

        self.cmb_stage_driver.currentIndexChanged.connect(self._update_hw_summary)
        self.cmb_load_cell_driver.currentIndexChanged.connect(self._update_hw_summary)
        self.cmb_sensor_driver.currentIndexChanged.connect(self._update_hw_summary)
        self.cmb_sensor_port.currentTextChanged.connect(self._update_hw_summary)
        self.cmb_sensor_baud.currentTextChanged.connect(self._update_hw_summary)
        self.cmb_stage_driver.currentIndexChanged.connect(self._update_required_highlights)
        self.cmb_load_cell_driver.currentIndexChanged.connect(self._update_required_highlights)
        self.cmb_sensor_driver.currentIndexChanged.connect(self._update_required_highlights)
        self.cmb_sensor_port.currentTextChanged.connect(self._update_required_highlights)
        self.cmb_sensor_baud.currentTextChanged.connect(self._update_required_highlights)

        self.btn_hw_save = QPushButton("Save Hardware Config")
        self.btn_hw_save.setObjectName("btn_primary")
        self.btn_hw_save.clicked.connect(lambda: self._save_hardware_config())
        l_hw.addWidget(self.btn_hw_save)

        self.lbl_hw_note = QLabel("Saved defaults apply on next launch.")
        self.lbl_hw_note.setWordWrap(True)
        l_hw.addWidget(self.lbl_hw_note)

        self.btn_check = QPushButton("Apply and Check Connections")
        self.btn_check.setObjectName("btn_primary")
        self.btn_check.clicked.connect(lambda: self._check_connections())
        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setMaximumHeight(70)
        l_hw.addWidget(self.btn_check)
        l_hw.addWidget(self.txt_report)

        sidebar_layout.addWidget(self.grp_hw)

        # 1. PARAMETERS
        self.grp_phys, l_phys, self.lbl_exp_summary, self.exp_content, self.exp_toggle = self._create_section(
            "Experiment", QGridLayout)
        l_phys.setVerticalSpacing(10)

        self.spin_depth = self._add_p(l_phys, "Depth (mm):", 2.0, 0, 0.0, 20.0)
        self.spin_speed = self._add_p(l_phys, "Speed (mm/s):", 0.2, 1, 0.01, 5.0)
        self.spin_hold = self._add_p(l_phys, "Hold (s):", 1.0, 2, 0.0, 60.0)
        self.spin_contact = self._add_p(l_phys, "Contact (N):", 0.4, 3, 0.01, 10.0)

        # New: Sampling Rate
        self.spin_rate = QSpinBox()
        self.spin_rate.setRange(1, 200)
        self.spin_rate.setValue(50)  # Default 50Hz
        self.spin_rate.setButtonSymbols(QAbstractSpinBox.PlusMinus)
        self.spin_rate.valueChanged.connect(self._recalc_buffer_limits)
        l_phys.addWidget(QLabel("Logging Rate (Hz):"), 4, 0)
        l_phys.addWidget(self.spin_rate, 4, 1)

        self.spin_cycles = QSpinBox()
        self.spin_cycles.setValue(5)
        self.spin_cycles.setRange(1, 100)
        self.spin_cycles.setButtonSymbols(QAbstractSpinBox.PlusMinus)
        l_phys.addWidget(QLabel("Cycles:"), 5, 0)
        l_phys.addWidget(self.spin_cycles, 5, 1)
        self.spin_depth.valueChanged.connect(self._update_exp_summary)
        self.spin_speed.valueChanged.connect(self._update_exp_summary)
        self.spin_hold.valueChanged.connect(self._update_exp_summary)
        self.spin_contact.valueChanged.connect(self._update_exp_summary)
        self.spin_rate.valueChanged.connect(self._update_exp_summary)
        self.spin_cycles.valueChanged.connect(self._update_exp_summary)
        sidebar_layout.addWidget(self.grp_phys)

        # 2. LOGGING
        self.grp_log, l_log, self.lbl_log_summary, self.log_content, self.log_toggle = self._create_section("Logging",
                                                                                                            QGridLayout)
        self.chk_csv = QCheckBox("CSV")
        self.chk_csv.setChecked(True)
        self.chk_sqlite = QCheckBox("SQLite")
        self.chk_sqlite.setChecked(False)
        l_log.addWidget(self.chk_csv, 0, 0)
        l_log.addWidget(self.chk_sqlite, 0, 1)
        self.chk_csv.stateChanged.connect(self._update_log_summary)
        self.chk_sqlite.stateChanged.connect(self._update_log_summary)
        sidebar_layout.addWidget(self.grp_log)

        # 3. VIEW
        self.grp_ui, l_ui, self.lbl_view_summary, self.view_content, self.view_toggle = self._create_section("View",
                                                                                                             QGridLayout)
        self.spin_window = QSpinBox()
        self.spin_window.setRange(5, 300)
        self.spin_window.setValue(10)
        self.spin_window.setButtonSymbols(QAbstractSpinBox.PlusMinus)
        self.spin_window.valueChanged.connect(self._recalc_buffer_limits)
        l_ui.addWidget(QLabel("Window (s):"), 0, 0)
        l_ui.addWidget(self.spin_window, 0, 1)
        self.spin_window.valueChanged.connect(self._update_view_summary)
        sidebar_layout.addWidget(self.grp_ui)

        # 4. MONITOR
        self.grp_status = QGroupBox("Status")
        l_stat = QGridLayout(self.grp_status)

        self.lbl_phase = QLabel("-")
        self.lbl_cycle = QLabel("0 / 0")
        self.lbl_time = QLabel("0s / 0s")

        def s(l):
            l.setStyleSheet("font-weight: bold; color: #2980B9;")

        s(self.lbl_phase)
        s(self.lbl_cycle)
        s(self.lbl_time)

        l_stat.addWidget(QLabel("Phase:"), 0, 0)
        l_stat.addWidget(self.lbl_phase, 0, 1)
        l_stat.addWidget(QLabel("Cycle:"), 1, 0)
        l_stat.addWidget(self.lbl_cycle, 1, 1)
        l_stat.addWidget(QLabel("Time:"), 2, 0)
        l_stat.addWidget(self.lbl_time, 2, 1)
        self.lbl_surface = QLabel("-")
        l_stat.addWidget(QLabel("Surface:"), 3, 0)
        l_stat.addWidget(self.lbl_surface, 3, 1)

        self.progress = QProgressBar()
        self.progress.setStyleSheet(
            "QProgressBar { height: 8px; border-radius: 4px; background: #BDC3C7; } QProgressBar::chunk { background: #2980B9; }")
        l_stat.addWidget(self.progress, 4, 0, 1, 2)
        sidebar_layout.addStretch()

        for grp in (self.grp_hw, self.auto_panel, self.manual_panel, self.sensor_panel,
                    self.grp_phys, self.grp_log, self.grp_ui, self.grp_status):
            self._apply_glass_effect(grp)

        # CONTROLS (Always visible)
        self.btn_start = QPushButton("START TEST")
        self.btn_start.setObjectName("btn_success")
        self.btn_start.clicked.connect(self.on_start_click)

        self.btn_stop = QPushButton("EMERGENCY STOP")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.clicked.connect(self.on_stop)

        footer_layout.addWidget(self.grp_status)
        footer_layout.addWidget(self.btn_start)
        footer_layout.addWidget(self.btn_stop)

        # --- RIGHT PLOTS ---
        self.plots = DashboardPlots()
        main_layout.addWidget(self.plots, stretch=1)

        # SIGNALS
        self.coord.sig_hw_info.connect(self.update_report)
        self.coord.sig_packet.connect(self.ingest_packet)
        self.coord.sig_finished.connect(self.on_finished)
        self.coord.sig_status.connect(self._on_status)
        self.coord.sig_error.connect(self._on_error)

        # Populate hardware UI from config
        self._load_hardware_ui()
        self._update_exp_summary()
        self._update_log_summary()
        self._update_view_summary()

    def _add_p(self, layout, text, val, row, min_v, max_v):
        layout.addWidget(QLabel(text), row, 0)
        s = QDoubleSpinBox()
        s.setRange(min_v, max_v)
        s.setSingleStep(0.1)
        s.setValue(val)
        s.setButtonSymbols(QAbstractSpinBox.PlusMinus)
        layout.addWidget(s, row, 1)
        return s

    def _cap_combo_width(self, combo, min_w=170, max_w=230):
        combo.setMinimumWidth(min_w)
        combo.setMaximumWidth(max_w)
        combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        view = combo.view()
        if view is not None:
            view.setMinimumWidth(max_w)
            view.setMaximumWidth(max_w)

    def _apply_glass_effect(self, widget):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(20)
        effect.setOffset(0, 6)
        effect.setColor(QColor(15, 20, 25, 40))
        widget.setGraphicsEffect(effect)

    def _create_section(self, title, content_layout_cls):
        grp = QGroupBox(title)
        outer = QVBoxLayout(grp)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        summary = QLabel("")
        summary.setStyleSheet("color: #5D6D7E; font-size: 9pt;")
        summary.setVisible(False)
        header_layout.addWidget(summary)
        header_layout.addStretch()
        toggle = QToolButton()
        toggle.setArrowType(Qt.DownArrow)
        toggle.setFixedSize(16, 16)
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.setAutoRaise(True)
        header_layout.addWidget(toggle)
        outer.addWidget(header)
        content = QWidget()
        content_layout = content_layout_cls(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(content)

        def _toggle():
            collapsed = content.isVisible()
            self._set_section_collapsed(content, summary, toggle, collapsed)

        toggle.clicked.connect(_toggle)
        return grp, content_layout, summary, content, toggle

    def _set_section_collapsed(self, content, summary, toggle, collapsed):
        content.setVisible(not collapsed)
        summary.setVisible(collapsed)
        toggle.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)

    def _make_status_badge(self):
        badge = QLabel()
        badge.setFixedSize(10, 10)
        badge.setStyleSheet("border-radius: 5px; background: #BDC3C7;")
        return badge

    def _set_badge(self, badge, status):
        colors = {
            "ok": "#27AE60",
            "warn": "#F39C12",
            "err": "#C0392B",
            "off": "#BDC3C7"
        }
        badge.setStyleSheet(f"border-radius: 5px; background: {colors.get(status, '#BDC3C7')};")

    def _flash_button(self, button, status="info", msec=350):
        if button is None:
            return
        button.setProperty("flash", status)
        button.style().unpolish(button)
        button.style().polish(button)
        QTimer.singleShot(msec, lambda: self._clear_flash(button))

    def _clear_flash(self, button):
        if button is None:
            return
        button.setProperty("flash", "")
        button.style().unpolish(button)
        button.style().polish(button)

    def _show_message(self, title, text, icon):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(icon)
        box.setText(text)
        box.setStandardButtons(QMessageBox.Ok)
        box.setMinimumSize(420, 200)
        box.exec()

    def _set_required(self, widget, required):
        widget.setProperty("required", "true" if required else "false")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _update_required_highlights(self, enforce=False):
        mode = self._current_mode()
        ok = True

        def mark(widget, good):
            self._set_required(widget, not good)

        if mode == "manual":
            stage_ok = bool(self.cmb_stage_driver.currentData())
            load_ok = bool(self.cmb_load_cell_driver.currentData())
            sensor_ok = bool(self.cmb_sensor_driver.currentData())
            port_ok = bool(self.cmb_sensor_port.currentText().strip())
            baud_ok = bool(self.cmb_sensor_baud.currentText().strip())
            mark(self.cmb_stage_driver, stage_ok)
            mark(self.cmb_load_cell_driver, load_ok)
            mark(self.cmb_sensor_driver, sensor_ok)
            mark(self.cmb_sensor_port, port_ok)
            mark(self.cmb_sensor_baud, baud_ok)
            ok = stage_ok and load_ok and sensor_ok and port_ok and baud_ok
        elif mode == "auto":
            port_ok = bool(self.cmb_sensor_port.currentText().strip())
            baud_ok = bool(self.cmb_sensor_baud.currentText().strip())
            mark(self.cmb_sensor_port, port_ok)
            mark(self.cmb_sensor_baud, baud_ok)
            for widget in (self.cmb_stage_driver, self.cmb_load_cell_driver, self.cmb_sensor_driver):
                self._set_required(widget, False)
        else:
            for widget in (self.cmb_stage_driver, self.cmb_load_cell_driver, self.cmb_sensor_driver,
                           self.cmb_sensor_port, self.cmb_sensor_baud):
                self._set_required(widget, False)

        return ok if enforce else True

    def _update_hw_summary(self):
        mode = self._current_mode()
        if mode == "sim":
            summary = "Simulation (Mock drivers)"
        elif mode == "auto":
            stage = self.lbl_auto_stage.text().strip()
            load = self.lbl_auto_load_cell.text().strip()
            sensor = self.lbl_auto_sensor.text().strip()
            detected = 0
            for val in (stage, load, sensor):
                if val and val not in {"-", "Not detected"}:
                    detected += 1
            summary = f"Auto ({detected} detected)"
        else:
            selected = 0
            if self.cmb_stage_driver.currentData():
                selected += 1
            if self.cmb_load_cell_driver.currentData():
                selected += 1
            if self.cmb_sensor_driver.currentData():
                selected += 1
            summary = f"Manual ({selected} selected)"
        self.lbl_hw_summary.setText(summary)
        self._refresh_hw_badges()

    def _refresh_hw_badges(self):
        mode = self._current_mode()
        if mode == "manual":
            self._set_badge(self.badge_auto_stage, "off")
            self._set_badge(self.badge_auto_load_cell, "off")
            self._set_badge(self.badge_auto_sensor, "off")
            stage_sel = bool(self.cmb_stage_driver.currentData())
            load_sel = bool(self.cmb_load_cell_driver.currentData())
            sensor_sel = bool(self.cmb_sensor_driver.currentData())
            self._set_badge(self.badge_stage, "warn" if stage_sel else "err")
            self._set_badge(self.badge_load_cell, "warn" if load_sel else "err")
            self._set_badge(self.badge_sensor, "warn" if sensor_sel else "err")
        elif mode == "auto":
            self._set_badge(self.badge_stage, "off")
            self._set_badge(self.badge_load_cell, "off")
            self._set_badge(self.badge_sensor, "off")
            stage_ok = self.lbl_auto_stage.text().strip() not in {"-", "Not detected", ""}
            load_ok = self.lbl_auto_load_cell.text().strip() not in {"-", "Not detected", ""}
            sensor_ok = self.lbl_auto_sensor.text().strip() not in {"-", "Not detected", ""}
            self._set_badge(self.badge_auto_stage, "ok" if stage_ok else "err")
            self._set_badge(self.badge_auto_load_cell, "ok" if load_ok else "err")
            self._set_badge(self.badge_auto_sensor, "ok" if sensor_ok else "err")
        else:
            for badge in (self.badge_stage, self.badge_load_cell, self.badge_sensor,
                          self.badge_auto_stage, self.badge_auto_load_cell, self.badge_auto_sensor):
                self._set_badge(badge, "off")

    def _update_exp_summary(self):
        summary = (
            f"Depth {self.spin_depth.value():.2f} mm, "
            f"Speed {self.spin_speed.value():.2f} mm/s, "
            f"Cycles {self.spin_cycles.value()}, "
            f"Rate {self.spin_rate.value()} Hz"
        )
        self.lbl_exp_summary.setText(summary)

    def _update_log_summary(self):
        parts = []
        if self.chk_csv.isChecked():
            parts.append("CSV")
        if self.chk_sqlite.isChecked():
            parts.append("SQLite")
        self.lbl_log_summary.setText(" + ".join(parts) if parts else "Logging off")

    def _update_view_summary(self):
        self.lbl_view_summary.setText(f"Window {self.spin_window.value()} s")

    def _set_connection_help(self, err):
        msg = [
            "Connection error:",
            str(err).strip(),
            "",
            "Try:",
            "- Verify the selected drivers for stage/load cell/sensor.",
            "- Check hardware power and cable connections.",
            "- For serial sensors: Scan Ports and confirm COM + baud.",
            "- Try Auto Detect or Simulation if hardware is unavailable."
        ]
        self.txt_report.setText("\n".join(msg))

    def _recalc_buffer_limits(self):
        rate = self._buffer_rate_hz or self.spin_rate.value() or 1
        window = self.spin_window.value()
        self._max_points = max(1, int(rate * window * 1.1))
        self._trim_threshold = int(self._max_points * 1.2)
        self._trim_buffers()

    def _trim_buffers(self):
        if self._max_points <= 0:
            return
        if len(self.time_data) <= self._trim_threshold:
            return
        self.time_data = self.time_data[-self._max_points:]
        self.force_data = self.force_data[-self._max_points:]
        if self.sensor_data:
            self.sensor_data = [c[-self._max_points:] for c in self.sensor_data]

    @Slot(dict)
    def ingest_packet(self, d):
        """Called whenever data arrives from the high-speed thread."""
        self.time_data.append(d['t'])
        self.force_data.append(d['f'])
        if not self.sensor_data:
            self.sensor_data = [[] for _ in d['s']]
            self.plots.init_sensor_curves(len(d['s']), d.get('s_names'))
        for i, v in enumerate(d['s']):
            self.sensor_data[i].append(v)
        self._trim_buffers()

        # CLEAN PHASE DISPLAY: "CYCLE_1_LOADING" -> "LOADING"
        raw_phase = d['phase']
        if "LOADING" in raw_phase:
            clean_phase = "LOADING"
        elif "UNLOADING" in raw_phase:
            clean_phase = "UNLOADING"
        elif "HOLDING" in raw_phase:
            clean_phase = "HOLDING"
        elif "MULLIN" in raw_phase:
            clean_phase = "PRE-CONDITIONING"
        else:
            clean_phase = raw_phase
        self.lbl_phase.setText(clean_phase)
        if "MULLIN" in raw_phase or "CYCLE" in raw_phase:
            self.lbl_surface.setText("-")

        # CYCLE DISPLAY: 0/5 for Mullin, 1/5...
        current_cycle = d['cycle']
        total_test_cycles = d['total_cycles'] - 1  # Subtract Mullin for display

        if current_cycle == 0:
            display_cycle = f"0 (Mullin) / {total_test_cycles}"
        else:
            display_cycle = f"{current_cycle} / {total_test_cycles}"
        self.lbl_cycle.setText(display_cycle)

        # TIME & PROGRESS
        elapsed = d['t']
        expected = d['expected_duration']
        self.lbl_time.setText(f"{elapsed:.1f}s / ~{expected:.1f}s")
        if expected > 0:
            self.progress.setValue(min(100, int((elapsed / expected) * 100)))

        # BUTTON STATE
        if self.is_searching and ("MULLIN" in raw_phase or "CYCLE" in raw_phase):
            self.is_searching = False
            self.btn_start.setText("RUNNING...")
            self.btn_start.setEnabled(False)
            self.btn_start.setObjectName("btn_disabled")
            self.btn_start.style().unpolish(self.btn_start)
            self.btn_start.style().polish(self.btn_start)

        if self.progress.maximum() != 100:
            self.progress.setRange(0, 100)

    def refresh_ui(self):
        """Visual update loop (20Hz) - Decoupled from logging"""
        if not self.time_data:
            return

        win = self.spin_window.value()
        t_end = self.time_data[-1]
        t_start = max(0, t_end - win)
        idx = np.searchsorted(self.time_data, t_start)

        self.plots.update_plots(
            self.time_data[idx:],
            self.force_data[idx:],
            [c[idx:] for c in self.sensor_data]
        )
        self.plots.set_x_range(t_start, t_start + win)

    def on_start_click(self):
        if not self.is_searching:
            if not self._apply_hardware_for_session(show_message=False):
                return
            self.is_searching = True
            self.btn_start.setText("SET SURFACE NOW")
            self.btn_start.setObjectName("btn_warn")
            self.btn_start.setEnabled(True)
            self.btn_start.style().unpolish(self.btn_start)
            self.btn_start.style().polish(self.btn_start)
            self.lbl_phase.setText("FINDING SURFACE...")
            self.lbl_surface.setText("Searching...")
            self.progress.setRange(0, 0)
            self._flash_button(self.btn_start, "info")
            self._set_section_collapsed(self.hw_content, self.lbl_hw_summary, self.hw_toggle, True)
            self._set_section_collapsed(self.exp_content, self.lbl_exp_summary, self.exp_toggle, True)
            self._set_section_collapsed(self.log_content, self.lbl_log_summary, self.log_toggle, True)
            self._set_section_collapsed(self.view_content, self.lbl_view_summary, self.view_toggle, True)

            self.time_data, self.force_data, self.sensor_data = [], [], []
            self.plots.clear()
            self._buffer_rate_hz = self.spin_rate.value()
            self._recalc_buffer_limits()

            params = {
                'depth': self.spin_depth.value(),
                'speed': self.spin_speed.value(),
                'hold_time': self.spin_hold.value(),
                'cycles': self.spin_cycles.value(),
                'contact_force': self.spin_contact.value(),
                'sampling_rate': self.spin_rate.value(),  # Pass User Rate
                'log_csv': self.chk_csv.isChecked(),
                'log_sqlite': self.chk_sqlite.isChecked()
            }
            test_type = self._on_test_type_changed()
            if test_type == "Uni":
                self.coord.start_experiment(params)
            elif test_type == "Tri":
                self.coord.start_triaxial_experiment(params) # to be added in backend
        else:
            self.coord.trigger_manual_surface()
            self._flash_button(self.btn_start, "ok")
            self.lbl_surface.setText("Manual trigger")

    def on_stop(self):
        is_complete = self.coord.stop()
        self.lbl_phase.setText("STOPPING...")
        self.progress.setRange(0, 0)
        self._flash_button(self.btn_stop, "warn")
        if is_complete:
            try:
                self.lbl_phase.setText("STOPPED")
                self.progress.setRange(0, 100)
                self.progress.setValue(100)
                self._show_message("Stopped", "Please restart the program.", QMessageBox.Information)
            except Exception:
                pass
    @Slot(dict)
    def update_report(self, info):
        self.txt_report.setText(
            f"Motor: {info.get('motor')}\nLC: {info.get('load_cell')}\nSensor: {info.get('sensor')}")
        self._checking_connections = False

        def ok_text(val):
            return isinstance(val, str) and ("OK" in val or "Connected" in val)

        motor_ok = ok_text(info.get("motor"))
        load_ok = ok_text(info.get("load_cell"))
        sensor_ok = ok_text(info.get("sensor"))

        if not (motor_ok and load_ok and sensor_ok):
            self.txt_report.append("")
            self.txt_report.append("Try:")
            self.txt_report.append("- Verify the selected drivers and configs.")
            self.txt_report.append("- Check power and cable connections.")
            self.txt_report.append("- For serial sensors: Scan Ports and confirm COM + baud.")

        if self._current_mode() == "auto":
            self._set_badge(self.badge_auto_stage, "ok" if motor_ok else "err")
            self._set_badge(self.badge_auto_load_cell, "ok" if load_ok else "err")
            self._set_badge(self.badge_auto_sensor, "ok" if sensor_ok else "err")
        else:
            self._set_badge(self.badge_stage, "ok" if motor_ok else "err")
            self._set_badge(self.badge_load_cell, "ok" if load_ok else "err")
            self._set_badge(self.badge_sensor, "ok" if sensor_ok else "err")

    @Slot()
    def on_finished(self):
        self.is_searching = False
        self.btn_start.setText("START TEST")
        self.btn_start.setObjectName("btn_success")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        self.btn_start.setEnabled(True)
        self.lbl_phase.setText("FINISHED")
        self.lbl_surface.setText("Complete")
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._show_message("Done", "Experiment Finished.", QMessageBox.Information)

    @Slot(str)
    def _on_status(self, msg):
        text = (msg or "").strip()
        if not text:
            return
        self.lbl_phase.setText(text)
        upper = text.upper()
        if "FINDING SURFACE" in upper:
            self.progress.setRange(0, 0)
            detail = ""
            if "..." in text:
                detail = text.split("...", 1)[-1].strip()
            self.lbl_surface.setText(f"Searching {detail}".strip())
        elif "SURFACE DETECTED" in upper:
            self.lbl_surface.setText("Detected")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        elif "SURFACE SET" in upper:
            self.lbl_surface.setText("Set (Manual)")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

    @Slot(str)
    def _on_error(self, msg):
        self.is_searching = False
        self.btn_start.setText("START TEST")
        self.btn_start.setObjectName("btn_success")
        self.btn_start.setEnabled(True)
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        self.progress.setRange(0, 100)
        self.lbl_surface.setText("-")
        if self._checking_connections:
            self._checking_connections = False
            self._set_connection_help(msg)
        self._show_message("Error", msg, QMessageBox.Warning)

    def _load_hardware_ui(self):
        cfg = self._hardware_cfg
        mode = (cfg.get("mode") or "manual").lower()
        self.cmb_mode.blockSignals(True)
        idx = self.cmb_mode.findData(mode)
        if idx >= 0:
            self.cmb_mode.setCurrentIndex(idx)
        else:
            self.cmb_mode.setCurrentIndex(self.cmb_mode.findData("manual"))
        self.cmb_mode.blockSignals(False)

        self._populate_driver_combo(
            self.cmb_stage_driver, IMotionStage, cfg.get("stage", {}).get("driver")
        )
        self._populate_driver_combo(
            self.cmb_load_cell_driver, ILoadCell, cfg.get("load_cell", {}).get("driver")
        )
        self._populate_driver_combo(
            self.cmb_sensor_driver, ITactileSensor, cfg.get("sensor", {}).get("driver")
        )

        sensor_cfg = cfg.get("sensor", {}).get("config", {})
        self._set_baud_combo(sensor_cfg.get("baud", 115200))
        self._refresh_serial_ports(select_port=sensor_cfg.get("port"))
        self._apply_mode(self._current_mode())
        self._update_hw_summary()
        self._update_required_highlights()

    def _populate_driver_combo(self, combo, base_cls, selected_path):
        combo.clear()
        options = hwcfg.list_driver_options(base_cls)
        for opt in options:
            combo.addItem(opt["name"], opt["path"])
        if selected_path:
            idx = combo.findData(selected_path)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.addItem(f"Unknown ({selected_path})", selected_path)
                combo.setCurrentIndex(combo.count() - 1)

    def _on_mode_changed(self, _index):
        self._apply_mode(self._current_mode())

    def _apply_mode(self, mode):
        mode = (mode or "").lower()
        self.lbl_sim_info.setVisible(mode == "sim")
        self.auto_panel.setVisible(mode == "auto")
        self.manual_panel.setVisible(mode == "manual")
        self.sensor_panel.setVisible(mode in {"auto", "manual"})
        show_hw_actions = mode != "sim"
        self.btn_hw_save.setVisible(show_hw_actions)
        self.lbl_hw_note.setVisible(show_hw_actions)
        if mode == "auto":
            self._run_auto_detect()
        self._update_hw_summary()
        self._update_required_highlights()

    def _current_mode(self):
        return self.cmb_mode.currentData() or self.cmb_mode.currentText().lower()

    def _run_auto_detect(self):
        cfg = hwcfg.load_config()
        cfg.setdefault("sensor", {}).setdefault("config", {})
        cfg["sensor"]["config"]["port"] = self.cmb_sensor_port.currentText().strip()
        cfg["sensor"]["config"]["baud"] = self._current_baud()
        try:
            stage_cls, load_cell_cls, sensor_cls = hwcfg.auto_detect_driver_classes(cfg)
            self.lbl_auto_stage.setText(stage_cls.__name__)
            self.lbl_auto_load_cell.setText(load_cell_cls.__name__)
            self.lbl_auto_sensor.setText(sensor_cls.__name__)
            self.lbl_auto_status.setText("Scan complete.")
            self._flash_button(self.btn_auto_rescan, "ok")
        except Exception as e:
            self.lbl_auto_stage.setText("Not detected")
            self.lbl_auto_load_cell.setText("Not detected")
            self.lbl_auto_sensor.setText("Not detected")
            self.lbl_auto_status.setText(f"Scan failed: {e}")
            self._flash_button(self.btn_auto_rescan, "warn")
        self._update_hw_summary()

    def _refresh_serial_ports(self, select_port=None):
        ports = hwcfg.list_serial_ports()
        current = select_port or self.cmb_sensor_port.currentText()
        self.cmb_sensor_port.clear()
        if ports:
            self.cmb_sensor_port.addItems(ports)
        if current:
            idx = self.cmb_sensor_port.findText(current)
            if idx >= 0:
                self.cmb_sensor_port.setCurrentIndex(idx)
            else:
                self.cmb_sensor_port.setEditText(current)
        if select_port is None:
            self._flash_button(self.btn_port_refresh, "info")

    def _suggest_serial_port(self):
        sensor_path = self.cmb_sensor_driver.currentData()
        if not sensor_path:
            return
        try:
            driver_cls = hwcfg.resolve_class(sensor_path)
        except Exception:
            driver_cls = None
        if driver_cls is None:
            return
        cfg = {"baud": self._current_baud()}
        suggested = hwcfg.suggest_serial_port(driver_cls, cfg)
        if suggested:
            idx = self.cmb_sensor_port.findText(suggested)
            if idx >= 0:
                self.cmb_sensor_port.setCurrentIndex(idx)
            else:
                self.cmb_sensor_port.setEditText(suggested)
            self._flash_button(self.btn_port_suggest, "ok")
        else:
            self._show_message("No Port Suggested", "No likely sensor port detected.", QMessageBox.Information)
            self._flash_button(self.btn_port_suggest, "warn")

    def _current_baud(self):
        text = self.cmb_sensor_baud.currentText().strip()
        try:
            return int(text)
        except ValueError:
            return 115200

    def _set_baud_combo(self, baud):
        text = str(int(baud)) if baud is not None else ""
        idx = self.cmb_sensor_baud.findText(text)
        if idx >= 0:
            self.cmb_sensor_baud.setCurrentIndex(idx)
        else:
            self.cmb_sensor_baud.setEditText(text)

    def _save_hardware_config(self):
        cfg = self._build_hw_config_from_ui()
        hwcfg.save_config(cfg)
        self._hardware_cfg = cfg
        self._show_message("Saved", "Hardware defaults saved for the next launch.", QMessageBox.Information)
        self._flash_button(self.btn_hw_save, "ok")

    def _build_hw_config_from_ui(self):
        cfg = hwcfg.load_config()
        cfg["mode"] = self._current_mode()

        cfg.setdefault("stage", {}).setdefault("config", {})
        cfg.setdefault("load_cell", {}).setdefault("config", {})
        cfg.setdefault("sensor", {}).setdefault("config", {})

        stage_path = self.cmb_stage_driver.currentData()
        load_cell_path = self.cmb_load_cell_driver.currentData()
        sensor_path = self.cmb_sensor_driver.currentData()
        if stage_path:
            cfg["stage"]["driver"] = stage_path
        if load_cell_path:
            cfg["load_cell"]["driver"] = load_cell_path
        if sensor_path:
            cfg["sensor"]["driver"] = sensor_path

        cfg["sensor"]["config"]["port"] = self.cmb_sensor_port.currentText().strip()
        cfg["sensor"]["config"]["baud"] = self._current_baud()
        return cfg

    def _apply_hardware_for_session(self, show_message=True):
        if self.coord.running:
            self._show_message("Busy", "Stop the experiment before changing hardware.", QMessageBox.Warning)
            return False

        if not self._update_required_highlights(enforce=True):
            self._show_message("Missing Required Fields", "Complete the required hardware fields.", QMessageBox.Warning)
            self._set_connection_help("Missing required hardware selections.")
            return False

        cfg = self._build_hw_config_from_ui()
        snapshot = json.dumps(cfg, sort_keys=True)
        if snapshot == self._active_hw_snapshot:
            if show_message:
                self._show_message("Ready", "Selected hardware is already active.", QMessageBox.Information)
            return True

        try:
            motor, load_cell, sensor = hwcfg.get_hardware_components(cfg)
        except Exception as e:
            self._show_message("Hardware Error", f"Failed to build hardware: {e}", QMessageBox.Warning)
            return False

        try:
            self.coord.set_hardware(motor, load_cell, sensor)
        except Exception as e:
            self._show_message("Hardware Error", f"Failed to apply hardware: {e}", QMessageBox.Warning)
            return False

        self._active_hw_snapshot = snapshot
        if show_message:
            self._show_message("Applied", "Hardware applied for this session.", QMessageBox.Information)
        return True

    def _check_connections(self):
        if self._checking_connections and self._check_thread and self._check_thread.is_alive():
            self.txt_report.setText("Connection check already in progress...")
            self._flash_button(self.btn_check, "info")
            return

        self._checking_connections = True
        self.txt_report.setText("Checking connections...")
        if not self._apply_hardware_for_session(show_message=False):
            self._checking_connections = False
            self._flash_button(self.btn_check, "warn")
            return

        self._check_thread = threading.Thread(target=self.coord.discover_hardware, daemon=True)
        self._check_thread.start()
        QTimer.singleShot(self._conn_timeout_ms, self._on_check_timeout)
        self._flash_button(self.btn_check, "info")

    def _on_check_timeout(self):
        if not (self._checking_connections and self._check_thread and self._check_thread.is_alive()):
            return
        self.txt_report.setText(
            "Connection check timed out.\n\nTry:\n"
            "- Verify the selected drivers and configs.\n"
            "- Check power and cable connections.\n"
            "- For serial sensors: Scan Ports and confirm COM + baud.\n"
            "- Try Auto Detect or Simulation if hardware is unavailable."
        )
        self._flash_button(self.btn_check, "warn")

    def _on_test_type_changed(self):
        test_type = self.cmb_test_type.currentData()
        return test_type
