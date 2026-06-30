import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pyobs.images import Image
from pyobs.interfaces import IAbortable, IBinning, ICamera, ICooling, ITemperatures, IWindow
from pyobs.interfaces.IBinning import BinningCapabilities, BinningState
from pyobs.interfaces.ICooling import CoolingState
from pyobs.interfaces.ITemperatures import SensorReading, TemperaturesState
from pyobs.interfaces.IWindow import WindowCapabilities, WindowState
from pyobs.modules.camera.basecamera import BaseCamera
from pyobs.utils.enums import ExposureStatus

log = logging.getLogger(__name__)


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

    async def open(self) -> None:
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        await BaseCamera.open(self)

        # open driver
        log.info("Opening SBIG driver...")
        try:
            self._cam.establish_link()
        except ValueError as e:
            raise ValueError(f"Could not establish link: {e}")

        # cooling
        await self.set_cooling(self._setpoint is not None, self._setpoint)

        # get full frame
        self._cam.binning = (1, 1)
        self._full_frame = self._cam.full_frame
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

            # init image
            self._img.image_can_close = False

            # set exposure time, window and binning
            self._cam.exposure_time = exposure_time
            self._cam.window = window
            self._cam.binning = binning

            # start exposure
            self._cam.start_exposure(self._img, open_shutter)

            # wait for it
            while not self._cam.has_exposure_finished():
                # was aborted?
                if abort_event.is_set():
                    raise InterruptedError("Exposure aborted.")
                await asyncio.sleep(0.01)

            # finish exposure
            self._cam.end_exposure()

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
            _, temp, setpoint, _ = self._cam.get_cooling()

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
        async with self._lock_active:
            self._cam.set_cooling(enabled, setpoint)

        # publish state (power unknown until next poll)
        await self.comm.set_state(ICooling, CoolingState(setpoint=setpoint, power=None, enabled=enabled))

    async def _poll_cooling(self) -> None:
        """Background task: periodically reads cooling status and publishes ICooling and ITemperatures state."""
        while True:
            try:
                async with self._lock_active:
                    enabled, temp, setpoint, power = self._cam.get_cooling()
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
