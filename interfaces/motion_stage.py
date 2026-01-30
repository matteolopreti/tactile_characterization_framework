from abc import ABC, abstractmethod


class IMotionStage(ABC):
    """
    Abstract Interface for Motion Controllers (Z-Axis).
    All units must be in Millimeters (mm).
    """

    @abstractmethod
    def connect(self):
        """
        Open connection to the hardware controller.
        Raises: ConnectionError if failed.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Cleanly close connection and release resources.
        """
        pass

    @abstractmethod
    def move_to_absolute(self, z_mm: float, velocity: float):
        """
        Blocking move to an absolute Z position.

        Args:
            z_mm (float): Target position in mm.
            velocity (float): Speed in mm/s.
        """
        pass

    @abstractmethod
    def move_relative(self, dist_mm: float, velocity: float):
        """
        Blocking move relative to the current position.

        Args:
            dist_mm (float): Distance to move (positive or negative) in mm.
            velocity (float): Speed in mm/s.
        """
        pass

    @abstractmethod
    def get_position(self) -> float:
        """
        Get the current Z position.

        Returns:
            float: Position in mm.
        """
        pass
