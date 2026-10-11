import contextlib
import os
import sqlite3
import sys
import tempfile
import types
import unittest

# core/__init__ needs PySide6 (absent in CI): stub the package, load only data_logger.
_core = types.ModuleType("core")
_core.__path__ = [os.path.join(os.path.dirname(__file__), "..", "core")]
sys.modules.setdefault("core", _core)

from core.data_logger import DataLogger


class SqliteWalTest(unittest.TestCase):
    def test_database_uses_wal(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)  # DataLogger writes under ./data
            try:
                logger = DataLogger(columns=["a"], enable_csv=False)
                db_path = logger.db_path
                logger.close()
                with contextlib.closing(sqlite3.connect(db_path)) as reader:
                    mode = reader.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                os.chdir(old)
        self.assertEqual(mode, "wal")

    def test_rows_visible_to_second_connection_before_close(self):
        self._check_rows_visible_before_close(async_logging=False)

    def test_rows_visible_before_close_async(self):
        # Production path: Coordinator uses async_logging=True.
        self._check_rows_visible_before_close(async_logging=True)

    def _check_rows_visible_before_close(self, async_logging):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                logger = DataLogger(columns=["a"], enable_csv=False,
                                    async_logging=async_logging)
                logger.COMMIT_INTERVAL_S = 0
                logger.log([1.0])
                if async_logging:
                    logger._queue.join()  # wait until the worker wrote and committed
                with contextlib.closing(sqlite3.connect(logger.db_path)) as reader:
                    count = reader.execute("SELECT COUNT(*) FROM data").fetchone()[0]
                logger.close()
            finally:
                os.chdir(old)
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
