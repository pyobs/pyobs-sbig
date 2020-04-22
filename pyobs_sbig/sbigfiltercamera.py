# distutils: language = c++

import logging
import threading
from astropy.io import fits
from pyobs.mixins import MotionStatusMixin

from pyobs.events import FilterChangedEvent
from pyobs.interfaces import IFilters, IMotion
from pyobs.utils.threads import LockWithAbort

from .sbigcamera import SbigCamera
from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigFilterCamera(MotionStatusMixin, SbigCamera, IFilters):
    """A pyobs module for SBIG cameras."""

    def __init__(self, filter_wheel: str = 'UNKNOWN', filter_names: list = None, *args, **kwargs):
        """Initializes a new SbigCamera.

        Args:
            filter_wheel: Name of filter wheel used by the camera.
            filter_names: List of filter names.
        """
        SbigCamera.__init__(self, *args, **kwargs)

        # filter wheel
        self._filter_wheel = FilterWheelModel[filter_wheel]

        # and filter names
        if filter_names is None:
            filter_names = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
        positions = [p for p in FilterWheelPosition]
        self._filter_names = dict(zip(positions[1:], filter_names))
        self._filter_names[FilterWheelPosition.UNKNOWN] = 'UNKNOWN'

        # allow to abort motion (filter wheel)
        self._lock_motion = threading.Lock()
        self._abort_motion = threading.Event()

        # current position
        self._position = FilterWheelPosition.UNKNOWN

        # init mixins
        MotionStatusMixin.__init__(self, *args, **kwargs, motion_status_interfaces=['IFilters'])

    def open(self):
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """

        # set filter wheel model
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            log.info('Initialising filter wheel...')
            try:
                self._cam.set_filter_wheel(self._filter_wheel)
            except ValueError as e:
                raise ValueError('Could not set filter wheel: %s' % str(e))
            self._change_motion_status(IMotion.Status.POSITIONED, interface='IFilters')

        # open camera
        SbigCamera.open(self)

        # subscribe to events
        if self.comm:
            self.comm.register_event(FilterChangedEvent)

    def _expose(self, exposure_time: int, open_shutter: bool, abort_event: threading.Event) -> fits.PrimaryHDU:
        """Actually do the exposure, should be implemented by derived classes.

        Args:
            exposure_time: The requested exposure time in ms.
            open_shutter: Whether or not to open the shutter.
            abort_event: Event that gets triggered when exposure should be aborted.

        Returns:
            The actual image.

        Raises:
            ValueError: If exposure was not successful.
        """

        # do expsure
        hdu = SbigCamera._expose(self, exposure_time, open_shutter, abort_event)

        # add filter to FITS headers
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            hdu.header['FILTER'] = (self.get_filter(), 'Current filter')

        # finished
        return hdu

    def set_filter(self, filter_name: str, *args, **kwargs):
        """Set the current filter.

        Args:
            filter_name: Name of filter to set.

        Raises:
            ValueError: If binning could not be set.
            NotImplementedError: If camera doesn't have a filter wheel.
        """

        # do we have a filter wheel?
        if self._filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # reverse dict and search for name
        filters = {y: x for x, y in self._filter_names.items()}
        if filter_name not in filters:
            raise ValueError('Unknown filter: %s', filter_name)

        # there already?
        position, status = self._cam.get_filter_position_and_status()
        if position == filters[filter_name] and status == FilterWheelStatus.IDLE:
            log.info('Filter changed.')
            return

        # set status
        self._change_motion_status(IMotion.Status.SLEWING, interface='IFilters')

        # acquire lock
        with LockWithAbort(self._lock_motion, self._abort_motion):
            # set it
            log.info('Changing filter to %s...', filter_name)
            self._cam.set_filter(filters[filter_name])

            # wait for it
            while True:
                # break, if wheel is idle and filter is set
                position, status = self._cam.get_filter_position_and_status()
                if position == filters[filter_name] and status == FilterWheelStatus.IDLE:
                    break

                # abort?
                if self._abort_motion.is_set():
                    log.warning('Filter change aborted.')
                    return

            # send event
            log.info('Filter changed.')
            self.comm.send_event(FilterChangedEvent(filter_name))

        # set status
        self._change_motion_status(IMotion.Status.POSITIONED, interface='IFilters')

    def get_filter(self, *args, **kwargs) -> str:
        """Get currently set filter.

        Returns:
            Name of currently set filter.

        Raises:
            ValueError: If filter could not be fetched.
            NotImplementedError: If camera doesn't have a filter wheel.
        """

        # do we have a filter wheel?
        if self._filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        try:
            self._position, _ = self._cam.get_filter_position_and_status()
        except ValueError:
            # use existing position
            pass
        return self._filter_names[self._position]

    def list_filters(self, *args, **kwargs) -> list:
        """List available filters.

        Returns:
            List of available filters.

        Raises:
            NotImplementedError: If camera doesn't have a filter wheel.
        """

        # do we have a filter wheel?
        if self._filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # return names
        return [f for f in self._filter_names.values() if f is not None]


__all__ = ['SbigFilterCamera']
