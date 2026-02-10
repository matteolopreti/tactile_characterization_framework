# core/data_logger.py
import csv
import os
import queue
import sqlite3
import threading
from datetime import datetime


class DataLogger:
    def __init__(
            self,
            base_filename="experiment",
            columns=None,
            async_logging=False,
            queue_max=10000,
            enable_csv=True,
            enable_sqlite=True
    ):
        """
        Handles simultaneous logging to SQLite and CSV.

        Args:
            base_filename (str): Prefix for the file (e.g., "viscoelastic_test")
            columns (list): List of column headers. E.g. ["Time", "Fz", "Pos", "Phase"]
            async_logging (bool): If True, writes are queued to a background thread.
            queue_max (int): Max queued rows before dropping new data.
            enable_csv (bool): Enable CSV output.
            enable_sqlite (bool): Enable SQLite output.
        """
        if not columns:
            raise ValueError("DataLogger requires a list of column names.")

        self.columns = columns
        self.async_logging = async_logging
        self.enable_csv = bool(enable_csv)
        self.enable_sqlite = bool(enable_sqlite)
        self._queue = None
        self._worker = None
        self._dropped_rows = 0
        self.csv_file = None
        self.csv_writer = None
        self.conn = None
        self.cursor = None
        self.data_dir = None

        if not self.enable_csv and not self.enable_sqlite:
            print("[DataLogger] Logging disabled.")
            return

        # 1. Setup Directories
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Generate a unique timestamp for this run (ISO-like format safe for filenames)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if self.enable_csv:
            # 2. Setup CSV (Immediate access)
            self.csv_path = os.path.join(self.data_dir, f"{base_filename}_{timestamp}.csv")
            # newline='' prevents blank lines on Windows systems
            self.csv_file = open(self.csv_path, mode='w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(self.columns)  # Write Headers

        if self.enable_sqlite:
            # 3. Setup SQLite (Robust storage)
            self.db_path = os.path.join(self.data_dir, f"{base_filename}_{timestamp}.db")
            # check_same_thread=False allows the Coordinator thread to use this connection
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()

            # Create Table Dynamically
            # Optimization: We assume 'Phase' is TEXT, all others are REAL (floats).
            # This covers 99% of sensor characterization needs.
            cols_sql = []
            for col in self.columns:
                if col == "Phase":
                    cols_sql.append(f"'{col}' TEXT")
                else:
                    cols_sql.append(f"'{col}' REAL")

            cols_sql_str = ", ".join(cols_sql)
            self.cursor.execute(f"CREATE TABLE IF NOT EXISTS data ({cols_sql_str})")
            self.conn.commit()

        # csv_path and db_path attributes for user access
        if self.enable_csv or self.enable_sqlite:
            csv_path = getattr(self, "csv_path", None)
            db_path = getattr(self, "db_path", None)
            print(f"[DataLogger] Logging to:\n  CSV: {csv_path}\n  DB:  {db_path}")

        if self.async_logging:
            self._queue = queue.Queue(maxsize=queue_max)
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

    def log(self, data_list):
        """
        Writes a single row of data.
        Args:
            data_list (list): Values matching the order of 'columns' provided in __init__
        """
        if len(data_list) != len(self.columns):
            print(f"[DataLogger Error] Column Mismatch! Exp: {len(self.columns)}, Got: {len(data_list)}")
            return
        if not self.enable_csv and not self.enable_sqlite:
            return

        if self.async_logging:
            try:
                self._queue.put_nowait(list(data_list))
            except queue.Full:
                self._dropped_rows += 1
            return

        self._write_row(data_list)

    def _write_row(self, data_list):
        # Write to CSV
        if self.enable_csv and self.csv_writer:
            self.csv_writer.writerow(data_list)

        # Write to SQLite
        if self.enable_sqlite and self.cursor:
            placeholders = ", ".join(["?"] * len(data_list))
            sql = f"INSERT INTO data VALUES ({placeholders})"
            self.cursor.execute(sql, data_list)

        # Note: We do NOT commit after every insert to maximize speed (500Hz+ capability).
        # Data is committed on self.close().

    def _worker_loop(self):
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                self._write_row(item)
            except Exception as e:
                print(f"[DataLogger] Async write error: {e}")
            finally:
                self._queue.task_done()

    def close(self):
        """Safely close files and connections."""
        try:
            if self.async_logging and self._queue:
                self._queue.put(None)
                self._queue.join()
                if self._worker and self._worker.is_alive():
                    self._worker.join(timeout=1.0)
                if self._dropped_rows:
                    print(f"[DataLogger] Dropped {self._dropped_rows} rows due to full queue.")

            if self.csv_file and not self.csv_file.closed:
                self.csv_file.flush()
                self.csv_file.close()

            if self.conn:
                self.conn.commit()
                self.conn.close()

            print("[DataLogger] Logs closed successfully.")
        except Exception as e:
            print(f"[DataLogger] Error closing logs: {e}")

    def queue_depth(self):
        if not self.async_logging or not self._queue:
            return 0
        return self._queue.qsize()
