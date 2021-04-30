import logging

from pyobs.interfaces import ICameraBinning, ICooling
from .sbigbasecamera import SbigBaseCamera
from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigCamera(SbigBaseCamera, ICameraBinning, ICooling):
    """A pyobs module for SBIG cameras."""
    __module__ = 'pyobs_sbig'

    def __init__(self, setpoint: float = -20, *args, **kwargs):
        """Initializes a new SbigCamera.

        Args:
            setpoint: Cooling temperature setpoint.
        """
        SbigBaseCamera.__init__(self, *args, **kwargs)

        # cooling
        self._setpoint = setpoint

    def open(self):
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        SbigBaseCamera.open(self)

        # cooling
        self.set_cooling(self._setpoint is not None, self._setpoint)

    def get_binning(self, *args, **kwargs) -> Tuple[int, int]:
        """Returns the camera binning.

        Returns:
            Dictionary with x and y.
        """
        return self._binning

    def set_binning(self, x: int, y: int, *args, **kwargs):
        """Set the camera binning.

        Args:
            x: X binning.
            y: Y binning.
        """
        self._binning = (x, y)
        log.info('Setting binning to %dx%d...', x, y)

    def set_cooling(self, enabled: bool, setpoint: float, *args, **kwargs):
        """Enables/disables cooling and sets setpoint.

        Args:
            enabled: Enable or disable cooling.
            setpoint: Setpoint in celsius for the cooling.

        Raises:
            ValueError: If cooling could not be set.
        """

        # log
        if enabled:
            log.info('Enabling cooling with a setpoint of %.2f°C...', setpoint)
        else:
            log.info('Disabling cooling and setting setpoint to 20°C...')

        # do it
        self._driver.camera.set_cooling(enabled, setpoint)

    def get_cooling_status(self, *args, **kwargs) -> Tuple[bool, float, float]:
        """Returns the current status for the cooling.

        Returns:
            Tuple containing:
                Enabled (bool):         Whether the cooling is enabled
                SetPoint (float):       Setpoint for the cooling in celsius.
                Power (float):          Current cooling power in percent or None.
        """

        try:
            enabled, temp, setpoint, _ = self._driver.camera.get_cooling()
            self._cooling = enabled, temp, setpoint
        except ValueError:
            # use existing cooling
            pass
        return self._cooling

    def get_temperatures(self, *args, **kwargs) -> dict:
        """Returns all temperatures measured by this module.

        Returns:
            Dict containing temperatures.
        """

        try:
            _, temp, _, _ = self._driver.camera.get_cooling()
            self._temps = {'CCD': temp}
        except ValueError:
            # use existing temps
            pass
        return self._temps


__all__ = ['SbigCamera']
