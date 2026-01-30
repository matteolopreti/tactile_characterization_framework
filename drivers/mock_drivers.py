import math
import os
import random
import sys
import time
from typing import Optional

# Path Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from interfaces.motion_stage import IMotionStage
from interfaces.tactile_sensor import ITactileSensor
from interfaces.load_cell import ILoadCell


class MockMotionStage(IMotionStage):
    PROBE_PRIORITY = -100

    def __init__(self, ip="127.0.0.1", port=9999):
        self.z_pos = 0.0
        self.connected = False

    @classmethod
    def probe(cls, config=None):
        return True

    def connect(self):
        print("[MockMotion] Connecting...")
        time.sleep(0.5)
        self.connected = True
        print("[MockMotion] Connected.")

    def disconnect(self):
        self.connected = False
        print("[MockMotion] Disconnected.")

    def move_to_absolute(self, z_mm: float, velocity: float):
        if not self.connected:
            raise ConnectionError("Mock Motion not connected")

        dist = abs(self.z_pos - z_mm)
        if velocity <= 0: velocity = 1.0
        duration = dist / velocity
        time.sleep(duration)
        self.z_pos = z_mm

    def move_relative(self, dist_mm: float, velocity: float):
        target = self.z_pos + dist_mm
        self.move_to_absolute(target, velocity)

    def get_position(self) -> float:
        return self.z_pos


class MockTactileSensor(ITactileSensor):
    PROBE_PRIORITY = -100

    def __init__(self, port="MockPort", baud=0):
        self.connected = False
        self.start_time = 0.0

    @classmethod
    def probe(cls, config=None):
        return True

    def connect(self):
        print("[MockSensor] Connecting...")
        time.sleep(0.2)
        self.connected = True
        self.start_time = time.time()
        print("[MockSensor] Connected.")

    def disconnect(self):
        self.connected = False
        print("[MockSensor] Disconnected.")

    def read_single_sample(self) -> Optional[list]:
        if not self.connected:
            return None

        t = time.time() - self.start_time
        v1 = math.sin(t * 2.0)
        v2 = math.cos(t * 2.5) * 0.5
        v3 = math.sin(t * 0.5) + 1.0
        v1 += random.uniform(-0.05, 0.05)

        return [v1, v2, v3]

    def get_column_names(self) -> list:
        return ["Sim_Sine_A", "Sim_Cos_B", "Sim_Slow_C"]


class MockLoadCell(ILoadCell):
    PROBE_PRIORITY = -100

    def __init__(self, channel="MockChannel"):
        self.connected = False
        self.sim_force = 0.0

    @classmethod
    def probe(cls, config=None):
        return True

    def connect(self):
        print("[MockLoadCell] Connecting...")
        self.connected = True
        print("[MockLoadCell] Connected.")

    def disconnect(self):
        self.connected = False
        print("[MockLoadCell] Disconnected.")

    def read_force(self) -> float:
        if not self.connected:
            return 0.0
        return self.sim_force + random.uniform(-0.02, 0.02)
