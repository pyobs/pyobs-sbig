import asyncio
import logging
import math
from datetime import datetime
from typing import Union, Any, Optional, Dict

from pyobs.images import Image
from pyobs.interfaces import ICamera, IWindow
from pyobs.modules.camera.basecamera import BaseCamera
from pyobs.utils.enums import ExposureStatus
from pyobs_sbig.sbigdriver import SbigDriver
from pyobs_sbig.sbigudrv import *


log = logging.getLogger(__name__)


class SbigBaseCamera(BaseCamera, ICamera, IWindow):
    """A pyobs module for SBIG cameras."""
    __module__ = 'pyobs_sbig'

    def __init__(self, sensor: Union[str, ActiveSensor] = ActiveSensor.IMAGING, driver: Optional[SbigDriver] = None,
                 driver_kwargs: Optional[Dict[str, Any]] = None, **kwargs: Any):
        """Initializes a new SbigCamera.

        Args:
            sensor: Sensor to use, if camera has more than one.
            driver_kwargs: kwargs for driver.

        """
        BaseCamera.__init__(self, **kwargs)

        # create driver?
        if driver is not None:
            self._driver = driver
        else:
            driver_kwargs = {} if driver_kwargs is None else driver_kwargs
            self._driver = self.add_child_object({'class': 'pyobs_sbig.SbigDriver'},
                                                 object_class=SbigDriver, **driver_kwargs)

        # active sensor
        if isinstance(sensor, str):
            self._active_sensor = ActiveSensor[sensor.upper()]
        elif isinstance(sensor, ActiveSensor):
            self._active_sensor = sensor
        else:
            raise ValueError('Invalid sensor given.')

        # create image
        self._img = SBIGImg()

        # window and binning
        self._full_frame = (0, 0, 0, 0)
        self._window = (0, 0, 0, 0)
        self._binning = (1, 1)

    async def open(self) -> None:
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        await BaseCamera.open(self)

        # get window
        self._window = await self.get_full_frame()

    async def get_full_frame(self, **kwargs: Any) -> Tuple[int, int, int, int]:
        """Returns full size of CCD.

        Returns:
            Tuple with left, top, width, and height set.
        """
        return self._driver.full_frame(self._active_sensor)

    async def get_window(self, **kwargs: Any) -> Tuple[int, int, int, int]:
        """Returns the camera window.

        Returns:
            Tuple with left, top, width, and height set.
        """
        return self._window

    async def set_window(self, left: int, top: int, width: int, height: int, **kwargs: Any) -> None:
        """Set the camera window.

        Args:
            left: X offset of window.
            top: Y offset of window.
            width: Width of window.
            height: Height of window.
        """
        self._window = (left, top, width, height)
        log.info('Setting window to %dx%d at %d,%d...', width, height, left, top)

    async def _expose(self, exposure_time: float, open_shutter: bool, abort_event: asyncio.Event) -> Image:
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

        #  binning
        binning = self._binning

        # set window, CSBIGCam expects left/top also in binned coordinates, so divide by binning
        left = int(math.floor(self._window[0]) / binning[0])
        top = int(math.floor(self._window[1]) / binning[1])
        width = int(math.floor(self._window[2]) / binning[0])
        height = int(math.floor(self._window[3]) / binning[1])
        log.info("Set window to %dx%d (binned %dx%d) at %d,%d.",
                 self._window[2], self._window[3], width, height, left, top)
        window = (left, top, width, height)

        # get date obs
        log.info('Starting exposure with for %.2f seconds...', exposure_time)
        date_obs = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")

        # init image
        self._img.image_can_close = False

        # start exposure (can raise ValueError)
        self._driver.start_exposure(self._active_sensor, self._img, open_shutter, exposure_time, window=window,
                                    binning=binning)

        # wait for it
        while not self._driver.has_exposure_finished(self._active_sensor):
            # was aborted?
            if abort_event.is_set():
                raise ValueError('Exposure aborted.')
            await asyncio.sleep(0.01)

        # finish exposure
        self._driver.end_exposure(self._active_sensor)

        # wait for readout
        log.info('Exposure finished, reading out...')
        await self._change_exposure_status(ExposureStatus.READOUT)

        # start readout (can raise ValueError)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._driver.readout, self._active_sensor, self._img, open_shutter)

        # finalize image
        self._img.image_can_close = True

        # download data
        data = self._img.data

        # temp & cooling
        _, temp, setpoint, _ = self._driver.camera.get_cooling()

        # create FITS image and set header
        img = Image(data)
        img.header['DATE-OBS'] = (date_obs, 'Date and time of start of exposure')
        img.header['EXPTIME'] = (exposure_time, 'Exposure time [s]')
        img.header['DET-TEMP'] = (temp, 'CCD temperature [C]')
        img.header['DET-TSET'] = (setpoint, 'Cooler setpoint [C]')

        # binning
        img.header['XBINNING'] = img.header['DET-BIN1'] = (self._binning[0], 'Binning factor used on X axis')
        img.header['YBINNING'] = img.header['DET-BIN2'] = (self._binning[1], 'Binning factor used on Y axis')

        # window
        img.header['XORGSUBF'] = (self._window[0], 'Subframe origin on X axis')
        img.header['YORGSUBF'] = (self._window[1], 'Subframe origin on Y axis')

        # statistics
        img.header['DATAMIN'] = (float(np.min(data)), 'Minimum data value')
        img.header['DATAMAX'] = (float(np.max(data)), 'Maximum data value')
        img.header['DATAMEAN'] = (float(np.mean(data)), 'Mean data value')

        # biassec/trimsec
        frame = await self.get_full_frame()
        self.set_biassec_trimsec(img.header, *frame)

        # return FITS image
        log.info('Readout finished.')
        return img

    async def _abort_exposure(self) -> None:
        """Abort the running exposure. Should be implemented by derived class.

        Raises:
            ValueError: If an error occured.
        """
        await self._change_exposure_status(ExposureStatus.IDLE)


__all__ = ['SbigBaseCamera']
