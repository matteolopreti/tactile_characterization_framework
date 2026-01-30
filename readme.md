# Tactile Sensor Characterization Framework

A modular, hardware-agnostic Python framework for repeatable tactile sensor characterization with a motion stage, load
cell, and sensor under test.

## Features

- Abstract interfaces for motion stage, load cell, and tactile sensor drivers
- Real-time plotting with PySide6 and pyqtgraph
- Background sampling threads to keep the UI responsive
- Timestamped CSV and SQLite logging

## Quick start (simulation)

1. Open the GUI and set Hardware Mode to `sim`, or edit `config/hardware.json` and set `"mode": "sim"`.
2. Run:

```bash
python main.py
```

## Hardware configuration

`config/hardware.json` supports three modes:

- `"sim"`: use mock drivers
- `"auto"`: auto-detect available drivers
- `"manual"`: select driver classes explicitly

The GUI includes a Hardware panel to edit mode, driver selection, and sensor port/baud.
Saved changes apply on the next launch.

### Auto-detect behavior

Auto-detect scans `drivers/` for classes that implement the interfaces and provide a `probe` method. Drivers can define:

- `PROBE_PRIORITY`: higher values are preferred when multiple drivers match
- `@classmethod probe(config) -> bool`: returns True if hardware is available

### Manual driver selection

In manual mode, edit `config/hardware.json` to choose the drivers and configure their parameters.

### Writing a driver

Use `drivers/_template.py` as a starting point, or create a new file under `drivers/`
and implement the appropriate interface:

```python
from interfaces.motion_stage import IMotionStage


class MyStage(IMotionStage):
    def connect(self):
        pass

    def disconnect(self):
        pass

    def move_to_absolute(self, z_mm, velocity):
        pass

    def move_relative(self, dist_mm, velocity):
        pass

    def get_position(self):
        return 0.0
```

If you want the driver to work with auto-detect, also add `PROBE_PRIORITY` and a `probe` method.
See `drivers/README.md` for the template and checklist.

## Data output

Logs are written under `data/` with a timestamped filename. Both CSV and SQLite formats are supported.

## Architecture

- `gui/`: PySide6 user interface and plots
- `core/`: coordinator, timing, async wrappers, and logging
- `interfaces/`: abstract base classes
- `drivers/`: hardware-specific implementations

## Contributing

New drivers are welcome. Please include a `probe` method if the driver should be auto-detected.

## Citation
If you use this suite in your research, please cite:

Lo Preti, M., et al. "Enabling Reproducible Soft Robotics: A Two-Stage Pipeline for the Characterization of Tactile
Sensors." (2026).
