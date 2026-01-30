import time


class RateLimiter:
    def __init__(self, rate_hz):
        if rate_hz <= 0:
            raise ValueError("rate_hz must be > 0")
        self._rate_hz = float(rate_hz)
        self._period = 1.0 / self._rate_hz
        self._next_time = time.perf_counter()

    def set_rate(self, rate_hz):
        if rate_hz <= 0:
            raise ValueError("rate_hz must be > 0")
        self._rate_hz = float(rate_hz)
        self._period = 1.0 / self._rate_hz
        self._next_time = time.perf_counter()

    def reset(self):
        self._next_time = time.perf_counter()

    def wait(self, stop_event=None):
        self._next_time += self._period
        now = time.perf_counter()
        delay = self._next_time - now
        if delay > 0:
            if stop_event is None:
                time.sleep(delay)
            else:
                stop_event.wait(delay)
            return 0.0
        self._next_time = now
        return -delay
