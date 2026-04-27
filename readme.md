# Tactile Sensor Characterization Framework

A GUI-driven Python framework for repeatable tactile sensor characterization with a motion stage, load cell, and
sensor under test. It supports simulation mode, hardware auto-detect, and structured logging for experiments.

## What this project does

- Runs a load/hold/unload protocol with an initial pre-conditioning cycle.
- Finds the contact surface automatically by force threshold or manually by user trigger.
- Streams and plots force and sensor channels in real time.
- Logs timestamped CSV and SQLite files for analysis.

## Startup

This repository targets Python 3.9 through 3.13 and provides reproducible setup paths for publication.

### Install `uv` (Recommended)

`uv` is an extremely fast Python package and project manager. If you don't have it installed:

- **Windows:**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **macOS/Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Quick Start (Recommended)

Use `uv` for the fastest setup and execution:

```bash
uv venv .venv
uv pip install -e .
uv run python main.py
```

### Standard Installation

Using the Makefile (Linux/macOS/WSL):

```bash
make setup
make run
```

Or using pip/venv:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python main.py
```

For macOS/Linux, replace `.venv\Scripts\python` with `.venv/bin/python`.

## Run (simulation)

1. In the GUI, set Hardware Mode to `sim`, or edit `config/hardware.json` and set `"mode": "sim"`.
2. Start the app:

```bash
uv run python main.py
```

If you used the standard venv setup, run:

```bash
.venv\Scripts\python main.py
```

## Run with hardware

1. Open the Hardware panel and choose `auto` or `manual` mode.
2. In manual mode, select driver classes and set sensor port and baud. Click **Save Hardware Config**.
3. Click **Apply and Check Connections** to verify devices.
4. Configure experiment parameters (depth, speed, hold time, contact force, cycles, logging rate).
5. Click **Start Test**. During surface finding you can click **Set Surface Now** to manually set the contact point.

## Configuration

Hardware defaults live in `config/hardware.json`:

```json
{
  "mode": "manual",
  "stage": {
    "driver": "drivers.acs_stage.ACSMotionStage",
    "config": { "ip": "10.0.0.100", "port": 701 }
  },
  "load_cell": {
    "driver": "drivers.ati_daq.NIDAQLoadCell",
    "config": { "channel_base": "Dev1/ai", "cal_file": "FT58072.cal" }
  },
  "sensor": {
    "driver": "drivers.serial_sensor.SerialMagneticSensor",
    "config": { "port": "COM1", "baud": 115200 }
  }
}
```

Modes:

- `sim`: mock drivers only
- `auto`: pick drivers via `probe()` and `PROBE_PRIORITY`
- `manual`: use explicit driver class paths

The GUI Hardware panel can edit mode, driver selection, and serial settings. Saved changes apply on the next launch.

## Drivers and dependencies

Built-in drivers:

- `drivers/acs_stage.py`: ACS stage (requires `SPiiPlusPython`, proprietary)
- `drivers/ati_daq.py`: NI DAQ + ATI load cell (requires `nidaqmx`, optional `atiiaftt` for calibration)
- `drivers/serial_sensor.py`: serial sensor (requires `pyserial`)
- `drivers/mock_drivers.py`: simulation drivers (no hardware)

If a vendor library is missing, that driver will not connect (or will run in simulation where available).
Install proprietary vendor packages manually inside the Pixi environment.

## Data output

Logs are written to `data/` with timestamped filenames:

- `experiment_YYYY-MM-DD_HH-MM-SS.csv`
- `experiment_YYYY-MM-DD_HH-MM-SS.db`

Columns include `Time`, `Pos`, `Force_Net`, `Phase`, plus sensor channels detected at runtime.

## Project layout

- `gui/`: PySide6 interface and plots
- `core/`: experiment coordinator, timing, logging
- `interfaces/`: abstract base classes
- `drivers/`: hardware implementations and templates
- `config/`: hardware defaults and calibration files

## Contributing

Use `drivers/_template.py` to add a new driver and implement the appropriate interface. Include `probe()` and
`PROBE_PRIORITY` if you want auto-detect. See `drivers/README.md` for the checklist.

## Citation

If you use this suite in your research, please cite:

Lo Preti, M., et al. "Enabling Reproducible Soft Robotics: A Two-Stage Pipeline for the Characterization of Tactile
Sensors." (2026).
