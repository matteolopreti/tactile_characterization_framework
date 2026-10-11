# Tactile Sensor Characterization Framework

Open-source Python reference implementation of the uniaxial Quasi-Static Indentation execution (Test 1) described in:

> M. Lo Preti, W. Buxiu, P. Trunin, M. S. Nazeer, L. Beccai, P. Maiolino, C. Laschi.
> **A Two-Stage Characterization Pipeline and Open-Source Framework for Reproducible Tactile Sensing.**
> *Advanced Intelligent Systems* (2026). DOI: [10.1002/aisy.70436](https://doi.org/10.1002/aisy.70436)

This repository ships the GUI-driven, multi-threaded Model–View–Controller (MVC) execution layer detailed in Appendix D of the paper: a controller that orchestrates a motion stage, a reference load cell, and a tactile sensor under test, and produces time-series records that conform to the Standardized Digital Datasheet schema (Appendix C.2) and can be reduced to a Comparison Card (Section 4.3) using the metric algorithms of Appendix C.1.

## Scope

The framework targets any deformable tactile sensor whose transduction yields a scalar or low-dimensional time-series electrical output — resistive, capacitive, inductive, magnetic, piezoelectric, or discrete optical. Vision-based tactile sensors fall outside the Stage 1 metric definitions at the signal level (see Section 1.4 of the paper).

This release implements **Test 1 — Quasi-Static Indentation** (Section B.2.3): a uniaxial load–hold–unload protocol under displacement control, executed exactly as the state machine of Appendix D Figure S7. It covers:

- Surface detection by force-threshold closed loop or manual user trigger (Section B.2.2).
- Pre-conditioning cycle (Mullins effect mitigation) prepended to every run.
- Configurable depth, speed, hold time, contact-force threshold, cycle count, and logging rate.
- Synchronized, rate-limited acquisition of indenter position, reference force, and sensor channels on a common clock (Appendix D.3).
- Asynchronous logging to CSV and SQLite (WAL mode), with the sensor channel count auto-detected at connect time.
- Modular hardware abstraction behind three abstract bases (`IMotionStage`, `ILoadCell`, `ITactileSensor`), with auto-detect, manual selection, and full simulation modes.

The remaining Stage 1 tests in the protocol (T2–T9) and the Stage 2 in-situ apparatus are out of scope for this release; they are intentionally application-specific (Section 3) and left to downstream extensions of the same architecture.

## Architecture

The execution model follows the Prioritized Producer–Consumer pattern of Appendix D.2:

- **Coordinator** (high-priority) — runs the experimental state machine and enforces sampling on a high-resolution performance counter via a rate limiter.
- **GUI thread** (low-priority) — independently polls plot buffers; UI lag never back-propagates into the control loop.
- **Sensor producer** — continuously polls the device under test and exposes a *latest-value* register, so synchronized gather events resolve in O(1) and never block on serial transmission.
- **Motion worker** — spawned transiently for blocking moves; the Coordinator keeps logging at the configured rate throughout the ramp, capturing the viscoelastic profile rather than just endpoints.
- **Logger consumer** — drains a bounded FIFO to SQLite/CSV, decoupling disk latency from the experimental clock.

Hardware drivers live behind the interfaces in `interfaces/`, so vendor libraries (ACS SPiiPlus, NI-DAQmx, ATI ATIDAQ, pyserial) can be swapped or substituted with the bundled mock drivers without touching the metrology core.

## Installation

Targets Python 3.9–3.13.

### With `uv` (recommended)

```bash
uv venv .venv
uv pip install -e .
uv run python main.py
```

Install `uv` first if needed:

- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### With pip / venv

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip   # .venv\Scripts\python on Windows
.venv/bin/python -m pip install -e .
.venv/bin/python main.py
```

Or via the Makefile: `make setup && make run`.

## Running

### Simulation

Set `mode: sim` in the GUI Hardware panel (or in `config/hardware.json`) to load the mock drivers. The protocol, plots, and logging run end-to-end without hardware — useful for protocol rehearsal, CI, and teaching.

### With hardware

1. Open the Hardware panel and choose `auto` (probe drivers and pick best match by `PROBE_PRIORITY`) or `manual` (explicit driver paths).
2. For serial sensors, **Scan Ports** and confirm baud rate.
3. **Save Hardware Config** to persist defaults for the next launch.
4. **Apply and Check Connections** — verifies stage/load cell/sensor handshakes and reports per-device status.
5. Set experiment parameters (depth, speed, hold time, contact force, cycles, logging rate, plot window).
6. **Start Test**. During surface finding the START button toggles to **Set Surface Now** for manual override.

## Configuration

Defaults live in `config/hardware.json`:

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
  },
  "experiment": {
    "depth": 0.5, "speed": 0.1, "hold_time": 0.5, "contact_force": 0.04
  }
}
```

Modes:

- `sim` — mock drivers only.
- `auto` — discover drivers via each class's `probe()` method, ranked by `PROBE_PRIORITY`.
- `manual` — explicit driver class paths.

The Hardware panel in the GUI edits all of the above and persists changes to the file on save.

## Bundled drivers

| Driver | Hardware | Required vendor library |
|---|---|---|
| `drivers.acs_stage.ACSMotionStage` | ACS SPiiPlus motion controller | `SPiiPlusPython` (proprietary) |
| `drivers.ati_daq.NIDAQLoadCell` | NI-DAQ + ATI multi-axis F/T sensor | `nidaqmx`; optional `atiiaftt` for calibrated readings |
| `drivers.serial_sensor.SerialMagneticSensor` | Generic CSV-streaming serial sensor (channel count auto-detected) | `pyserial` |
| `drivers.mock_drivers.*` | Simulated devices | none |

Missing a vendor library degrades the affected driver to a no-op or simulated path; the framework still launches.

## Data output

Each run produces a pair of timestamped files in `data/`, named by the experimental conditions:

```
data/experiment_D0.5_S0.10_C5_R50_T1.0_F0.04_2026-05-22_14-30-12.csv
data/experiment_D0.5_S0.10_C5_R50_T1.0_F0.04_2026-05-22_14-30-12.db
```

Columns: `Time, Pos, Force_Net, Phase` plus the sensor channels detected at runtime. `Phase` is the labelled segmentation (`MULLIN_LOADING`, `CYCLE_1_HOLDING`, …) ready for the segmentation step of the workflow in Section 4.2.

These files are the raw input to the Digital Datasheet (Appendix C.2) and the Comparison Card (Section 4.3). The Test 1 metric algorithms of Appendix C.1 — sensitivity, hysteresis, and linearity error — operate directly on this schema.

## Repository layout

```
gui/         PySide6 interface, pyqtgraph plots, GUI-side controls
core/        Coordinator, async wrappers, rate limiter, logger, hardware config
interfaces/  IMotionStage, ILoadCell, ITactileSensor abstract bases
drivers/     Hardware implementations (ACS, NI-DAQ/ATI, serial, mocks) + template
config/      Hardware defaults and calibration files
main.py      Entry point
```

## Adding a driver

Copy `drivers/_template.py`, implement the relevant interface, and optionally declare `PROBE_PRIORITY` and `probe(config)` for auto-detect. See `drivers/README.md` for the checklist. New drivers become selectable in the GUI without further wiring.

## Changelog

- Sensor frames are now stamped with the host read time and numbered: two new trailing log columns, `sensor_t_s` (same clock as `Time`) and `sensor_seq` (frame counter; a repeated value marks a stale frame). Before the first frame, sensor values and `sensor_t_s` are NaN (CSV `nan`, SQLite NULL) and `sensor_seq` is 0, instead of zeros. The host read time equals the frame arrival time only while the reader keeps up with the device; with `TCF_SENSOR_MAX_HZ` throttling, a backlog forms and the stamp lags arrival.

## Companion paper

The Component–System Dichotomy, the calibrated-interaction paradigm, and the broader Design-for-Benchmarking culture that motivate this protocol are developed in:

> M. Lo Preti, M. S. Nazeer, J. Pinskier, D. Howard, C. Laschi. *Advanced Intelligent Systems* (2026).

## Citation

If you use this framework in research, please cite:

```bibtex
@article{LoPreti2026Pipeline,
  author  = {Lo Preti, Matteo and Buxiu, Weng and Trunin, Petr and Nazeer, Muhammad Sunny and Beccai, Lucia and Maiolino, Perla and Laschi, Cecilia},
  title   = {A Two-Stage Characterization Pipeline and Open-Source Framework for Reproducible Tactile Sensing},
  journal = {Advanced Intelligent Systems},
  year    = {2026},
  doi     = {10.1002/aisy.70436}
}
```

## License

Released under the MIT License. See [LICENSE](LICENSE).

## Contact

Corresponding author: Matteo Lo Preti — `mlp95@nus.edu.sg`
Soft Robotics Lab, College of Design and Engineering, National University of Singapore.
