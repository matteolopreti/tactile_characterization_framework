from abc import ABC, abstractmethod


class ILoadCell(ABC):
    """
    Abstract Interface for Force Sensors / Load Cells.
    Units must be in Newtons (N).
    """

    @abstractmethod
    def connect(self):
        """
        Prepare the DAQ task or Serial connection.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Release the DAQ task or connection.
        """
        pass

    @abstractmethod
    def read_force(self) -> float:
        """
        Get the current Z-axis force.

        Returns:
            float: Force in Newtons (N).
        """
        pass