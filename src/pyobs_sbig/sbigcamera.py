import asyncio
import logging
import math
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

import numpy as np
from pyobs.images import Image
from pyobs.interfaces import IAbortable, IBinning, ICamera, ICooling, ITemperatures, IWindow
from pyobs.interfaces.IBinning import BinningCapabilities, BinningState
from pyobs.interfaces.ICooling import CoolingState
from pyobs.interfaces.ITemperatures import SensorReading, TemperaturesState
from pyobs.interfaces.IWindow import WindowCapabilities, WindowState
from pyobs.modules.camera.basecamera import BaseCamera
from pyobs.utils import exceptions as exc
from pyobs.utils.enums import ExposureStatus

log = logging.getLogger(__name__)

_T = TypeVar("_T")

# SBIG SDK calls are blocking and are made directly on the event loop thread (see
# _run_blocking). If the camera has gone unresponsive, they can hang indefinitely, so they're
# bounded with a timeout rather than let a single dead camera freeze the whole module.
_SDK_CALL_TIMEOUT = 5.0

# the exposure-wait loop's own timeout needs to cover the actual exposure time plus some margin
# for overhead -- exposure_time alone would be too tight.
_EXPOSURE_WAIT_MARGIN = 30.0


class SbigCamera(BaseCamera, ICamera, IWindow, IBinning, ICooling, ITemperatures, IAbortable):
    """A pyobs module for SBIG cameras."""

    __module__ = "pyobs_sbig"

    def __init__(self, setpoint: float = -20, **kwargs: Any):
        """Initializes a new SbigCamera.

        Args:
            setpoint: Temperature setpoint.

        """
        BaseCamera.__init__(self, **kwargs)
        from .sbigudrv import SBIGCam, SBIGImg  # type: ignore

        # create image and cam
        self._img = SBIGImg()
        self._cam = SBIGCam()

        # active lock
        self._lock_active = asyncio.Lock()

        # cooling
        self._setpoint = setpoint

        # window and binning
        self._full_frame = (0, 0, 0, 0)
        self._window = (0, 0, 0, 0)
        self._binning = (1, 1)

        # background task for polling cooling/temperature
        self.add_background_task(self._poll_cooling)

    @staticmethod
    async def _run_blocking(func: Callable[[], None], timeout: float = _SDK_CALL_TIMEOUT) -> bool:
        """Run a blocking SBIG SDK call in a daemon thread, so a hung call can't freeze the module.

        A plain executor isn't used here, since its worker threads are non-daemon and Python joins
        them on interpreter shutdown -- a hung call would then just move the freeze to process exit.

        Returns:
            True if func completed within timeout, False if it's still running in the background.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()

        def _wrapper() -> None:
            try:
                func()
            finally:
                loop.call_soon_threadsafe(future.set_result, None)

        threading.Thread(target=_wrapper, daemon=True).start()
        try:
            await asyncio.wait_for(future, timeout=timeout)
            return True
        except TimeoutError:
            return False

    async def _run_blocking_or_raise(self, func: Callable[[], _T], timeout: float = _SDK_CALL_TIMEOUT) -> _T:
        """Run a blocking SBIG SDK call in a thread, returning its result or re-raising what it raised.

        Unlike _run_blocking(), this also carries the callable's return value/exception back to the
        caller -- several SBIG calls here drive control flow via their return value or a raised
        ValueError (e.g. establishing the link), which a bare fire-and-forget thread call would
        otherwise silently lose.
        """
        outcome: list[Any] = []

        def _wrapper() -> None:
            try:
                outcome.append(func())
            except BaseException as e:
                outcome.append(e)

        if not await self._run_blocking(_wrapper, timeout=timeout):
            raise TimeoutError(f"Timed out waiting for SBIG SDK call after {timeout}s.")
        value = outcome[0]
        if isinstance(value, BaseException):
            raise value
        return cast(_T, value)

    async def open(self) -> None:
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        await BaseCamera.open(self)

        # open driver
        log.info("Opening SBIG driver...")

        def _connect() -> None:
            try:
                self._cam.establish_link()
            except ValueError as e:
                raise ValueError(f"Could not establish link: {e}")

        await self._run_blocking_or_raise(_connect)

        # cooling
        await self.set_cooling(self._setpoint is not None, self._setpoint)

        # get full frame
        def _get_full_frame() -> tuple[int, int, int, int]:
            self._cam.binning = (1, 1)
            return self._cam.full_frame

        self._full_frame = await self._run_blocking_or_raise(_get_full_frame)
        self._window = self._full_frame

        # publish capabilities and initial state
        await self.comm.set_capabilities(
            IWindow,
            WindowCapabilities(
                full_frame_x=self._full_frame[0],
                full_frame_y=self._full_frame[1],
                full_frame_width=self._full_frame[2],
                full_frame_height=self._full_frame[3],
            ),
        )
        await self.comm.set_state(
            IWindow, WindowState(x=self._window[0], y=self._window[1], width=self._window[2], height=self._window[3])
        )
        await self.comm.set_capabilities(
            IBinning,
            BinningCapabilities(binnings=[BinningState(x=1, y=1), BinningState(x=2, y=2), BinningState(x=3, y=3)]),
        )
        await self.comm.set_state(IBinning, BinningState(x=self._binning[0], y=self._binning[1]))

    async def set_window(self, left: int, top: int, width: int, height: int, **kwargs: Any) -> None:
        """Set the camera window.

        Args:
            left: X offset of window.
            top: Y offset of window.
            width: Width of window.
            height: Height of window.
        """
        self._window = (left, top, width, height)
        log.info("Setting window to %dx%d at %d,%d...", width, height, left, top)
        await self.comm.set_state(IWindow, WindowState(x=left, y=top, width=width, height=height))

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

        async with self._lock_active:
            #  binning
            binning = self._binning

            # set window, CSBIGCam expects left/top also in binned coordinates, so divide by binning
            left = int(math.floor(self._window[0]) / binning[0])
            top = int(math.floor(self._window[1]) / binning[1])
            width = int(math.floor(self._window[2]) / binning[0])
            height = int(math.floor(self._window[3]) / binning[1])
            log.info(
                "Set window to %dx%d (binned %dx%d) at %d,%d.",
                self._window[2],
                self._window[3],
                width,
                height,
                left,
                top,
            )
            window = (left, top, width, height)

            # get date obs
            log.info("Starting exposure with for %.2f seconds...", exposure_time)
            date_obs = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")

            def _start() -> None:
                # init image
                self._img.image_can_close = False

                # set exposure time, window and binning
                self._cam.exposure_time = exposure_time
                self._cam.window = window
                self._cam.binning = binning

                # start exposure
                self._cam.start_exposure(self._img, open_shutter)

            await self._run_blocking_or_raise(_start)

            # wait for it -- runs the whole poll loop as a single blocking call (see _run_blocking),
            # rather than polling has_exposure_finished() every 10ms directly on the event loop
            def _wait() -> bool:
                while not self._cam.has_exposure_finished():
                    if abort_event.is_set():
                        return True
                    time.sleep(0.01)
                return False

            exposure_timeout = exposure_time + _EXPOSURE_WAIT_MARGIN
            aborted = await self._run_blocking_or_raise(_wait, timeout=exposure_timeout)
            if aborted:
                raise exc.AbortedError("Exposure aborted.")

            # finish exposure
            await self._run_blocking_or_raise(self._cam.end_exposure)

            # wait for readout
            log.info("Exposure finished, reading out...")
            await self._change_exposure_status(ExposureStatus.READOUT)

            # start readout (can raise ValueError)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._cam.readout, self._img, open_shutter)

            # finalize image
            self._img.image_can_close = True

            # download data
            data = self._img.data

            # temp & cooling
            def _get_cooling() -> tuple[Any, float, float, Any]:
                return self._cam.get_cooling()

            _, temp, setpoint, _ = await self._run_blocking_or_raise(_get_cooling)

            # create FITS image and set header
            img = Image(data)
            img.header["DATE-OBS"] = (date_obs, "Date and time of start of exposure")
            img.header["EXPTIME"] = (exposure_time, "Exposure time [s]")
            img.header["DET-TEMP"] = (temp, "CCD temperature [C]")
            img.header["DET-TSET"] = (setpoint, "Cooler setpoint [C]")

            # binning
            img.header["XBINNING"] = img.header["DET-BIN1"] = (self._binning[0], "Binning factor used on X axis")
            img.header["YBINNING"] = img.header["DET-BIN2"] = (self._binning[1], "Binning factor used on Y axis")

            # window
            img.header["XORGSUBF"] = (self._window[0], "Subframe origin on X axis")
            img.header["YORGSUBF"] = (self._window[1], "Subframe origin on Y axis")

            # statistics
            img.header["DATAMIN"] = (float(np.min(data)), "Minimum data value")
            img.header["DATAMAX"] = (float(np.max(data)), "Maximum data value")
            img.header["DATAMEAN"] = (float(np.mean(data)), "Mean data value")

            # biassec/trimsec
            self.set_biassec_trimsec(img.header, *self._full_frame)

            # return FITS image
            log.info("Readout finished.")
            return img

    async def _abort_exposure(self) -> None:
        """Abort the running exposure. Should be implemented by derived class.

        Raises:
            ValueError: If an error occured.
        """
        await self._change_exposure_status(ExposureStatus.IDLE)

    async def set_binning(self, x: int, y: int, **kwargs: Any) -> None:
        """Set the camera binning.

        Args:
            x: X binning.
            y: Y binning.
        """
        self._binning = (x, y)
        log.info("Setting binning to %dx%d...", x, y)
        await self.comm.set_state(IBinning, BinningState(x=x, y=y))

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
            log.info("Enabling cooling with a setpoint of %.2f°C...", setpoint)
        else:
            log.info("Disabling cooling and setting setpoint to 20°C...")

        # do it
        def _set() -> None:
            self._cam.set_cooling(enabled, setpoint)

        async with self._lock_active:
            await self._run_blocking_or_raise(_set)

        # publish state (power unknown until next poll)
        await self.comm.set_state(ICooling, CoolingState(setpoint=setpoint, power=None, enabled=enabled))

    async def _poll_cooling(self) -> None:
        """Background task: periodically reads cooling status and publishes ICooling and ITemperatures state."""
        while True:
            try:

                def _get() -> tuple[bool, float, float, float]:
                    return self._cam.get_cooling()

                async with self._lock_active:
                    enabled, temp, setpoint, power = await self._run_blocking_or_raise(_get)
                await self.comm.set_state(
                    ICooling, CoolingState(setpoint=setpoint, power=round(power * 100), enabled=enabled)
                )
                await self.comm.set_state(
                    ITemperatures, TemperaturesState(readings=[SensorReading(name="CCD", value=temp)])
                )
            except Exception:
                pass
            await asyncio.sleep(10)


__all__ = ["SbigCamera"]
