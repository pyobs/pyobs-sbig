import logging
from typing import Union, Any

from .sbigbasecamera import SbigBaseCamera
from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigTracker(SbigBaseCamera):
    """A pyobs module for the tracker chip in some SBIG cameras."""
    __module__ = 'pyobs_sbig'

    def __init__(self, sensor: Union[str, ActiveSensor] = ActiveSensor.TRACKING, **kwargs: Any):
        """Initializes a new SbigTracker.

        Args:
            setpoint: Cooling temperature setpoint.
        """
        SbigBaseCamera.__init__(self, sensor=sensor, **kwargs)


__all__ = ['SbigTracker']
