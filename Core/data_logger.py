# core/data_logger.py
import sqlite3
import csv
import os
from datetime import datetime


class DataLogger:
    def __init__(self, base_filename="experiment", columns=None):
        """
        Handles simultaneous logging to SQLite and CSV.

        Args:
            base_filename (str): Prefix for the file (e.g., "viscoelastic_test")
            columns (list): List of column headers. E.g. ["Time", "Fz", "Pos", "Phase"]
        """
        if not columns:
            raise ValueError("DataLogger requires a list of column names.")

        self.columns = columns

        # 1. Setup Directories
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Generate unique timestamp for this run (ISO-like format safe for filenames)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # 2. Setup CSV (Immediate access)
        self.csv_path = os.path.join(self.data_dir, f"{base_filename}_{timestamp}.csv")
        # newline='' prevents blank lines on Windows systems
        self.csv_file = open(self.csv_path, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(self.columns)  # Write Headers

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

        print(f"[DataLogger] Logging to:\n  CSV: {self.csv_path}\n  DB:  {self.db_path}")

    def log(self, data_list):
        """
        Writes a single row of data.
        Args:
            data_list (list): Values matching the order of 'columns' provided in __init__
        """
        if len(data_list) != len(self.columns):
            print(f"[DataLogger Error] Column Mismatch! Exp: {len(self.columns)}, Got: {len(data_list)}")
            return

        # Write to CSV
        self.csv_writer.writerow(data_list)

        # Write to SQLite
        placeholders = ", ".join(["?"] * len(data_list))
        sql = f"INSERT INTO data VALUES ({placeholders})"
        self.cursor.execute(sql, data_list)

        # Note: We do NOT commit after every insert to maximize speed (500Hz+ capability).
        # Data is committed on self.close().

    def close(self):
        """Safely close files and connections."""
        try:
            if not self.csv_file.closed:
                self.csv_file.flush()
                self.csv_file.close()

            if self.conn:
                self.conn.commit()
                self.conn.close()

            print("[DataLogger] Logs closed successfully.")
        except Exception as e:
            print(f"[DataLogger] Error closing logs: {e}")