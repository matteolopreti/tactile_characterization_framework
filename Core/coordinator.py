import time
import threading
import numpy as np
from PySide6.QtCore import QObject, Signal

# Clean imports (Now works beautifully if you updated core/__init__.py)
from .async_wrapper import AsyncSensorRunner
from .data_logger import DataLogger


class ExperimentCoordinator(QObject):
    # --- PySide6 Signals ---
    sig_status = Signal(str)
    sig_progress = Signal(int)
    sig_data = Signal(dict)
    sig_error = Signal(str)
    sig_finished = Signal()

    def __init__(self, motor, load_cell, sensor_driver):
        super().__init__()
        self.motor = motor
        self.load_cell = load_cell
        self.sensor_driver = sensor_driver

        # Helper objects
        self.sensor_runner = None
        self.logger = None

        # State
        self.running = False
        self.stop_requested = False
        self.thread = None

    def start_experiment(self, params):
        if self.running: return
        self.running = True
        self.stop_requested = False

        # (1) Fix: Assign to self.thread
        self.thread = threading.Thread(target=self._run_protocol, args=(params,), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_requested = True
        self.sig_status.emit("STOP REQUESTED!")

    def _run_protocol(self, params):
        self.logger = DataLogger()

        try:
            # --- 1. INITIALIZATION ---
            self.sig_status.emit("Initializing Hardware...")
            if not self.motor.connected: self.motor.connect()
            if not self.load_cell.connected: self.load_cell.connect()

            # Ensure sensor is connected before wrapping it
            if not self.sensor_driver.connected: self.sensor_driver.connect()

            # Start Async Sensor Thread (Non-blocking reads)
            # We pass the DRIVER INSTANCE, not the class
            self.sensor_runner = AsyncSensorRunner(self.sensor_driver)
            self.sensor_runner.start()

            # Setup Database
            sensor_cols = self.sensor_driver.get_column_names()
            self.logger.start_logging(sensor_columns=sensor_cols)
            self.sig_status.emit(f"Logging to: {self.logger.filepath}")

            # --- 2. SURFACE FINDING ---
            self.sig_status.emit("Finding Surface...")
            surface_z = self._find_surface_routine()
            self.sig_status.emit(f"Surface Found at Z={surface_z:.3f}")
            time.sleep(1.0)

            # --- 3. TRAJECTORY GENERATION ---
            # We use your triangular wave logic
            trajectory = self._generate_triangular_wave(
                start_z=surface_z,
                depth=params['depth'],
                step_size=params.get('step_size', 0.1),
                cycles=params['cycles']
            )

            # --- 4. EXECUTION LOOP ---
            self.sig_status.emit("Starting Cycles...")
            start_time = time.time()
            total_points = len(trajectory)

            for i, (target_z, phase) in enumerate(trajectory):
                if self.stop_requested: break

                # A. MOVE
                # Note: If this is blocking, we wait here. If non-blocking, we proceed.
                # Assuming blocking for step-wise precision.
                self.motor.move_to_absolute(target_z, velocity=params['speed'])

                # B. HOLD (Only sleep if explicitly holding)
                if phase == "HOLDING":
                    # Sleep in small chunks to allow interrupt
                    hold_end = time.time() + params['hold_time']
                    while time.time() < hold_end:
                        if self.stop_requested: break
                        self._emit_data_point(start_time, phase, sensor_cols)
                        time.sleep(0.01)
                else:
                    # For Moving phases, just log the point immediately after move
                    # We removed the hardcoded 'time.sleep(0.1)' to go faster
                    pass

                # C. ACQUIRE & LOG (One point per step)
                self._emit_data_point(start_time, phase, sensor_cols)

                # D. UI PROGRESS
                if i % 5 == 0:  # Throttle UI updates slightly
                    self.sig_progress.emit(int((i / total_points) * 100))

            # --- 5. FINISH ---
            if not self.stop_requested:
                self.sig_status.emit("Retracting...")
                self.motor.move_to_absolute(surface_z + 5.0, velocity=5.0)
                self.sig_finished.emit()

        except (ValueError, RuntimeError, OSError) as e:
            self.sig_error.emit(str(e))
            print(f"Protocol Error: {e}")

        finally:
            # --- CLEANUP ---
            # 1. Stop Logging
            if self.logger:
                self.logger.stop_logging()

            # 2. Stop Sensor Thread
            if self.sensor_runner:
                self.sensor_runner.stop()

            # 3. Safety Retract (If stopped manually)
            if self.stop_requested:
                try:
                    self.motor.move_relative(-2.0, 5.0)
                except:
                    pass

            self.running = False

    def _emit_data_point(self, start_time, phase, sensor_cols):
        """Helper to gather, log, and emit a single data point."""
        t_now = time.time() - start_time
        pos = self.motor.get_position()
        force = self.load_cell.read_force()

        # Get freshest data from Async Runner
        sens_data = self.sensor_runner.get_latest()

        # Handle empty/init state
        if not sens_data or len(sens_data) != len(sensor_cols):
            sens_data = [0.0] * len(sensor_cols)

        # Log to File
        if self.logger:
            self.logger.log_sample(t_now, force, phase, sens_data)

        # Emit to GUI
        self.sig_data.emit({
            "Time": t_now,
            "Force": force,
            "Phase": phase,
            "Sensor": sens_data
        })

    @staticmethod
    def _generate_triangular_wave(start_z, depth, step_size, cycles):
        """
        Generates strict Triangular Wave (Step-wise).
        """
        trajectory = []

        # Create steps relative to 0
        steps_up = np.arange(0, depth, step_size)
        steps_down = np.arange(depth, 0, -step_size)

        # Ensure we hit the exact depth
        if not np.isclose(steps_up[-1], depth):
            steps_up = np.append(steps_up, depth)

        # Ensure we return to 0
        if not np.isclose(steps_down[-1], 0):
            steps_down = np.append(steps_down, 0)
        else:
            steps_down[-1] = 0.0

        for _ in range(cycles):
            # Down (Loading)
            for z_rel in steps_up:
                trajectory.append((start_z + z_rel, "LOADING"))  # Note: +z is usually down into material

            # Hold
            trajectory.append((start_z + depth, "HOLDING"))

            # Up (Unloading)
            for z_rel in steps_down[1:]:  # Skip first point to avoid duplicate
                trajectory.append((start_z + z_rel, "UNLOADING"))

        return trajectory

    def _find_surface_routine(self):
        contact_threshold = 0.4
        max_dist = 20.0
        step = 0.05
        traveled = 0.0

        start_pos = self.motor.get_position()

        while traveled < max_dist:
            if self.stop_requested: raise RuntimeError("Stopped by User")

            # Check Force
            if abs(self.load_cell.read_force()) > contact_threshold:
                return self.motor.get_position()

            # Move Down
            self.motor.move_to_absolute(start_pos + traveled + step, velocity=1.0)
            traveled += step

            # Brief settle
            time.sleep(0.05)

        raise RuntimeError("Surface not found within max distance")