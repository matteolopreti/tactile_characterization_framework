import os
import sys
import time
import types
import unittest

# core/__init__ imports PySide6 (not installed in CI); bind a bare 'core' package instead.
_core = types.ModuleType("core")
_core.__path__ = [os.path.join(os.path.dirname(__file__), "..", "core")]
sys.modules.setdefault("core", _core)

from core.async_wrapper import AsyncSensorRunner


class FakeDriver:
    """Yields frames [1], [2], [3] at ~50 ms intervals, None in between."""

    def __init__(self):
        self.frame_times = []
        self._t0 = time.perf_counter() + 0.1  # first frame after 100 ms
        self._n = 0

    def read_single_sample(self):
        time.sleep(0.002)
        due = self._t0 + 0.05 * self._n
        if self._n < 3 and time.perf_counter() >= due:
            self._n += 1
            self.frame_times.append(time.perf_counter())
            return [float(self._n)]
        return None

    def get_column_names(self):
        return ["a"]


class SensorStampingTest(unittest.TestCase):
    def test_stamps_and_sequence(self):
        drv = FakeDriver()
        runner = AsyncSensorRunner(drv)
        runner.start()
        try:
            data, seq, t = runner.get_latest_stamped()
            self.assertEqual((data, seq, t), ([], 0, None))  # nothing fabricated
            seen = {}
            deadline = time.perf_counter() + 1.0
            while len(seen) < 3 and time.perf_counter() < deadline:
                data, seq, t = runner.get_latest_stamped()
                if seq:
                    seen[seq] = (data, t)
                time.sleep(0.001)
            self.assertEqual(sorted(seen), [1, 2, 3])
            for seq, (data, t) in seen.items():
                self.assertEqual(data, [float(seq)])
                self.assertAlmostEqual(t, drv.frame_times[seq - 1], delta=0.010)  # 2 ms on a quiet host; 10 ms tolerates CI thread preemption, still << 50 ms frame spacing
            time.sleep(0.05)  # no new frame: repeated read keeps the same seq
            self.assertEqual(runner.get_latest_stamped()[1], 3)
            self.assertEqual(runner.get_latest_stamped()[1], 3)
        finally:
            runner.stop()


if __name__ == "__main__":
    unittest.main()
