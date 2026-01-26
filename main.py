import sys
import os
from PySide6.QtWidgets import QApplication

# 1. Setup Core Imports
# Ensure we can see the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_hardware import get_hardware_components
from Core.coordinator import ExperimentCoordinator
from GUI.main_window import TactileTestUI


def main():
    # A. Create Qt Application
    app = QApplication(sys.argv)

    # B. Load Hardware (Real or Mock based on config)
    try:
        motor, load_cell, sensor = get_hardware_components()
    except Exception as e:
        print(f"CRITICAL ERROR loading hardware: {e}")
        sys.exit(1)

    # C. Initialize Logic Core
    # The Coordinator acts as the bridge between Hardware and GUI
    coordinator = ExperimentCoordinator(motor, load_cell, sensor)

    # D. Initialize GUI
    window = TactileTestUI(coordinator)
    window.show()

    # E. Run Main Loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()