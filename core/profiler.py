import time
import tracemalloc


class RollingStats:
    def __init__(self):
        self.count = 0
        self.total = 0.0
        self.max = 0.0

    def add(self, value):
        if value is None:
            return
        self.count += 1
        self.total += value
        if value > self.max:
            self.max = value

    def mean(self):
        if self.count == 0:
            return 0.0
        return self.total / self.count


class PerfMonitor:
    def __init__(self, enabled=True, enable_memory=True, label=""):
        self.enabled = bool(enabled)
        self.enable_memory = bool(enable_memory) and self.enabled
        self.label = label
        self._stats = {}
        self._start = time.perf_counter()
        self._owns_tracemalloc = False

        if self.enable_memory and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._owns_tracemalloc = True

    def add_timing(self, name, seconds):
        if not self.enabled:
            return
        self._stats.setdefault(name, RollingStats()).add(seconds)

    def add_value(self, name, value):
        if not self.enabled:
            return
        self._stats.setdefault(name, RollingStats()).add(value)

    def report(self):
        if not self.enabled:
            return None

        elapsed = time.perf_counter() - self._start
        parts = [f"[Perf] {self.label}elapsed={elapsed:.2f}s"]

        for key in sorted(self._stats.keys()):
            stats = self._stats[key]
            if stats.count == 0:
                continue
            if key.endswith("_s"):
                mean_ms = stats.mean() * 1000.0
                max_ms = stats.max * 1000.0
                parts.append(f"{key}_ms(mean/max)={mean_ms:.2f}/{max_ms:.2f}")
            else:
                parts.append(f"{key}(mean/max)={stats.mean():.2f}/{stats.max:.2f}")

        if self.enable_memory and tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            parts.append(f"mem_peak_mb={peak / (1024 * 1024):.2f}")
            if self._owns_tracemalloc:
                tracemalloc.stop()

        report = " ".join(parts)
        print(report)
        return report
