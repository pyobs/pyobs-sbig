import logging
from typing import Any, Dict

from pyobs.interfaces import IBinning, ICooling
from .sbigbasecamera import SbigBaseCamera
from .sbigudrv import *

log = logging.getLogger(__name__)


class SbigCamera(SbigBaseCamera, IBinning, ICooling):
    """A pyobs module for SBIG cameras."""
    __module__ = 'pyobs_sbig'

    def __init__(self, setpoint: float = -20, **kwargs: Any):
        """Initializes a new SbigCamera.

        Args:
            setpoint: Cooling temperature setpoint.
        """
        SbigBaseCamera.__init__(self, **kwargs)

        # cooling
        self._setpoint = setpoint
        self._cooling = None

    async def open(self) -> None:
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        await SbigBaseCamera.open(self)

        # cooling
        await self.set_cooling(self._setpoint is not None, self._setpoint)

    async def get_binning(self, **kwargs: Any) -> Tuple[int, int]:
        """Returns the camera binning.

        Returns:
            Dictionary with x and y.
        """
        return self._binning

    async def set_binning(self, x: int, y: int, **kwargs: Any) -> None:
        """Set the camera binning.

        Args:
            x: X binning.
            y: Y binning.
        """
        self._binning = (x, y)
        log.info('Setting binning to %dx%d...', x, y)

    async def set_cooling(self, enabled: bool, setpoint: float, **kwargs: Any) -> None:
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

    async def get_cooling_status(self, **kwargs: Any) -> Tuple[bool, float, float]:
        """Returns the current status for the cooling.

        Returns:
            Tuple containing:
                Enabled (bool):         Whether the cooling is enabled
                SetPoint (float):       Setpoint for the cooling in celsius.
                Power (float):          Current cooling power in percent or None.
        """

        try:
            enabled, temp, setpoint, power = self._driver.camera.get_cooling()
            self._cooling = enabled is True, setpoint, power * 100.
        except ValueError:
            # use existing cooling
            pass
        return self._cooling

    async def get_temperatures(self, **kwargs: Any) -> Dict[str, float]:
        """Returns all temperatures measured by this module.

        Returns:
            Dict containing temperatures.
        """

        try:
            _, temp, _, _ = self._driver.camera.get_cooling()
            return {'CCD': temp}
        except ValueError:
            # use existing temps
            pass


__all__ = ['SbigCamera']
