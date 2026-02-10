import os
import sys

# Set up the path to find interfaces
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from interfaces.motion_stage import IMotionStage

# --- CONDITIONAL IMPORT & MOCKING ---
SP_AVAILABLE = False
try:
    # noinspection PyPep8Naming
    import SPiiPlusPython as sp

    SP_AVAILABLE = True
except ImportError:
    print("[ACS Driver] SPiiPlusPython not found. Running in SIMULATION MODE.")


    # MOCK CLASS (Simulates the Hardware Library)
    class MockSP:
        class Axis:
            ACSC_AXIS_0 = 0

        SYNCHRONOUS = 1

        # noinspection PyPep8Naming, PyUnusedLocal
        @staticmethod
        def OpenCommEthernetTCP(ip, port):
            # Return a fake handle (integer)
            return 1

        # noinspection PyPep8Naming, PyUnusedLocal
        @staticmethod
        def CloseComm(handle):
            pass

        # noinspection PyPep8Naming, PyUnusedLocal
        @staticmethod
        def SetVelocityImm(handle, axis, vel):
            pass

        # noinspection PyPep8Naming, PyUnusedLocal
        @staticmethod
        def ToPoint(handle, flags, axis, target, mode):
            pass

        # noinspection PyPep8Naming, PyUnusedLocal
        @staticmethod
        def GetFPosition(handle, axis):
            return 0.0


    # Alias the mock so the code below uses it transparently
    # noinspection PyPep8Naming
    sp = MockSP()


class ACSMotionStage(IMotionStage):
    PROBE_PRIORITY = 80

    def __init__(self, ip="10.0.0.100", port=701):
        self.ip = ip
        self.port = port
        self.hc = None
        self.connected = False

        # Safe access to constants (Works with Real OR Mock lib)
        self.axis_id_z = sp.Axis.ACSC_AXIS_0
        self.axis_id_y = sp.Axis.ACSC_AXIS_1
        self.axis_id_x = sp.Axis.ACSC_AXIS_2

    @classmethod
    def probe(cls, config=None):
        if not SP_AVAILABLE:
            return False
        config = config or {}
        ip = config.get("ip", "10.0.0.100")
        port = config.get("port", 701)
        try:
            hc = sp.OpenCommEthernetTCP(ip, port)
            sp.CloseComm(hc)
            return True
        except (RuntimeError, OSError):
            return False

    def connect(self):
        try:
            if SP_AVAILABLE:
                print(f"[ACS] Connecting to {self.ip}...")
            else:
                print("[ACS-SIM] Connecting to Mock Controller...")

            self.hc = sp.OpenCommEthernetTCP(self.ip, self.port)
            self.connected = True
            print("[ACS] Connected.")
        except (RuntimeError, OSError) as e:
            self.connected = False
            raise ConnectionError(f"Failed to connect to ACS: {e}")

    def disconnect(self):
        if self.hc is not None:
            try:
                sp.DisableAll(
                    self.hc,
                    sp.SYNCHRONOUS,
                    True
                )
                sp.CloseComm(self.hc)
            except (RuntimeError, OSError):
                pass
            finally:
                self.hc = None
                self.connected = False

    def move_to_absolute(self, z_mm: float, velocity: float):
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            # 1. Set Velocity
            sp.SetVelocityImm(self.hc, self.axis_id_z, velocity)

            # 2. Move (Blocking)
            sp.ToPoint(self.hc, 0, self.axis_id_z, z_mm, sp.SYNCHRONOUS)

        except (RuntimeError, OSError) as e:
            raise RuntimeError(f"ACS Move Error: {e}")

    def move_to_absolute_y(self, y_mm: float, velocity: float):
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            # 1. Set Velocity
            sp.SetVelocityImm(self.hc, self.axis_id_y, velocity)

            # 2. Move (Blocking)
            sp.ToPoint(self.hc, 0, self.axis_id_y, y_mm, sp.SYNCHRONOUS)

        except (RuntimeError, OSError) as e:
            raise RuntimeError(f"ACS Move Y Error: {e}")

    def move_to_absolute_x(self, x_mm: float, velocity: float):
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            # 1. Set Velocity
            sp.SetVelocityImm(self.hc, self.axis_id_x, velocity)

            # 2. Move (Blocking)
            sp.ToPoint(self.hc, 0, self.axis_id_x, x_mm, sp.SYNCHRONOUS)

        except (RuntimeError, OSError) as e:
            raise RuntimeError(f"ACS Move X Error: {e}")

    def move_relative(self, dist_mm: float, velocity: float):
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            sp.SetVelocityImm(self.hc, self.axis_id_z, velocity)

            current = self.get_position()[0]
            target = current + dist_mm

            sp.ToPoint(self.hc, 0, self.axis_id_z, target, sp.SYNCHRONOUS)

        except (RuntimeError, OSError) as e:
            raise RuntimeError(f"ACS Relative Move Error: {e}")

    def move_relative_y(self, dist_mm: float, velocity: float):
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            sp.SetVelocityImm(self.hc, self.axis_id_y, velocity)

            current = self.get_position()[1]
            target = current + dist_mm

            sp.ToPoint(self.hc, 0, self.axis_id_y, target, sp.SYNCHRONOUS)

        except (RuntimeError, OSError) as e:
            raise RuntimeError(f"ACS Relative Move Y Error: {e}")

    def move_relative_x(self, dist_mm: float, velocity: float):
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            sp.SetVelocityImm(self.hc, self.axis_id_x, velocity)

            current = self.get_position()[2]
            target = current + dist_mm

            sp.ToPoint(self.hc, 0, self.axis_id_x, target, sp.SYNCHRONOUS)

        except (RuntimeError, OSError) as e:
            raise RuntimeError(f"ACS Relative Move X Error: {e}")

    def get_position(self) -> list:
        if self.hc is None:
            raise ConnectionError("ACS Controller not connected.")

        try:
            pos = [sp.GetFPosition(self.hc, self.axis_id_z), sp.GetFPosition(self.hc, self.axis_id_y), sp.GetFPosition(self.hc, self.axis_id_x)]
            return list(pos)
        except (RuntimeError, OSError, ValueError) as e:
            raise RuntimeError(f"ACS Position Read Error: {e}")


if __name__ == "__main__":
    # Test the mock logic
    driver = ACSMotionStage()
    driver.connect()
    print(f"Position: {driver.get_position()}")
    driver.move_to_absolute(10.0, 1.0)
    driver.disconnect()
    print("Test Complete.")
