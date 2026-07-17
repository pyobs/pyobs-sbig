import asyncio
import logging
from typing import Any

from pyobs.events import FilterChangedEvent
from pyobs.images import Image
from pyobs.interfaces import IFilters, IReady
from pyobs.interfaces.IFilters import FiltersCapabilities, FilterState
from pyobs.interfaces.IReady import ReadyState
from pyobs.mixins import MotionStatusMixin
from pyobs.utils import exceptions as exc
from pyobs.utils.enums import MotionStatus
from pyobs.utils.threads import LockWithAbort

from .sbigcamera import SbigCamera

log = logging.getLogger(__name__)


class SbigFilterCamera(MotionStatusMixin, SbigCamera, IFilters):
    """A pyobs module for SBIG cameras."""

    __module__ = "pyobs_sbig"

    def __init__(self, filter_wheel: str, filter_names: list[str] | None = None, **kwargs: Any):
        """Initializes a new SbigCamera.

        Args:
            filter_names: List of filter names.
        """
        SbigCamera.__init__(self, **kwargs)
        from .sbigudrv import FilterWheelModel, FilterWheelPosition  # type: ignore

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
        from .sbigudrv import FilterWheelModel

        # set filter wheel model
        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            log.info("Initialising filter wheel...")
            try:
                self._cam.set_filter_wheel(self.filter_wheel)
            except ValueError as e:
                raise ValueError(f"Could not set filter wheel: {e}")

        # open camera (connects to hardware, publishes IWindow/IBinning states)
        await SbigCamera.open(self)

        # init mixin — registers events and publishes initial IMotion state
        await MotionStatusMixin.open(self)

        # subscribe to events
        if self._comm:
            await self.comm.register_event(FilterChangedEvent)

        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            # set motion status to positioned
            await self._change_motion_status(MotionStatus.POSITIONED, interface="IFilters")

            # publish filter capabilities
            filter_list = [name for name in self._filter_names.values() if name != "UNKNOWN"]
            await self.comm.set_capabilities(IFilters, FiltersCapabilities(filters=filter_list))

            # query and publish current filter position
            try:
                self._position, _ = self._cam.get_filter_position_and_status()
            except (ValueError, Exception):
                pass
            await self.comm.set_state(IFilters, FilterState(filter=self._filter_names[self._position]))

        # camera is ready once open
        await self.comm.set_state(IReady, ReadyState(ready=True))

    async def _expose(self, exposure_time: float, open_shutter: bool, abort_event: asyncio.Event) -> Image:
        """Actually do the exposure, should be implemented by derived classes.

        Args:
            exposure_time: The requested exposure time in ms.
            open_shutter: Whether or not to open the shutter.
            abort_event: Event that gets triggered when exposure should be aborted.

        Returns:
            The actual image.

        Raises:
            pyobs.utils.exceptions.GrabImageError: If exposure was not successful.
        """
        from .sbigudrv import FilterWheelModel

        # do exposure
        img = await SbigCamera._expose(self, exposure_time, open_shutter, abort_event)

        # add filter to FITS headers
        if self.filter_wheel != FilterWheelModel.UNKNOWN:
            img.header["FILTER"] = (self._filter_names[self._position], "Current filter")

        # finished
        return img

    async def set_filter(self, filter_name: str, **kwargs: Any) -> None:
        """Set the current filter.

        Args:
            filter_name: Name of filter to set.

        Raises:
            InvalidArgumentError: If filter_name is unknown.
            NotImplementedError: If camera doesn't have a filter wheel.
        """
        from .sbigudrv import FilterWheelModel, FilterWheelStatus

        # do we have a filter wheel?
        if self.filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # reverse dict and search for name
        filters = {y: x for x, y in self._filter_names.items()}
        if filter_name not in filters:
            raise exc.InvalidArgumentError(f"Unknown filter: {filter_name}")

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
                    raise exc.AbortedError("Filter change aborted.")

                # sleep a little
                await asyncio.sleep(0.1)

            # update cached position and publish new state
            self._position = filters[filter_name]
            log.info("Filter changed.")
            await self.comm.send_event(FilterChangedEvent(filter_name))
            await self.comm.set_state(IFilters, FilterState(filter=filter_name))

        # set status
        await self._change_motion_status(MotionStatus.POSITIONED, interface="IFilters")

    async def init(self, **kwargs: Any) -> None:
        """Initialize device.

        Raises:
            pyobs.utils.exceptions.InitError: If device could not be initialized.
        """
        pass

    async def park(self, **kwargs: Any) -> None:
        """Park device.

        Raises:
            pyobs.utils.exceptions.ParkError: If device could not be parked.
        """
        pass

    async def stop_motion(self, device: str | None = None, **kwargs: Any) -> None:
        """Stop the motion.

        Args:
            device: Name of device to stop, or None for all.
        """
        pass


__all__ = ["SbigFilterCamera"]
