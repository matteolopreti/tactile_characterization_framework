import math
import os
import sys
import time
import types
import unittest

# CI has no PySide6 and core/__init__ imports it: stub both.
_qt = types.ModuleType("PySide6.QtCore")
_qt.QObject, _qt.Signal, _qt.QCoreApplication = object, lambda *a, **k: None, object
sys.modules.setdefault("PySide6", types.ModuleType("PySide6"))
sys.modules.setdefault("PySide6.QtCore", _qt)
_core = types.ModuleType("core")
_core.__path__ = [os.path.join(os.path.dirname(__file__), "..", "core")]
sys.modules.setdefault("core", _core)

from core.coordinator import ExperimentCoordinator


class StubRunner:
    def __init__(self, frame):
        self.frame = frame  # (data, seq, arrival_t)

    def get_latest_stamped(self):
        return self.frame

    def get_latest(self):
        return self.frame[0]


class StubDb:
    def __init__(self):
        self.rows = []

    def log(self, row):
        self.rows.append(row)


def make_coord(runner):
    c = object.__new__(ExperimentCoordinator)
    c.sensor_runner = runner
    c.position_runner = types.SimpleNamespace(get_latest=lambda: 1.0)
    c.load_cell_runner = types.SimpleNamespace(get_latest=lambda: 2.0)
    c.force_offset = 0.0
    c._ui_emit_period, c._ui_last_emit = 0.0, 0.0
    c.sig_packet = types.SimpleNamespace(emit=lambda d: None)
    return c


class EmitTest(unittest.TestCase):
    def test_before_first_frame_is_nan_not_zero(self):
        db = StubDb()
        make_coord(StubRunner(([], 0, None)))._emit(db, time.perf_counter(), "P", ["a", "b"], 0, 1, 1.0)
        row = db.rows[0]
        self.assertEqual(len(row), 4 + 2 + 2)
        self.assertTrue(all(math.isnan(v) for v in row[4:7]))  # a, b, sensor_t_s
        self.assertEqual(row[7], 0)

    def test_columns_order_and_sensor_time_not_after_time(self):
        db = StubDb()
        start = time.perf_counter()
        arr = start + 0.001
        time.sleep(0.005)
        make_coord(StubRunner(([5.0, 6.0], 7, arr)))._emit(db, start, "P", ["a", "b"], 0, 1, 1.0)
        t, pos, f, phase, a, b, s_t, seq = db.rows[0]
        self.assertEqual((pos, f, phase, a, b, seq), (1.0, 2.0, "P", 5.0, 6.0, 7))
        self.assertAlmostEqual(s_t, 0.001, places=6)
        self.assertLessEqual(s_t, t)


if __name__ == "__main__":
    unittest.main()
