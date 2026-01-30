import os
import statistics
import sys
import time
from typing import Optional

# Path Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from interfaces.tactile_sensor import ITactileSensor

try:
    import serial
except ImportError:
    serial = None
    print("[Serial Driver] 'pyserial' not found. Driver will fail.")


class SerialMagneticSensor(ITactileSensor):
    PROBE_PRIORITY = 60

    def __init__(self, port="COM4", baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.num_channels = None  # Will be detected at startup
        self.column_names = []
        self.connected = False

    @classmethod
    def probe(cls, config=None):
        if not serial:
            return False
        try:
            from serial.tools import list_ports
            ports = [p.device for p in list_ports.comports()]
            if not ports:
                return False
            config = config or {}
            target = config.get("port")
            if target:
                return target in ports
            return True
        except Exception:
            return False

    @classmethod
    def probe_port(cls, port, config=None):
        if not serial:
            return False
        config = config or {}
        baud = config.get("baud", 115200)
        ser = None
        try:
            ser = serial.Serial(port, baud, timeout=0.2, write_timeout=0.2)
            time.sleep(0.2)
            ser.reset_input_buffer()
            for _ in range(5):
                line = ser.readline()
                if not line:
                    continue
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                parts = text.split(',')
                try:
                    [float(p) for p in parts]
                except ValueError:
                    continue
                return True
        except (OSError, ValueError):
            return False
        finally:
            if ser and ser.is_open:
                try:
                    ser.close()
                except (OSError, ValueError):
                    pass
        return False

    def connect(self):
        if not serial:
            raise ImportError("pyserial library is missing.")

        try:
            print(f"[Serial] Opening {self.port} @ {self.baud}...")
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
            time.sleep(2.0)  # Wait for MCU reset
            self.ser.reset_input_buffer()
            self.connected = True

            # --- AUTO-DETECT CONFIGURATION ---
            if self.num_channels is None:
                self._detect_channel_count()

        except (OSError, ValueError) as conn_err:
            self.connected = False
            raise ConnectionError(f"Serial Open Error: {conn_err}")

    def disconnect(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except (OSError, ValueError):
                pass
        self.connected = False

    def _detect_channel_count(self):
        """
        Reads 100 samples to statistically determine the number of channels.
        """
        print("[Serial] Auto-detecting number of channels...")
        counts = []
        max_attempts = 150

        for _ in range(max_attempts):
            line = self.ser.readline()
            if not line: continue

            try:
                text = line.decode("utf-8", errors="ignore").strip()
                if not text: continue
                parts = text.split(',')
                # Check if parts are numbers
                [float(p) for p in parts]
                counts.append(len(parts))
            except ValueError:
                continue

            if len(counts) >= 100:
                break

        if not counts:
            raise RuntimeError("Could not detect channels: No valid data received.")

        self.num_channels = statistics.mode(counts)
        print(f"[Serial] Detected {self.num_channels} Channels (Mode of {len(counts)} samples).")

        self.column_names = [f"Ch_{i}" for i in range(self.num_channels)]

    def read_single_sample(self) -> Optional[list]:
        if not self.ser or self.num_channels is None:
            return None

        try:
            line = self.ser.readline()
            if not line: return None

            text = line.decode("utf-8", errors="ignore").strip()
            if not text: return None

            parts = text.split(',')

            if len(parts) != self.num_channels:
                return None

            return [float(p) for p in parts]

        except (ValueError, OSError):
            return None

    def get_column_names(self) -> list:
        if self.column_names:
            return self.column_names

        was_open = (self.ser is not None and self.ser.is_open)

        if not was_open:
            try:
                self.connect()  # Triggers detection
                names = self.column_names[:]
                self.disconnect()
                return names
            except Exception as detect_err:
                print(f"[Serial] Detection failed: {detect_err}")
                return ["Error_Detecting_Channels"]
        else:
            return self.column_names


if __name__ == "__main__":
    if serial:
        print("Driver loaded. Attempting auto-detect on COM4...")
        try:
            drv = SerialMagneticSensor(port="COM4")
            cols = drv.get_column_names()
            print(f"Result: {cols}")
        except Exception as test_err:
            print(f"Test failed: {test_err}")
    else:
        print("Serial driver requires pyserial.")
