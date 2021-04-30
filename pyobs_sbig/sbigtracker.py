import logging
from typing import Union

from .sbigbasecamera import SbigBaseCamera
from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigTracker(SbigBaseCamera):
    """A pyobs module for the tracker chip in some SBIG cameras."""
    __module__ = 'pyobs_sbig'

    def __init__(self, sensor: Union[str, ActiveSensor] = ActiveSensor.TRACKING, *args, **kwargs):
        """Initializes a new SbigTracker.

        Args:
            setpoint: Cooling temperature setpoint.
        """
        SbigBaseCamera.__init__(self, sensor=sensor, *args, **kwargs)


__all__ = ['SbigTracker']
