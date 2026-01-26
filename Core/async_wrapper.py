import multiprocessing
import time
import queue


class AsyncSensorRunner:
    def __init__(self, driver_class, driver_params):
        """
        Wraps a synchronous hardware driver in a background process.

        Args:
            driver_class (class): The uninstantiated class (e.g., SerialMagneticSensor)
            driver_params (dict): Arguments for the driver (e.g., {'port':'COM4'})
        """
        self.driver_class = driver_class
        self.driver_params = driver_params

        # Communication Queues
        self.data_queue = multiprocessing.Queue()
        self.cmd_queue = multiprocessing.Queue()
        self.process = None

    def start(self):
        """Starts the background process."""
        if self.process is None or not self.process.is_alive():
            self.process = multiprocessing.Process(target=self._worker_loop)
            self.process.start()
            time.sleep(1.0)  # Allow connection stabilization

    def stop(self):
        """Signals shutdown."""
        if self.process and self.process.is_alive():
            self.cmd_queue.put("STOP")
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
                print("[AsyncRunner] Process forced terminated.")

    def get_latest(self):
        """
        Returns the absolute latest sample.
        Drains the queue to ensure zero latency.
        """
        latest_data = None
        try:
            if self.data_queue.empty():
                return None

            # Flush queue, keep only the last item
            while not self.data_queue.empty():
                latest_data = self.data_queue.get_nowait()

            return latest_data

        except queue.Empty:
            return None

    def get_column_names(self):
        """Helper to get column names without starting the process."""
        temp = self.driver_class(**self.driver_params)
        return temp.get_column_names()

    def _worker_loop(self):
        """The isolated process loop."""
        driver = None
        try:
            # 1. Instantiate Driver
            try:
                driver = self.driver_class(**self.driver_params)
                driver.connect()
                print(f"[Async] {self.driver_class.__name__} Connected.")
            except Exception as e:
                print(f"[Async] Connection Failed: {e}")
                return

            # 2. Main Loop
            while True:
                if not self.cmd_queue.empty():
                    if self.cmd_queue.get() == "STOP":
                        break

                try:
                    data = driver.read_single_sample()
                    if data:
                        self.data_queue.put(data)
                except Exception as e:
                    print(f"[Async] Read Error: {e}")
                    time.sleep(1)

        finally:
            # 3. Cleanup (Guaranteed execution)
            if driver:
                try:
                    driver.disconnect()
                    print(f"[Async] {self.driver_class.__name__} Disconnected.")
                except Exception as e:
                    print(f"[Async] Disconnect Error: {e}")