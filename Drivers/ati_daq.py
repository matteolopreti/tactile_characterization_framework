import sys
import os
import time
import numpy as np

# Path Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from Interfaces.load_cell import ILoadCell

# --- CONDITIONAL IMPORTS ---
# 1. NIDAQMX
DAQ_AVAILABLE = False
try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration, AcquisitionType, READ_ALL_AVAILABLE
    from nidaqmx.errors import DaqError

    DAQ_AVAILABLE = True
except ImportError:
    # Define Dummies for the 'except' block to prevent NameErrors
    nidaqmx = None


    class MockConstants:
        TerminalConfiguration = None
        AcquisitionType = None
        READ_ALL_AVAILABLE = -1


    # Define Dummy Exception
    class DaqError(Exception):
        pass


    # Assign dummies
    TerminalConfiguration = MockConstants
    AcquisitionType = MockConstants
    READ_ALL_AVAILABLE = -1
    print("[DAQ Driver] 'nidaqmx' not found. Simulation Mode.")

# 2. ATI F/T (Calibration Library)
ATI_AVAILABLE = False
try:
    import atiiaftt

    ATI_AVAILABLE = True
except ImportError:
    atiiaftt = None
    print("[DAQ Driver] 'atiiaftt' not found. Raw voltage mode.")


class NIDAQLoadCell(ILoadCell):
    def __init__(self, channel_base="Dev1/ai", cal_file="FT58072.cal"):
        self.channel_base = channel_base
        self.task = None
        self.bias = np.zeros(6)

        # Locate Calibration File
        self.cal_path = os.path.join(parent_dir, "config", cal_file)

        # Initialize FT Sensor Object if library exists
        self.ft_sensor = None
        if ATI_AVAILABLE and os.path.exists(self.cal_path):
            try:
                # 1 indicates the calibration index in the file
                self.ft_sensor = atiiaftt.FTSensor(self.cal_path, 1)
                print(f"[DAQ] Loaded Calibration: {self.cal_path}")
            except (RuntimeError, ValueError) as e:
                print(f"[DAQ] Failed to load calibration: {e}")

    def connect(self):
        if not DAQ_AVAILABLE:
            return

        try:
            self.task = nidaqmx.Task()

            # Add 6 Channels (0-5) for Fx, Fy, Fz, Tx, Ty, Tz
            for i in range(6):
                chan_name = f"{self.channel_base}{i}"
                self.task.ai_channels.add_ai_voltage_chan(
                    chan_name,
                    min_val=-10.0,
                    max_val=10.0
                )

            # Configure Continuous Timing (1kHz)
            self.task.timing.cfg_samp_clk_timing(
                rate=1000,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=100000
            )

            self.task.start()
            print("[DAQ] Task Started (6 Channels).")

        except (DaqError, OSError, ValueError) as conn_err:
            if self.task:
                self.task.close()
                self.task = None
            raise ConnectionError(f"DAQ Open Error: {conn_err}")

    def disconnect(self):
        if self.task:
            try:
                self.task.stop()
                self.task.close()
            except (DaqError, OSError):
                pass
            finally:
                self.task = None

    def zero_bias(self, samples=200):
        if not self.task: return

        print(f"[DAQ] Zeroing Bias ({samples} samples)...")
        data_acc = []
        for _ in range(samples):
            # Read Raw (no bias applied yet)
            raw = self._read_latest_sample(apply_bias=False)
            if raw is not None:
                data_acc.append(raw)
            time.sleep(0.001)

        if data_acc:
            self.bias = np.mean(data_acc, axis=0)
            print(f"[DAQ] New Bias: {self.bias}")

    def _read_latest_sample(self, apply_bias=True):
        """
        Internal: Drains buffer, gets latest 6-axis data.
        Returns np.array([Fx, Fy, Fz, Tx, Ty, Tz]) or None.
        """
        if not DAQ_AVAILABLE or self.task is None:
            # Simulation: Random noise
            return np.random.uniform(-0.05, 0.05, 6)

        try:
            # READ_ALL_AVAILABLE drains the buffer to ensure real-time data
            all_data = self.task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE)

            # Check if we got data (list of lists)
            if all_data and len(all_data[0]) > 0:
                # Take the LAST sample (-1) from each channel
                voltages = [ch_data[-1] for ch_data in all_data]
            else:
                # Fallback: Blocking read of 1 sample if buffer was empty
                temp = self.task.read(number_of_samples_per_channel=1)
                # flatten if necessary
                if isinstance(temp[0], list):
                    voltages = [x[0] for x in temp]
                else:
                    voltages = temp

            # Convert Voltages -> Forces
            if self.ft_sensor:
                forces = self.ft_sensor.convertToFt(voltages)
                forces = np.array(forces)  # [Fx, Fy, Fz, Tx, Ty, Tz]
            else:
                forces = np.array(voltages)

            # Apply Bias
            if apply_bias:
                return forces - self.bias
            else:
                return forces

        except (DaqError, ValueError, OSError):
            # Return None on read failure to prevent crash
            return None

    def read_force(self) -> float:
        """
        ILoadCell Interface Implementation.
        Returns ONLY Fz (Index 2) for the Z-axis test loop.
        """
        data = self._read_latest_sample(apply_bias=True)
        if data is not None:
            return float(data[2])  # Return Fz
        return 0.0

    def read_all_forces(self):
        """
        Extra method to get full 6-axis data if needed.
        """
        return self._read_latest_sample(apply_bias=True)


if __name__ == "__main__":
    driver = NIDAQLoadCell()
    driver.connect()
    # Zero bias before reading
    driver.zero_bias(50)
    print(f"Z-Force Reading: {driver.read_force():.4f} N")
    driver.disconnect()