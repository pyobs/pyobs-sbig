import logging
import math
import threading
from datetime import datetime
from typing import Tuple, Union

from astropy.io import fits

from pyobs.interfaces import ICamera, ICameraWindow
from pyobs.modules.camera.basecamera import BaseCamera
from pyobs.utils.enums import ExposureStatus
from pyobs_sbig.sbigdriver import SbigDriver
from pyobs_sbig.sbigudrv import *


log = logging.getLogger(__name__)


class SbigBaseCamera(BaseCamera, ICamera, ICameraWindow):
    """A pyobs module for SBIG cameras."""
    __module__ = 'pyobs_sbig'

    def __init__(self, sensor: Union[str, ActiveSensor] = ActiveSensor.IMAGING, driver: SbigDriver = None,
                 *args, **kwargs):
        """Initializes a new SbigCamera.

        Args:
            sensor: Sensor to use, if camera has more than one.
            driver: Driver to use, if any.

        """
        BaseCamera.__init__(self, *args, **kwargs)

        # create driver?
        if driver is None:
            self._driver = self.add_child_object(object_class=SbigDriver)
        else:
            self._driver = driver

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
        self._full_frame = None
        self._window = None
        self._binning = (1, 1)

    def open(self):
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        BaseCamera.open(self)

        # get window
        self._window = self.get_full_frame()

    def get_full_frame(self, *args, **kwargs) -> Tuple[int, int, int, int]:
        """Returns full size of CCD.

        Returns:
            Tuple with left, top, width, and height set.
        """
        return self._driver.full_frame(self._active_sensor)

    def get_window(self, *args, **kwargs) -> Tuple[int, int, int, int]:
        """Returns the camera window.

        Returns:
            Tuple with left, top, width, and height set.
        """
        return self._window

    def set_window(self, left: int, top: int, width: int, height: int, *args, **kwargs):
        """Set the camera window.

        Args:
            left: X offset of window.
            top: Y offset of window.
            width: Width of window.
            height: Height of window.
        """
        self._window = (left, top, width, height)
        log.info('Setting window to %dx%d at %d,%d...', width, height, left, top)

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

        # set exposing
        self._change_exposure_status(ExposureStatus.EXPOSING)

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
                return None

        # finish exposure
        self._driver.end_exposure(self._active_sensor)

        # wait for readout
        log.info('Exposure finished, reading out...')
        self._change_exposure_status(ExposureStatus.READOUT)

        # start readout (can raise ValueError)
        self._driver.readout(self._active_sensor, self._img, open_shutter)

        # finalize image
        self._img.image_can_close = True

        # download data
        data = self._img.data

        # temp & cooling
        _, temp, setpoint, _ = self._driver.camera.get_cooling()

        # create FITS image and set header
        hdu = fits.PrimaryHDU(data)
        hdu.header['DATE-OBS'] = (date_obs, 'Date and time of start of exposure')
        hdu.header['EXPTIME'] = (exposure_time, 'Exposure time [s]')
        hdu.header['DET-TEMP'] = (temp, 'CCD temperature [C]')
        hdu.header['DET-TSET'] = (setpoint, 'Cooler setpoint [C]')

        # binning
        hdu.header['XBINNING'] = hdu.header['DET-BIN1'] = (self._binning[0], 'Binning factor used on X axis')
        hdu.header['YBINNING'] = hdu.header['DET-BIN2'] = (self._binning[1], 'Binning factor used on Y axis')

        # window
        hdu.header['XORGSUBF'] = (self._window[0], 'Subframe origin on X axis')
        hdu.header['YORGSUBF'] = (self._window[1], 'Subframe origin on Y axis')

        # statistics
        hdu.header['DATAMIN'] = (float(np.min(data)), 'Minimum data value')
        hdu.header['DATAMAX'] = (float(np.max(data)), 'Maximum data value')
        hdu.header['DATAMEAN'] = (float(np.mean(data)), 'Mean data value')

        # biassec/trimsec
        frame = self.get_full_frame()
        self.set_biassec_trimsec(hdu.header, *frame)

        # return FITS image
        log.info('Readout finished.')
        self._change_exposure_status(ExposureStatus.IDLE)
        return hdu

    def _abort_exposure(self):
        """Abort the running exposure. Should be implemented by derived class.

        Raises:
            ValueError: If an error occured.
        """
        self._change_exposure_status(ExposureStatus.IDLE)


__all__ = ['SbigBaseCamera']
