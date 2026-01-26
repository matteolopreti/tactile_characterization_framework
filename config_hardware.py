# --- SIMULATION SWITCH ---
# True = Use Mock Drivers (Laptop testing)
# False = Use Real Drivers (Hardware connection)
SIMULATION_MODE = False

# --- HARDWARE DEFINITIONS ---
# Grouping settings makes the code hardware-agnostic.
# If you switch to a different motor, you only update this block.

MOTOR_CONFIG = {
    "ip": "10.0.0.100",
    "port": 701
}

DAQ_CONFIG = {
    # NI-DAQmx Device Name (check NI MAX)
    "channel_base": "Dev1/ai",
    # Name of the file inside the 'config/' folder
    "cal_file": "FT58072.cal"
}

SENSOR_CONFIG = {
    # Serial Port (Windows: COMx, Linux: /dev/ttyUSBx)
    "port": "COM4",
    "baud": 12800
}


def get_hardware_components():
    """
    Factory function to initialize hardware.
    Returns: (motor, load_cell, sensor)
    """

    # --- 1. SIMULATION MODE ---
    if SIMULATION_MODE:
        print("[Config] SIMULATION_MODE is True. Loading Mock Drivers...")
        from Drivers.mock_drivers import MockMotionStage, MockLoadCell, MockTactileSensor

        # We pass empty or dummy configs to mocks
        motor = MockMotionStage()
        load_cell = MockLoadCell()
        sensor = MockTactileSensor()

        return motor, load_cell, sensor

    # --- 2. REAL HARDWARE MODE ---
    print("[Config] Loading Real Drivers...")

    # Import locally to avoid import errors if libraries are missing during Sim mode
    from Drivers.acs_stage import ACSMotionStage
    from Drivers.ati_daq import NIDAQLoadCell
    from Drivers.serial_sensor import SerialMagneticSensor

    # Initialize with Dictionary unpacking (**config)
    # This maps 'ip' -> ip, 'port' -> port automatically.
    motor = ACSMotionStage(**MOTOR_CONFIG)

    load_cell = NIDAQLoadCell(
        channel_base=DAQ_CONFIG["channel_base"],
        cal_file=DAQ_CONFIG["cal_file"]
    )

    sensor = SerialMagneticSensor(
        port=SENSOR_CONFIG["port"],
        baud=SENSOR_CONFIG["baud"]
    )

    return motor, load_cell, sensor