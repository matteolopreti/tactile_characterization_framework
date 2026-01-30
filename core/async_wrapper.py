import threading

from .timing import RateLimiter


class AsyncSensorRunner:
    def __init__(self, sensor_driver, max_rate_hz=None):
        """
        Wraps an existing sensor driver to read in a background thread.
        Args:
            sensor_driver: An initialized and connected driver instance (e.g., SerialMagneticSensor)
        """
        self.driver = sensor_driver
        self.latest_data = []
        self.running = False
        self._lock = threading.Lock()
        self._thread = None
        self._stop_evt = threading.Event()
        self._rate = RateLimiter(max_rate_hz) if max_rate_hz else None

    def start(self):
        if self.running: return
        self.running = True
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def set_max_rate(self, max_rate_hz):
        if max_rate_hz:
            if self._rate is None:
                self._rate = RateLimiter(max_rate_hz)
            else:
                self._rate.set_rate(max_rate_hz)
        else:
            self._rate = None

    def _worker_loop(self):
        """
        Continuously reads from the driver.
        """
        if self._rate:
            self._rate.reset()
        while self.running and not self._stop_evt.is_set():
            try:
                # Blocks here until serial data arrives (efficient)
                data = self.driver.read_single_sample()

                if data is not None:
                    with self._lock:
                        self.latest_data = data
                else:
                    # If read timed out or returned None, sleep briefly
                    self._stop_evt.wait(0.001)

            except Exception as e:
                # Prevent a loop crash on transient error
                print(f"[Async] Loop Error: {e}")
                self._stop_evt.wait(0.1)
                continue

            if self._rate:
                self._rate.wait(self._stop_evt)

    def get_latest(self):
        """Returns the most recent sample immediately (Non-blocking)."""
        with self._lock:
            # Return copy to avoid race conditions
            return list(self.latest_data) if self.latest_data else []

    def get_column_names(self):
        """Pass-through to the driver."""
        return self.driver.get_column_names()


class AsyncValuePoller:
    def __init__(self, read_fn, default=None, rate_hz=50.0, name="poller"):
        self._read_fn = read_fn
        self._default = default
        self._name = name
        self._latest = default
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread = None
        self._rate = RateLimiter(rate_hz)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def set_rate(self, rate_hz):
        self._rate.set_rate(rate_hz)

    def _worker_loop(self):
        self._rate.reset()
        while not self._stop_evt.is_set():
            try:
                value = self._read_fn()
                if value is not None:
                    with self._lock:
                        self._latest = value
            except Exception as e:
                print(f"[Async:{self._name}] Loop Error: {e}")
            self._rate.wait(self._stop_evt)

    def get_latest(self):
        with self._lock:
            return self._latest if self._latest is not None else self._default
