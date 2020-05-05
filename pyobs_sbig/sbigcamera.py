# distutils: language = c++

import logging
import math
import threading
from datetime import datetime
from astropy.io import fits

from pyobs.interfaces import ICamera, ICameraWindow, ICameraBinning, ICooling
from pyobs.modules.camera.basecamera import BaseCamera

from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigCamera(BaseCamera, ICamera, ICameraWindow, ICameraBinning, ICooling):
    """A pyobs module for SBIG cameras."""

    def __init__(self, setpoint: float = -20, *args, **kwargs):
        """Initializes a new SbigCamera.

        Args:
            setpoint: Cooling temperature setpoint.
        """
        BaseCamera.__init__(self, *args, **kwargs)

        # create cam
        self._cam = SBIGCam()
        self._img = SBIGImg()

        # cooling
        self._setpoint = setpoint

        # window and binning
        self._full_frame = None
        self._window = None
        self._binning = None

        # cooling and temps to return in case of blocked device
        self._cooling = None, None, None
        self._temps = None

    def open(self):
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        BaseCamera.open(self)

        # open driver
        log.info('Opening SBIG driver...')
        try:
            self._cam.establish_link()
        except ValueError as e:
            raise ValueError('Could not establish link: %s' % str(e))

        # get window and binning from camera
        self._window = self.get_full_frame()
        self._binning = (1, 1)

        # cooling
        self.set_cooling(self._setpoint is not None, self._setpoint)

        # set binning to 1x1 and get full frame
        self._cam.binning = self._binning
        self._full_frame = (0, 0, *self._cam.full_frame)

    def get_full_frame(self, *args, **kwargs) -> (int, int, int, int):
        """Returns full size of CCD.

        Returns:
            Tuple with left, top, width, and height set.
        """
        return self._full_frame

    def get_window(self, *args, **kwargs) -> (int, int, int, int):
        """Returns the camera window.

        Returns:
            Tuple with left, top, width, and height set.
        """
        return self._window

    def get_binning(self, *args, **kwargs) -> dict:
        """Returns the camera binning.

        Returns:
            Dictionary with x and y.
        """
        return self._binning

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

    def set_binning(self, x: int, y: int, *args, **kwargs):
        """Set the camera binning.

        Args:
            x: X binning.
            y: Y binning.
        """
        self._binning = (x, y)
        log.info('Setting binning to %dx%d...', x, y)

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

        # set binning
        self._cam.binning = self._binning

        # set window, CSBIGCam expects left/top also in binned coordinates, so divide by binning
        left = int(math.floor(self._window[0]) / self._binning[0])
        top = int(math.floor(self._window[1]) / self._binning[1])
        width = int(math.floor(self._window[2]) / self._binning[0])
        height = int(math.floor(self._window[3]) / self._binning[1])
        log.info("Set window to %dx%d (binned %dx%d) at %d,%d.",
                 self._window[2], self._window[3], width, height, left, top)
        self._cam.window = (left, top, width, height)

        # set exposure time
        self._cam.exposure_time = exposure_time / 1000.

        # set exposing
        self._change_exposure_status(ICamera.ExposureStatus.EXPOSING)

        # get date obs
        log.info('Starting exposure with %s shutter for %.2f seconds...',
                 'open' if open_shutter else 'closed', exposure_time / 1000.)
        date_obs = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")

        # init image
        self._img.image_can_close = False

        # start exposure (can raise ValueError)
        self._cam.expose(self._img, open_shutter)

        # was aborted?
        if self._cam.was_aborted():
            return None

        # wait for readout
        log.info('Exposure finished, reading out...')
        self._change_exposure_status(ICamera.ExposureStatus.READOUT)

        # start readout (can raise ValueError)
        self._cam.readout(self._img, open_shutter)

        # finalize image
        self._img.image_can_close = True

        # download data
        data = self._img.data

        # temp & cooling
        _, temp, setpoint, _ = self._cam.get_cooling()

        # create FITS image and set header
        hdu = fits.PrimaryHDU(data)
        hdu.header['DATE-OBS'] = (date_obs, 'Date and time of start of exposure')
        hdu.header['EXPTIME'] = (exposure_time / 1000., 'Exposure time [s]')
        hdu.header['DET-TEMP'] = (temp, 'CCD temperature [C]')
        hdu.header['DET-TSET'] = (setpoint, 'Cooler setpoint [C]')

        # instrument and detector
        hdu.header['INSTRUME'] = ('Andor', 'Name of instrument')

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
        self._change_exposure_status(ICamera.ExposureStatus.IDLE)
        return hdu

    def set_cooling(self, enabled: bool, setpoint: float, *args, **kwargs):
        """Enables/disables cooling and sets setpoint.

        Args:
            enabled: Enable or disable cooling.
            setpoint: Setpoint in celsius for the cooling.

        Raises:
            ValueError: If cooling could not be set.
        """

        # log
        if enabled:
            log.info('Enabling cooling with a setpoint of %.2f°C...', setpoint)
        else:
            log.info('Disabling cooling and setting setpoint to 20°C...')

        # do it
        self._cam.set_cooling(enabled, setpoint)

    def get_cooling_status(self, *args, **kwargs) -> (bool,  float, float):
        """Returns the current status for the cooling.

        Returns:
            Tuple containing:
                Enabled (bool):         Whether the cooling is enabled
                SetPoint (float):       Setpoint for the cooling in celsius.
                Power (float):          Current cooling power in percent or None.
        """

        try:
            enabled, temp, setpoint, _ = self._cam.get_cooling()
            self._cooling = enabled, temp, setpoint
        except ValueError:
            # use existing cooling
            pass
        return self._cooling

    def get_temperatures(self, *args, **kwargs) -> dict:
        """Returns all temperatures measured by this module.

        Returns:
            Dict containing temperatures.
        """

        try:
            _, temp, _, _ = self._cam.get_cooling()
            self._temps = {'CCD': temp}
        except ValueError:
            # use existing temps
            pass
        return self._temps

    def _abort_exposure(self):
        """Abort the running exposure. Should be implemented by derived class.

        Raises:
            ValueError: If an error occured.
        """
        self._cam.abort()
        self._change_exposure_status(ICamera.ExposureStatus.IDLE)


__all__ = ['SbigCamera']
