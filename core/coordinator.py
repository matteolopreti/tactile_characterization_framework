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
        self.force_offset = [0.0] * 6  # 6-element offset for [Fx, Fy, Fz, Tx, Ty, Tz]
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
            # Read all 6 force/torque values for bias offset
            if hasattr(self.load_cell, 'read_all_forces'):
                try:
                    all_forces = self.load_cell.read_all_forces()
                    if all_forces is not None:
                        self.force_offset = list(all_forces)[:6]
                        if len(self.force_offset) < 6:
                            self.force_offset += [0.0] * (6 - len(self.force_offset))
                    else:
                        self.force_offset = [0.0] * 6
                except Exception:
                    self.force_offset = [0.0] * 6
            else:
                # Fallback: get only Fz
                try:
                    fz = self.load_cell.read_force()
                    self.force_offset = [0.0, 0.0, float(fz), 0.0, 0.0, 0.0]
                except Exception:
                    self.force_offset = [0.0] * 6
            offset_str = ", ".join(f"{f:.2f}" for f in self.force_offset)
            info['load_cell'] = f"OK (Offset: [{offset_str}] N)"
            if not self.sensor_driver.connected: self.sensor_driver.connect()
            else: # reconnect to refresh
                self.sensor_driver.disconnect()
                self.sensor_driver.connect()
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
        self.force_offset = [0.0] * 6
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
        self.sig_status.emit("STOP REQUESTED")
        return True

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
            # The emitter writes three position components (z,y,x) and six force/torque
            # components (Fx, Fy, Fz, Tx, Ty, Tz), so create matching headers.
            header = ["Time", "Pos_Z", "Pos_Y", "Pos_X", "Fx", "Fy", "Fz", "Tx", "Ty", "Tz", "Phase"] + cols
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
            horizontal_range = params['horizontal_range']
            speed = params['speed']
            hold_t = params['hold_time']

            total_cycles = params['cycles'] + 1
            dur = depth/speed
            cycle_dur = (2 * depth / speed) + hold_t
            total_dur = total_cycles * cycle_dur
            start_t = time.perf_counter()

            for c in range(total_cycles):
                if self.stop_requested: break

                is_mullin = (c == 0)
                prefix = "MULLIN" if is_mullin else f"CYCLE_{c}"

                # 1. LOAD (Parallel Move)
                target = surface_z - depth
                self._run_phase_parallel(
                    target, speed, f"{prefix}_LOADING",
                    db, start_t, cols, c, total_cycles, total_dur, rate_hz, dur
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
                    db, start_t, cols, c, total_cycles, total_dur, rate_hz, dur
                )

            self.sig_finished.emit()
            self.motor.move_to_absolute(surface_z + 5.0, velocity=5.0)
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
            if self.stop_requested:# emergency stop,try to back off a bit
                try:
                    self.motor.move_relative(5, 5.0)# move up a bit on stop,upward is positive
                except:
                    pass

    def _run_phase_parallel(
            self,
            target_z,
            speed,
            phase,
            db,
            start_t,
            cols,
            c,
            tot_c,
            tot_dur,
            rate_hz,
            duration
    ):
        done_evt = threading.Event()

        def motion_worker():
            """
            carries out the motor movement in a separate thread
            """
            try:
                self.motor.move_to_absolute(
                    target_z,
                    velocity=speed
                )
            except Exception:
                pass
            finally:
                done_evt.set()


        t = threading.Thread(
            target=motion_worker,
            daemon=True
        )
        t.start()

        # main thread: emit while motion not done
        rate = RateLimiter(rate_hz)
        rate.reset()
        end_time = time.perf_counter() + duration

        while (
                time.perf_counter() < end_time
                and not self.stop_requested
                and not self._stop_evt.is_set()
        ):
            self._emit(
                db,
                start_t,
                phase,
                cols,
                c,
                tot_c,
                tot_dur
            )

            rate.wait(self._stop_evt)

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
        """Return a 3-element list [z, y, x].

        The motor driver may return a single float (Z only) or an iterable
        (e.g. [z, y, x]). The async poller likewise may store a float.
        Coerce any numeric or iterable return into a list of three floats so
        callers can safely index pos[0], pos[1], pos[2].
        """
        def _coerce(v):
            # None -> zeros
            if v is None:
                return [0.0, 0.0, 0.0]

            # Numeric scalar -> Z only
            if isinstance(v, (int, float)):
                return [float(v), 0.0, 0.0]

            # Try to treat as iterable
            try:
                seq = list(v)
            except Exception:
                # Fallback to zeros
                return [0.0, 0.0, 0.0]

            # Convert elements to floats where possible
            out = []
            for i in range(3):
                try:
                    out.append(float(seq[i]))
                except Exception:
                    out.append(0.0)
            return out

        if self.position_runner:
            return _coerce(self.position_runner.get_latest())
        return _coerce(self.motor.get_position())

    def _get_force(self):
        """Return all 6 force/torque values [Fx, Fy, Fz, Tx, Ty, Tz].

        Calls read_all_forces() on the load_cell driver if available,
        otherwise falls back to a tuple with Fz only.
        """
        # Try to get all 6 force/torque values from the driver
        if hasattr(self.load_cell, 'read_all_forces'):
            try:
                forces = self.load_cell.read_all_forces()
                if forces is not None:
                    # Ensure it's a list-like of 6 floats
                    try:
                        forces_list = list(forces)
                        if len(forces_list) >= 6:
                            return [float(forces_list[i]) for i in range(6)]
                        else:
                            # Pad with zeros if fewer than 6
                            return [float(forces_list[i]) if i < len(forces_list) else 0.0 for i in range(6)]
                    except (TypeError, ValueError):
                        return [0.0] * 6
            except Exception:
                pass

        # Fallback: get only Fz from read_force() and return zeros for other axes
        try:
            fz = self.load_cell.read_force()
            return [0.0, 0.0, float(fz), 0.0, 0.0, 0.0]  # [Fx, Fy, Fz, Tx, Ty, Tz]
        except Exception:
            return [0.0] * 6

    def _emit(self, db, start_t, phase, cols, c, tot_c, tot_dur):
        t = time.perf_counter() - start_t
        try:
            pos = self._get_position()
        except Exception:
            pos = [0.0, 0.0, 0.0]

        try:
            forces = self._get_force()  # Returns [Fx, Fy, Fz, Tx, Ty, Tz]
        except Exception:
            forces = [0.0] * 6

        # Ensure forces is a list of 6 elements
        if not isinstance(forces, (list, tuple)):
            forces = [0.0] * 6
        else:
            try:
                forces = list(forces)
                if len(forces) < 6:
                    forces += [0.0] * (6 - len(forces))
                elif len(forces) > 6:
                    forces = forces[:6]
            except Exception:
                forces = [0.0] * 6

        # Subtract force_offset (6 elements) to get net forces
        net_forces = [0.0] * 6
        try:
            if isinstance(self.force_offset, (list, tuple)):
                fo = list(self.force_offset)
                if len(fo) < 6:
                    fo += [0.0] * (6 - len(fo))
            else:
                fo = [0.0] * 6
            for i in range(6):
                try:
                    net_forces[i] = float(forces[i]) - float(fo[i])
                except Exception:
                    net_forces[i] = 0.0
        except Exception:
            net_forces = [0.0] * 6

        # Ensure sensor data is a list with exactly len(cols) elements to
        # prevent column mismatch when logging.
        s_data = self.sensor_runner.get_latest() or [0.0] * len(cols)
        # Normalize to list
        if not isinstance(s_data, (list, tuple)):
            try:
                s_data = list(s_data)
            except Exception:
                s_data = [s_data]
        s_data = list(s_data)
        if len(s_data) < len(cols):
            s_data += [0.0] * (len(cols) - len(s_data))
        elif len(s_data) > len(cols):
            s_data = s_data[:len(cols)]

        # Log net forces: [Time, Pos_Z, Pos_Y, Pos_X, Fx, Fy, Fz, Tx, Ty, Tz, Phase] + sensor_data
        if db:
            db.log([t, pos[0], pos[1], pos[2], net_forces[0], net_forces[1], net_forces[2], net_forces[3], net_forces[4], net_forces[5], phase] + s_data)

        if self._ui_emit_period <= 0 or (t - self._ui_last_emit) >= self._ui_emit_period:
            self._ui_last_emit = t
            self.sig_packet.emit({
                "t": t,
                # Net forces (offset subtracted): [Fx, Fy, Fz, Tx, Ty, Tz]
                "forces": net_forces,
                # Single Fz value (net) used by the GUI's plotting code
                "fz": net_forces[2],
                # Backwards-compatible key expected by GUI ingest_packet
                "f": net_forces[2],
                "s": s_data,
                "phase": phase,
                "cycle": c,
                "total_cycles": tot_c,
                "expected_duration": tot_dur,
                "s_names": cols
            })

    def _smart_find_surface(self, thresh):
        step = 0.1
        trav = 0.0
        last_emit = time.perf_counter()
        self.motor.move_relative(5.0, velocity=2.0)
        self._stop_evt.wait(4.0)
        while trav < 25.0:
            if self.stop_requested or self._stop_evt.is_set():
                return None
            if self.manual_surface_flag:
                self.sig_status.emit("SURFACE SET (MANUAL)")
                # Return Z coordinate only
                pos = self._get_position()
                return float(pos[0])

            try:
                forces = self._get_force()  # Returns [Fx, Fy, Fz, Tx, Ty, Tz]
                if isinstance(forces, (list, tuple)) and len(forces) > 2:
                    # Ensure force_offset is also a list and subtract Fz component
                    if isinstance(self.force_offset, (list, tuple)) and len(self.force_offset) > 2:
                        f = abs(forces[2] - self.force_offset[2])  # Use Fz (index 2)
                    else:
                        f = abs(forces[2])
                else:
                    f = 0.0
            except Exception:
                f = 0.0
            if f > thresh:
                self.sig_status.emit("SURFACE DETECTED")
                pos = self._get_position()
                return float(pos[0])

            self.motor.move_relative(-step, velocity=1.0)
            self._stop_evt.wait(0.2)
            trav += step
            now = time.perf_counter()
            if now - last_emit >= 0.25:
                self.sig_status.emit(f"FINDING {trav:.1f} mm{f:.3f} N")
                last_emit = now
            self._stop_evt.wait(0.02)
        raise RuntimeError("Surface not found")
