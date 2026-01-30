import os
import threading
import time

from PySide6.QtCore import QObject, Signal

from .async_wrapper import AsyncSensorRunner, AsyncValuePoller
from .data_logger import DataLogger
from .profiler import PerfMonitor
from .timing import RateLimiter


def _env_flag(name, default=False):
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name, default=None):
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


class ExperimentCoordinator(QObject):
    sig_status = Signal(str)
    sig_hw_info = Signal(dict)
    sig_packet = Signal(dict)
    sig_error = Signal(str)
    sig_finished = Signal()

    def __init__(self, motor, load_cell, sensor_driver):
        super().__init__()
        self.motor = motor
        self.load_cell = load_cell
        self.sensor_driver = sensor_driver
        self.running = False
        self.stop_requested = False
        self.manual_surface_flag = False
        self.force_offset = 0.0
        self.sensor_runner = None
        self.load_cell_runner = None
        self.position_runner = None
        self._stop_evt = threading.Event()
        self._perf = None
        self._profile_enabled = _env_flag("TCF_PROFILE", True)
        self._profile_memory = _env_flag("TCF_PROFILE_MEM", self._profile_enabled)
        self._ui_emit_period = 0.0
        self._ui_last_emit = 0.0

    def discover_hardware(self):
        try:
            info = {}
            if not self.motor.connected: self.motor.connect()
            info['motor'] = "Connected"
            if not self.load_cell.connected: self.load_cell.connect()
            self.force_offset = self.load_cell.read_force()
            info['load_cell'] = f"OK (Offset: {self.force_offset:.2f}N)"
            if not self.sensor_driver.connected: self.sensor_driver.connect()
            cols = self.sensor_driver.get_column_names()
            info['sensor'] = f"OK ({len(cols)} Ch)"
            self.sig_hw_info.emit(info)
        except Exception as e:
            self.sig_error.emit(str(e))

    def trigger_manual_surface(self):
        self.manual_surface_flag = True
        self.sig_status.emit("MANUAL SURFACE TRIGGERED")

    def set_hardware(self, motor, load_cell, sensor_driver):
        if self.running:
            raise RuntimeError("Cannot change hardware while running.")

        for runner in (self.sensor_runner, self.load_cell_runner, self.position_runner):
            if runner:
                try:
                    runner.stop()
                except Exception:
                    pass
        self.sensor_runner = None
        self.load_cell_runner = None
        self.position_runner = None

        for dev in (self.motor, self.load_cell, self.sensor_driver):
            if dev and hasattr(dev, "disconnect"):
                try:
                    dev.disconnect()
                except Exception:
                    pass

        self.motor = motor
        self.load_cell = load_cell
        self.sensor_driver = sensor_driver
        self.force_offset = 0.0
        self.manual_surface_flag = False

    def start_experiment(self, params):
        if self.running: return
        self.running = True
        self.stop_requested = False
        self.manual_surface_flag = False
        self._stop_evt.clear()
        threading.Thread(target=self._run_protocol, args=(params,), daemon=True).start()

    def stop(self):
        self.stop_requested = True
        self._stop_evt.set()

    def _run_protocol(self, params):
        db = None
        try:
            rate_hz = float(params.get('sampling_rate', 50))
            if rate_hz <= 0:
                raise ValueError("sampling_rate must be > 0")

            self._perf = PerfMonitor(
                enabled=self._profile_enabled,
                enable_memory=self._profile_memory,
                label="Experiment "
            )

            ui_rate_hz = _env_float("TCF_UI_RATE_HZ", 20.0) or 0.0
            self._ui_emit_period = 1.0 / ui_rate_hz if ui_rate_hz > 0 else 0.0
            self._ui_last_emit = -1e9

            sensor_rate_limit = _env_float("TCF_SENSOR_MAX_HZ", None)
            if sensor_rate_limit is None:
                driver_module = self.sensor_driver.__class__.__module__.lower()
                if "mock" in driver_module:
                    sensor_rate_limit = max(rate_hz, 200.0)

            self.sensor_runner = AsyncSensorRunner(self.sensor_driver, max_rate_hz=sensor_rate_limit)
            self.sensor_runner.start()
            self.load_cell_runner = AsyncValuePoller(
                self.load_cell.read_force, default=0.0, rate_hz=rate_hz, name="load_cell"
            )
            self.position_runner = AsyncValuePoller(
                self.motor.get_position, default=0.0, rate_hz=rate_hz, name="motor_pos"
            )
            self.load_cell_runner.start()
            self.position_runner.start()

            cols = self.sensor_driver.get_column_names()
            header = ["Time", "Pos", "Force_Net", "Phase"] + cols
            db = DataLogger(
                "experiment",
                columns=header,
                async_logging=True,
                enable_csv=params.get("log_csv", True),
                enable_sqlite=params.get("log_sqlite", True)
            )

            # Surface Finding
            self.sig_status.emit("FINDING SURFACE...")
            surface_z = self._smart_find_surface(params['contact_force'])
            if self.stop_requested: return

            # Calc Physics
            depth = params['depth']
            speed = params['speed']
            hold_t = params['hold_time']

            total_cycles = params['cycles'] + 1
            cycle_dur = (2 * depth / speed) + hold_t
            total_dur = total_cycles * cycle_dur
            start_t = time.perf_counter()

            for c in range(total_cycles):
                if self.stop_requested: break

                is_mullin = (c == 0)
                prefix = "MULLIN" if is_mullin else f"CYCLE_{c}"

                # 1. LOAD (Parallel Move)
                target = surface_z + depth
                self._run_phase_parallel(
                    target, speed, f"{prefix}_LOADING",
                    db, start_t, cols, c, total_cycles, total_dur, rate_hz
                )
                if self.stop_requested: break

                # 2. HOLD (Parallel Wait)
                self._run_hold_parallel(
                    hold_t, f"{prefix}_HOLDING",
                    db, start_t, cols, c, total_cycles, total_dur, rate_hz
                )
                if self.stop_requested: break

                # 3. UNLOAD (Parallel Move)
                self._run_phase_parallel(
                    surface_z, speed, f"{prefix}_UNLOADING",
                    db, start_t, cols, c, total_cycles, total_dur, rate_hz
                )

            self.sig_finished.emit()

        except Exception as e:
            self.sig_error.emit(f"Error: {e}")
        finally:
            if db: db.close()
            if self.sensor_runner: self.sensor_runner.stop()
            if self.load_cell_runner: self.load_cell_runner.stop()
            if self.position_runner: self.position_runner.stop()
            if self._perf:
                self._perf.report()
                self._perf = None
            self.running = False
            if self.stop_requested:
                try:
                    self.motor.move_relative(-2.0, 5.0)
                except:
                    pass

    def _run_phase_parallel(self, target_z, speed, phase, db, start_t, cols, c, tot_c, tot_dur, rate_hz):
        """Spawns motion thread, runs logging loop in the main thread."""
        done_evt = threading.Event()

        def motion_worker():
            try:
                self.motor.move_to_absolute(target_z, velocity=speed)
            except:
                pass
            finally:
                done_evt.set()

        t = threading.Thread(target=motion_worker, daemon=True)
        t.start()

        rate = RateLimiter(rate_hz)
        rate.reset()

        # Logging Loop
        self._emit_loop(lambda: done_evt.is_set(), rate, db, start_t, phase, cols, c, tot_c, tot_dur)

        t.join()

    def _run_hold_parallel(self, duration, phase, db, start_t, cols, c, tot_c, tot_dur, rate_hz):
        end = time.perf_counter() + duration
        rate = RateLimiter(rate_hz)
        rate.reset()
        self._emit_loop(lambda: time.perf_counter() >= end, rate, db, start_t, phase, cols, c, tot_c, tot_dur)

    def _emit_loop(self, stop_check, rate, db, start_t, phase, cols, c, tot_c, tot_dur):
        while not stop_check():
            if self.stop_requested or self._stop_evt.is_set():
                break
            emit_start = time.perf_counter() if self._perf else None
            self._emit(db, start_t, phase, cols, c, tot_c, tot_dur)
            if self._perf and emit_start is not None:
                self._perf.add_timing("emit_s", time.perf_counter() - emit_start)
                self._perf.add_value("log_queue", db.queue_depth() if db else 0)
            late = rate.wait(self._stop_evt)
            if self._perf:
                self._perf.add_timing("sampling_late_s", late)

    def _get_position(self):
        if self.position_runner:
            return self.position_runner.get_latest()
        return self.motor.get_position()

    def _get_force(self):
        if self.load_cell_runner:
            return self.load_cell_runner.get_latest()
        return self.load_cell.read_force()

    def _emit(self, db, start_t, phase, cols, c, tot_c, tot_dur):
        t = time.perf_counter() - start_t
        try:
            pos = self._get_position()
        except Exception:
            pos = 0.0

        try:
            f_raw = self._get_force()
        except Exception:
            f_raw = 0.0
        f_net = f_raw - self.force_offset
        s_data = self.sensor_runner.get_latest() or [0.0] * len(cols)

        if db: db.log([t, pos, f_net, phase] + s_data)

        if self._ui_emit_period <= 0 or (t - self._ui_last_emit) >= self._ui_emit_period:
            self._ui_last_emit = t
            self.sig_packet.emit({
                "t": t, "f": f_net, "s": s_data, "phase": phase,
                "cycle": c, "total_cycles": tot_c, "expected_duration": tot_dur,
                "s_names": cols
            })

    def _smart_find_surface(self, thresh):
        step = 0.1
        trav = 0.0
        last_emit = time.perf_counter()
        while trav < 25.0:
            if self.stop_requested or self._stop_evt.is_set():
                return None
            if self.manual_surface_flag:
                self.sig_status.emit("SURFACE SET (MANUAL)")
                return self._get_position()

            try:
                f = abs(self._get_force() - self.force_offset)
            except Exception:
                f = 0.0
            if f > thresh:
                self.sig_status.emit("SURFACE DETECTED")
                return self._get_position()

            self.motor.move_relative(step, velocity=1.0)
            trav += step
            now = time.perf_counter()
            if now - last_emit >= 0.25:
                self.sig_status.emit(f"FINDING SURFACE... {trav:.1f} mm")
                last_emit = now
            self._stop_evt.wait(0.02)
        raise RuntimeError("Surface not found")
