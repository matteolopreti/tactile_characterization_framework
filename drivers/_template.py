"""
Driver template. Copy this file and keep only the interface you need.
"""

from interfaces.motion_stage import IMotionStage
from interfaces.load_cell import ILoadCell
from interfaces.tactile_sensor import ITactileSensor


class ExampleStage(IMotionStage):
    PROBE_PRIORITY = 10

    def __init__(self, ip="127.0.0.1", port=1234):
        self.ip = ip
        self.port = port
        self.connected = False

    @classmethod
    def probe(cls, config=None):
        return False

    def connect(self):
        pass

    def disconnect(self):
        pass

    def move_to_absolute(self, z_mm: float, velocity: float):
        pass

    def move_relative(self, dist_mm: float, velocity: float):
        pass

    def get_position(self) -> float:
        return 0.0


class ExampleLoadCell(ILoadCell):
    PROBE_PRIORITY = 10

    def __init__(self, channel_base="Dev1/ai", cal_file="FT00000.cal"):
        self.channel_base = channel_base
        self.cal_file = cal_file
        self.connected = False

    @classmethod
    def probe(cls, config=None):
        return False

    def connect(self):
        pass

    def disconnect(self):
        pass

    def read_force(self) -> float:
        return 0.0


class ExampleTactileSensor(ITactileSensor):
    PROBE_PRIORITY = 10

    def __init__(self, port="COM1", baud=115200):
        self.port = port
        self.baud = baud
        self.connected = False

    @classmethod
    def probe(cls, config=None):
        return False

    def connect(self):
        pass

    def disconnect(self):
        pass

    def read_single_sample(self) -> list:
        return []

    def get_column_names(self) -> list:
        return []
