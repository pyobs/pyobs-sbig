import logging
from typing import Any, Optional

from pyobs.object import Object

from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigDriver(Object):
    """The underlying driver for the pyobs SBIG modules."""

    def __init__(self, filter_wheel: str = 'UNKNOWN', **kwargs: Any):
        """Initializes a new SbigCamera.

        Args:
            filter_wheel: Name of filter wheel, if any.
        """
        Object.__init__(self, **kwargs)

        # create cam
        self.camera = SBIGCam()

        # filter wheel
        self.filter_wheel = FilterWheelModel[filter_wheel]

        # active lock
        self._lock_active = threading.Lock()

    def open(self) -> None:
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """

        # set filter wheel model
        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            log.info('Initialising filter wheel...')
            try:
                self.camera.set_filter_wheel(self.filter_wheel)
            except ValueError as e:
                raise ValueError('Could not set filter wheel: %s' % str(e))

        # open driver
        log.info('Opening SBIG driver...')
        try:
            self.camera.establish_link()
        except ValueError as e:
            raise ValueError('Could not establish link: %s' % str(e))

    def full_frame(self, sensor: ActiveSensor) -> Tuple[int, int, int, int]:
        """Return full frame."""
        with self._lock_active:
            # TODO: maybe rethink this: should the camera return the full frame for the current binning and
            # not for 1x1?
            self.camera.binning = (1, 1)
            self.camera.sensor = sensor
            return self.camera.full_frame

    def start_exposure(self, sensor: ActiveSensor, img: SBIGImg, shutter: bool, exposure_time: float,
                       window: Optional[Tuple[int, int, int, int]] = None,
                       binning: Optional[Tuple[int, int]] = None) -> None:
        """Start an exposure.

        Args:
            sensor: Sensor to use for exposure.
            img: Image to write into.
            shutter: Whether to open shutter.
            exposure_time: Exposure time in secs.
            window: Window to use.
            binning: Binning to use.
        """

        # do all settings within a mutex
        with self._lock_active:
            # set active sensor
            self.camera.sensor = sensor

            # set exposure time, window and binnint
            self.camera.exposure_time = exposure_time
            self.camera.window = window
            self.camera.binning = binning

            # start exposure
            self.camera.start_exposure(img, shutter)

    def has_exposure_finished(self, sensor: ActiveSensor) -> bool:
        """Whether an exposure has finished

        Args:
            sensor: Sensor to use for exposure.

        Returns:
            Exposure finished or not.
        """
        with self._lock_active:
            self.camera.sensor = sensor
            return self.camera.has_exposure_finished()

    def end_exposure(self, sensor: ActiveSensor) -> None:
        """End an exposure."""
        with self._lock_active:
            self.camera.sensor = sensor
            return self.camera.end_exposure()

    def readout(self, sensor: ActiveSensor, img: SBIGImg, shutter: bool) -> None:
        """Readout image.

        Args:
            sensor: Camera to use for exposure.
            img: Image to read into.
            shutter: Whether shutter was open.
        """
        with self._lock_active:
            self.camera.sensor = sensor
            return self.camera.readout(img, shutter)


__all__ = ['SbigDriver']
