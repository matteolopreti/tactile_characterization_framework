import os
import sys

from PySide6.QtWidgets import QApplication

# Setup path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.hardware_config import get_hardware_components
from core.coordinator import ExperimentCoordinator
from gui.main_window import TactileTestUI
def main():
    app = QApplication(sys.argv)

    try:
        motor, load_cell, sensor = get_hardware_components()
    except Exception as e:
        print(f"CRITICAL ERROR loading hardware: {e}")
        sys.exit(1)

    coordinator = ExperimentCoordinator(motor, load_cell, sensor)

    window = TactileTestUI(coordinator)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
