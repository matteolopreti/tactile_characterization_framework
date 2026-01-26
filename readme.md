# Tactile Sensor Characterization Suite

A modular, hardware-agnostic Python framework for the reproducible characterization of soft tactile sensors.

This suite implements the **"Two-Stage Characterization Pipeline"** (Benchtop Characterization & In-Situ Evaluation), ensuring metrological rigor through automated surface detection, viscoelastic relaxation handling, and synchronized high-speed data acquisition.

## 🌟 Key Features

- **Universal Hardware Support:** Uses an Abstract Driver layer. Works with *any* motion stage (ACS, Thorlabs, Newport) or sensor (DAQ, Serial, Bluetooth) by simply writing a small wrapper class.
- **Metrology-Grade Protocol:** * Automated **Contact Detection** (Surface Finding) to establish a repeatable datum ($h=0$).
  - **Viscoelastic Relaxation** enforcement (ISO 14577 compliant) to prevent phase lag.
  - **Hysteresis Analysis** via automated cycling.
- **Real-Time Visualization:** Dual-axis PyQt5 dashboard plotting Force vs. Time and Sensor Signal vs. Time simultaneously.
- **High-Performance Logging:** Uses `multiprocessing` to decouple high-speed sensor reading from the UI thread, ensuring no data loss.

## 🛠️ Installation

1. **Clone the repository:**
  
  ```bash
  git clone [https://github.com/your-lab/tactile-characterization-suite.git](https://github.com/your-lab/tactile-characterization-suite.git)
  cd tactile-characterization-suite
  ```
  
2. **Create a virtual environment (Recommended):**
  
  ```bash
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  ```
  
3. **Install dependencies:**
  
  ```bash
  pip install -r requirements.txt
  ```
  

## 🚀 Quick Start (Simulation Mode)

You can run the software immediately without connecting any hardware. The suite comes with `MockDrivers` that simulate a sensor and motor response.

1. Open `config_hardware.py`.
  
2. Ensure the "Mock" drivers are selected:
  
  ```python
  # config_hardware.py
  from drivers.mock_drivers import MockMotionStage, MockTactileSensor, MockLoadCell
  
  MOTOR_DRIVER = MockMotionStage
  SENSOR_DRIVER = MockTactileSensor
  LOAD_CELL_DRIVER = MockLoadCell
  ```
  
3. Run the application:
  
  ```bash
  python main.py
  ```
  

## ⚙️ Configuring Your Hardware

To use your own lab equipment, you do not need to change the core code. You only need to edit the `drivers/` folder.

### Step 1: Create a Driver

Create a new file in `drivers/` (e.g., `my_motor.py`) and implement the standard interface:

````
```python
from interfaces.motion_stage import IMotionStage

class MyCustomMotor(IMotionStage):
 def connect(self):
 # Your hardware connection code
 passdef move_to_absolute(self, z_mm, velocity):
    # Your hardware move code
    pass
````

### Step 2: Register in Config

Edit `config_hardware.py` to point to your new class:

Python

```
from drivers.my_motor import MyCustomMotor

MOTOR_DRIVER = MyCustomMotor
MOTOR_PARAMS = {"port": "COM3", "baud": 9600}
```

## 📊 Output Data

Data is saved automatically to an SQLite database (experiment_data.db).

The schema is dynamic based on your sensor, but generally follows:

| **Timestamp** | **Pos_Z (mm)** | **Force_Z (N)** | **Sensor_Ch1** | **Sensor_Ch2** | **...** |
| --- | --- | --- | --- | --- | --- |
| 0.015 | 5.001 | 0.002 | 1204 | 503 | ... |

## 🏗️ Architecture

The software follows a **Model-View-Controller (MVC)** pattern to ensure safety and scalability:

- **GUI (`/gui`)**: Handles user input and plotting. It is "dumb" and knows nothing about hardware.
  
- **Coordinator (`/core`)**: The "Brain." It executes the State Machine (Idle -> Find Surface -> Indent -> Hold -> Retract). It handles safety checks and signals.
  
- **AsyncWrapper (`/core`)**: Runs sensor drivers in a separate process to prevent UI freezing and buffer overflows.
  

## 🤝 Contributing

We welcome contributions! If you write a driver for common hardware (e.g., specific Insties/SmarAct stages), please submit a Pull Request.

## 📄 Citation

If you use this suite in your research, please cite:

> Lo Preti, M., et al. "Enabling Reproducible Soft Robotics: A Two-Stage Pipeline for the Characterization of Tactile Sensors." (2026).