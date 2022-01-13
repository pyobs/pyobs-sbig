import asyncio
import logging
from typing import List, Optional, Any

from pyobs.images import Image
from pyobs.mixins import MotionStatusMixin
from pyobs.events import FilterChangedEvent
from pyobs.interfaces import IFilters
from pyobs.utils.enums import MotionStatus
from pyobs.utils.threads import LockWithAbort

from .sbigcamera import SbigCamera
from .sbigudrv import FilterWheelPosition, FilterWheelStatus, FilterWheelModel


log = logging.getLogger(__name__)


class SbigFilterCamera(MotionStatusMixin, SbigCamera, IFilters):
    """A pyobs module for SBIG cameras."""

    __module__ = "pyobs_sbig"

    def __init__(self, filter_wheel: str, filter_names: Optional[List[str]] = None, **kwargs: Any):
        """Initializes a new SbigCamera.

        Args:
            filter_names: List of filter names.
        """
        SbigCamera.__init__(self, **kwargs)

        # filter wheel
        self.filter_wheel = FilterWheelModel[filter_wheel]

        # and filter names
        if filter_names is None:
            filter_names = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        positions = [p for p in FilterWheelPosition]
        self._filter_names = dict(zip(positions[1:], filter_names))
        self._filter_names[FilterWheelPosition.UNKNOWN] = "UNKNOWN"

        # allow to abort motion (filter wheel)
        self._lock_motion = asyncio.Lock()
        self._abort_motion = asyncio.Event()

        # current position
        self._position = FilterWheelPosition.UNKNOWN

        # init mixins
        MotionStatusMixin.__init__(self, **kwargs, motion_status_interfaces=["IFilters"])

    async def open(self) -> None:
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """

        # set filter wheel model
        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            log.info("Initialising filter wheel...")
            try:
                self._cam.set_filter_wheel(self.filter_wheel)
            except ValueError as e:
                raise ValueError("Could not set filter wheel: %s" % str(e))

        # open camera
        await SbigCamera.open(self)

        # init status of filter wheel
        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            await self._change_motion_status(MotionStatus.POSITIONED, interface="IFilters")

        # subscribe to events
        if self.comm:
            await self.comm.register_event(FilterChangedEvent)

    async def _expose(self, exposure_time: float, open_shutter: bool, abort_event: asyncio.Event) -> Image:
        """Actually do the exposure, should be implemented by derived classes.

        Args:
            exposure_time: The requested exposure time in ms.
            open_shutter: Whether or not to open the shutter.
            abort_event: Event that gets triggered when exposure should be aborted.

        Returns:
            The actual image.

        Raises:
            GrabImageError: If exposure was not successful.
        """

        # do expsure
        img = await SbigCamera._expose(self, exposure_time, open_shutter, abort_event)

        # add filter to FITS headers
        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            img.header["FILTER"] = (await self.get_filter(), "Current filter")

        # finished
        return img

    async def set_filter(self, filter_name: str, **kwargs: Any) -> None:
        """Set the current filter.

        Args:
            filter_name: Name of filter to set.

        Raises:
            ValueError: If binning could not be set.
            NotImplementedError: If camera doesn't have a filter wheel.
        """

        # do we have a filter wheel?
        if self.filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # reverse dict and search for name
        filters = {y: x for x, y in self._filter_names.items()}
        if filter_name not in filters:
            raise ValueError("Unknown filter: %s" % filter_name)

        # there already?
        position, status = self._cam.get_filter_position_and_status()
        if position == filters[filter_name] and status == FilterWheelStatus.IDLE:
            log.info("Filter changed.")
            return

        # set status
        await self._change_motion_status(MotionStatus.SLEWING, interface="IFilters")

        # acquire lock
        async with LockWithAbort(self._lock_motion, self._abort_motion):
            # set it
            log.info("Changing filter to %s...", filter_name)
            self._cam.set_filter(filters[filter_name])

            # wait for it
            while True:
                # break, if wheel is idle and filter is set
                position, status = self._cam.get_filter_position_and_status()
                if position == filters[filter_name] and status == FilterWheelStatus.IDLE:
                    break

                # abort?
                if self._abort_motion.is_set():
                    raise InterruptedError("Filter change aborted.")

                # sleep a little
                await asyncio.sleep(0.1)

            # send event
            log.info("Filter changed.")
            self.comm.send_event(FilterChangedEvent(filter_name))

        # set status
        await self._change_motion_status(MotionStatus.POSITIONED, interface="IFilters")

    async def get_filter(self, **kwargs: Any) -> str:
        """Get currently set filter.

        Returns:
            Name of currently set filter.

        Raises:
            ValueError: If filter could not be fetched.
            NotImplementedError: If camera doesn't have a filter wheel.
        """

        # do we have a filter wheel?
        if self.filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        try:
            self._position, _ = self._cam.get_filter_position_and_status()
        except ValueError:
            # use existing position
            pass
        return self._filter_names[self._position]

    async def list_filters(self, **kwargs: Any) -> List[str]:
        """List available filters.

        Returns:
            List of available filters.

        Raises:
            NotImplementedError: If camera doesn't have a filter wheel.
        """

        # do we have a filter wheel?
        if self.filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # return names
        return [f for f in self._filter_names.values() if f is not None]

    async def init(self, **kwargs: Any) -> None:
        pass

    async def park(self, **kwargs: Any) -> None:
        pass

    async def stop_motion(self, device: Optional[str] = None, **kwargs: Any) -> None:
        pass

    async def is_ready(self, **kwargs: Any) -> bool:
        return True


__all__ = ["SbigFilterCamera"]
