import pyqtgraph as pg
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QGraphicsDropShadowEffect


def _set_downsampling(plot_item):
    # pyqtgraph uses either "method" or "mode" depending on the version.
    try:
        plot_item.setDownsampling(auto=True, method='peak')
    except TypeError:
        try:
            plot_item.setDownsampling(auto=True, mode='peak')
        except TypeError:
            plot_item.setDownsampling(auto=True)


class DashboardPlots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Global Config
        pg.setConfigOption('background', '#F8FBFF')
        pg.setConfigOption('foreground', '#1F2A36')
        pg.setConfigOption('antialias', False)

        # --- STYLE ---
        self._label_style = {'color': '#1F2A36', 'font-size': '10pt'}
        self._tick_font = QFont("Segoe UI", 9)

        # --- PLOT 1: FORCE (Fz) ---
        self.plot_force = pg.PlotWidget()
        plot_force_item = self.plot_force.getPlotItem()
        plot_force_item.setClipToView(True)
        _set_downsampling(plot_force_item)

        # Axes
        ax_left = self.plot_force.getAxis('left')
        ax_left.enableAutoSIPrefix(False)
        ax_left.setTickFont(self._tick_font)
        self.plot_force.setLabel('left', "Force (N)", **self._label_style)

        ax_bottom = self.plot_force.getAxis('bottom')
        ax_bottom.enableAutoSIPrefix(False)
        ax_bottom.setTickFont(self._tick_font)
        self.plot_force.setLabel('bottom', "Time (s)", **self._label_style)

        self.plot_force.showGrid(x=True, y=True, alpha=0.3)
        self.curve_force = self.plot_force.plot(pen=pg.mkPen('#D32F2F', width=2.5))

        # --- FIXED FORCE INDICATOR ---
        # Anchor (1,0) means the (x,y) pos refers to the Top-Right of the text bounding box.
        self.force_text = pg.TextItem(text="0.000 N", color='#B71C1C', anchor=(1, 0))
        self.force_text.setFont(QFont("Segoe UI", 14, QFont.Bold))  # Reduced size
        self.force_text.setParentItem(self.plot_force.graphicsItem())

        self.grp_force = QGroupBox("Load Cell Response")
        grp_force_layout = QVBoxLayout(self.grp_force)
        grp_force_layout.setContentsMargins(12, 18, 12, 12)
        grp_force_layout.addWidget(self.plot_force)
        layout.addWidget(self.grp_force)

        # --- PLOT 2: SENSOR ---
        self.plot_sensor = pg.PlotWidget()
        plot_sensor_item = self.plot_sensor.getPlotItem()
        plot_sensor_item.setClipToView(True)
        _set_downsampling(plot_sensor_item)

        ax_left_s = self.plot_sensor.getAxis('left')
        ax_left_s.enableAutoSIPrefix(False)
        ax_left_s.setTickFont(self._tick_font)
        self.plot_sensor.setLabel('left', "Raw Output", **self._label_style)

        ax_bottom_s = self.plot_sensor.getAxis('bottom')
        ax_bottom_s.setTickFont(self._tick_font)
        self.plot_sensor.setLabel('bottom', "Time (s)", **self._label_style)

        self.plot_sensor.showGrid(x=True, y=True, alpha=0.3)
        self.grp_sensor = QGroupBox("Tactile Sensor Response")
        grp_sensor_layout = QVBoxLayout(self.grp_sensor)
        grp_sensor_layout.setContentsMargins(12, 18, 12, 12)
        grp_sensor_layout.addWidget(self.plot_sensor)
        layout.addWidget(self.grp_sensor)

        self.sensor_curves = []
        self.sensor_legend = None
        self.colors = ['#1976D2', '#388E3C', '#FBC02D', '#7B1FA2', '#E64A19']

        for grp in (self.grp_force, self.grp_sensor):
            self._apply_glass_effect(grp)

    def _apply_glass_effect(self, widget):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(20)
        effect.setOffset(0, 6)
        effect.setColor(QColor(15, 20, 25, 40))
        widget.setGraphicsEffect(effect)

    def init_sensor_curves(self, num_channels, names=None):
        self.plot_sensor.clear()
        self.sensor_curves = []
        self.sensor_legend = self.plot_sensor.addLegend(offset=(10, 10))
        if self.sensor_legend is not None:
            self.sensor_legend.setBrush(pg.mkBrush(255, 255, 255, 0))
            self.sensor_legend.setPen(pg.mkPen(0, 0, 0, 0))
        self.plot_sensor.showGrid(x=True, y=True, alpha=0.3)
        ax_left_s = self.plot_sensor.getAxis('left')
        ax_left_s.enableAutoSIPrefix(False)
        ax_left_s.setTickFont(self._tick_font)
        self.plot_sensor.setLabel('left', "Raw Output", **self._label_style)
        ax_bottom_s = self.plot_sensor.getAxis('bottom')
        ax_bottom_s.setTickFont(self._tick_font)
        self.plot_sensor.setLabel('bottom', "Time (s)", **self._label_style)
        names = names or []
        for i in range(num_channels):
            c = self.colors[i % len(self.colors)]
            label = names[i] if i < len(names) else f"Ch_{i + 1}"
            curve = self.plot_sensor.plot(pen=pg.mkPen(c, width=2), name=label)
            self.sensor_curves.append(curve)

    def update_plots(self, t, f, s_cols):
        self.curve_force.setData(t, f, skipFiniteCheck=True)
        for i, curve in enumerate(self.sensor_curves):
            if i < len(s_cols):
                curve.setData(t, s_cols[i], skipFiniteCheck=True)

        # Update Overlay
        if f:
            self.force_text.setText(f"{f[-1]:.3f} N")
            # Logic: Get Width of widget, subtract margin (20px).
            # Y=40 pushes it down inside the plot area.
            view_w = self.plot_force.width()
            self.force_text.setPos(view_w - 20, 40)

    def set_x_range(self, t_min, t_max):
        self.plot_force.setXRange(t_min, t_max)
        self.plot_force.enableAutoRange(axis='y')

        self.plot_sensor.setXRange(t_min, t_max)
        self.plot_sensor.enableAutoRange(axis='y')

    def clear(self):
        self.curve_force.setData([], [])
        for c in self.sensor_curves: c.setData([], [])
