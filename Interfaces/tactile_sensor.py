from abc import ABC, abstractmethod


class ITactileSensor(ABC):
    """
    Abstract Interface for the Device Under Test (Tactile Sensor).
    """

    @abstractmethod
    def connect(self):
        """
        Open serial port, bluetooth connection, or DAQ task.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Close connection.
        """
        pass

    @abstractmethod
    def read_single_sample(self) -> list:
        """
        Read a single data packet (or averaged sample) from the sensor.

        Returns:
            list: A list of floats (e.g. [1.2, 0.5, 3.3]).
            Return None if read fails or times out.
        """
        pass

    @abstractmethod
    def get_column_names(self) -> list:
        """
        Define the CSV/Database headers for this sensor's data.

        Returns:
            list[str]: E.g. ['Coil_A', 'Coil_B', 'Temp_C']
        """
        pass