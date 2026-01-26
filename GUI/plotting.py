import PySide6
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout


class DashboardPlots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Global Style
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOption('antialias', True)  # Smoother lines

        # --- PLOT 1: FORCE RESPONSE ---
        self.plot_force = pg.PlotWidget(title="Force Response (Fz)")
        self.plot_force.setLabel('left', "Force", units='N')
        self.plot_force.setLabel('bottom', "Time", units='s')
        self.plot_force.showGrid(x=True, y=True, alpha=0.3)
        self.plot_force.setMouseEnabled(x=True, y=True)

        # Force Curve (Blue)
        self.curve_force = self.plot_force.plot(pen=pg.mkPen('#2196F3', width=2))
        layout.addWidget(self.plot_force)

        # --- PLOT 2: TACTILE SENSOR ---
        self.plot_sensor = pg.PlotWidget(title="Tactile Sensor Signals")
        self.plot_sensor.setLabel('left', "Raw Signal", units='V')
        self.plot_sensor.setLabel('bottom', "Time", units='s')
        self.plot_sensor.showGrid(x=True, y=True, alpha=0.3)
        self.plot_sensor.addLegend(offset=(10, 10))

        layout.addWidget(self.plot_sensor)

        # State
        self.sensor_curves = []
        # Distinct colors for up to 10 channels
        self.colors = [
            '#F44336',  # Red
            '#4CAF50',  # Green
            '#9C27B0',  # Purple
            '#FF9800',  # Orange
            '#607D8B',  # Blue Grey
            '#795548',  # Brown
            '#E91E63',  # Pink
            '#3F51B5',  # Indigo
            '#00BCD4',  # Cyan
            '#CDDC39'  # Lime
        ]

    def init_sensor_curves(self, num_channels, column_names=None):
        """
        Initializes the curves once we know how many channels exist.
        """
        self.plot_sensor.clear()
        self.sensor_curves = []

        for i in range(num_channels):
            color = self.colors[i % len(self.colors)]
            name = column_names[i] if column_names and i < len(column_names) else f"Ch {i}"

            # Create curve
            curve = self.plot_sensor.plot(
                name=name,
                pen=pg.mkPen(color, width=2)
            )
            self.sensor_curves.append(curve)

    def update_plots(self, time_data, force_data, sensor_data_columns):
        """
        Efficiently updates data.
        Args:
            time_data (list): [t0, t1, ...]
            force_data (list): [f0, f1, ...]
            sensor_data_columns (list of lists): [[ch0_t0, ...], [ch1_t0, ...]]
        """
        # Update Force
        self.curve_force.setData(time_data, force_data)

        # Update Sensors
        # Note: sensor_data_columns must match sensor_curves length
        for i, curve in enumerate(self.sensor_curves):
            if i < len(sensor_data_columns):
                curve.setData(time_data, sensor_data_columns[i])

    def clear(self):
        self.curve_force.clear()
        # We don't clear sensor curves entirely, just their data,
        # unless reset is explicitly needed.
        for curve in self.sensor_curves:
            curve.setData([], [])