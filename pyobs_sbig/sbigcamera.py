# distutils: language = c++

import logging
import threading
from datetime import datetime
from astropy.io import fits

from pyobs.interfaces import ICamera, ICameraWindow, ICameraBinning, IFilters, ICooling
from pyobs.modules.camera.basecamera import BaseCamera

from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigCamera(BaseCamera, ICamera, ICameraWindow, ICameraBinning, IFilters, ICooling):
    """A pyobs module for SBIG cameras."""

    def __init__(self, filter_wheel: str = 'UNKNOWN', filter_names: list = None, setpoint: float = -20,
                 *args, **kwargs):
        """Initializes a new SbigCamera.

        Args:
            filter_wheel: Name of filter wheel used by the camera.
            filter_names: List of filter names.
            setpoint: Cooling temperature setpoint.
        """
        BaseCamera.__init__(self, *args, **kwargs)

        # create cam
        self._cam = SBIGCam()
        self._img = SBIGImg()

        # cooling
        self._setpoint = setpoint

        # filter wheel
        self._filter_wheel = FilterWheelModel[filter_wheel]

        # and filter names
        if filter_names is None:
            filter_names = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
        positions = [p for p in FilterWheelPosition]
        self._filter_names = dict(zip(positions[1:], filter_names))
        self._filter_names[FilterWheelPosition.UNKNOW] = 'UNKNOWN'

        # window and binning
        self._window = None
        self._binning = None

    def open(self):
        """Open module.

        Raises:
            ValueError: If cannot connect to camera or set filter wheel.
        """
        BaseCamera.open(self)

        # set filter wheel model
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            log.info('Initialising filter wheel...')
            try:
                self._cam.set_filter_wheel(self._filter_wheel)
            except ValueError as e:
                raise ValueError('Could not set filter wheel: %s' % str(e))

        # open driver
        log.info('Opening SBIG driver...')
        try:
            self._cam.establish_link()
        except ValueError as e:
            raise ValueError('Could not establish link: %s' % str(e))

        # get window and binning from camera
        self._window = self.get_full_frame()
        self._binning = {'x': 1, 'y': 1}

        # cooling
        self.set_cooling(self._setpoint is not None, self._setpoint)

    def close(self):
        """Close module."""
        BaseCamera.close(self)

    def get_full_frame(self, *args, **kwargs) -> dict:
        """Returns full size of CCD.

        Returns:
            Dictionary with left, top, width, and height set.

        Raises:
            ValueError: If full frame could not be obtained.
        """
        width, height = self._cam.full_frame
        return {'left': 0, 'top': 0, 'width': width, 'height': height}

    def get_window(self, *args, **kwargs) -> dict:
        """Returns the camera window.

        Returns:
            Dictionary with left, top, width, and height set.
        """
        return self._window

    def get_binning(self, *args, **kwargs) -> dict:
        """Returns the camera binning.

        Returns:
            Dictionary with x and y.
        """
        return self._binning

    def set_window(self, left: float, top: float, width: float, height: float, *args, **kwargs):
        """Set the camera window.

        Args:
            left: X offset of window.
            top: Y offset of window.
            width: Width of window.
            height: Height of window.
        """
        self._window = {'left': int(left), 'top': int(top), 'width': int(width), 'height': int(height)}
        log.info('Setting window to %dx%d at %d,%d...', width, height, left, top)

    def set_binning(self, x: int, y: int, *args, **kwargs):
        """Set the camera binning.

        Args:
            x: X binning.
            y: Y binning.
        """
        self._binning = {'x': int(x), 'y': int(y)}
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

        # set window/binning and exposure time
        self._cam.binning = self._binning
        self._cam.window = self._window
        self._cam.exposure_time = exposure_time / 1000.

        # set exposing
        self._camera_status = ICamera.ExposureStatus.EXPOSING

        # get date obs
        log.info('Starting exposure with %s shutter for %.2f seconds...',
                 'open' if open_shutter else 'closed', exposure_time / 1000.)
        date_obs = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")

        # init image
        self._img.image_can_close = False

        # start exposure (can raise ValueError)
        self._cam.expose(self._img, open_shutter)

        # wait for readout
        log.info('Exposure finished, reading out...')
        self._camera_status = ICamera.ExposureStatus.READOUT

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
        hdu.header['XBINNING'] = hdu.header['DET-BIN1'] = (self._binning['x'], 'Binning factor used on X axis')
        hdu.header['YBINNING'] = hdu.header['DET-BIN2'] = (self._binning['y'], 'Binning factor used on Y axis')

        # window
        hdu.header['XORGSUBF'] = (self._window['left'], 'Subframe origin on X axis')
        hdu.header['YORGSUBF'] = (self._window['top'], 'Subframe origin on Y axis')

        # statistics
        hdu.header['DATAMIN'] = (float(np.min(data)), 'Minimum data value')
        hdu.header['DATAMAX'] = (float(np.max(data)), 'Maximum data value')
        hdu.header['DATAMEAN'] = (float(np.mean(data)), 'Mean data value')

        # biassec/trimsec
        full = self.get_full_frame()
        self.set_biassec_trimsec(hdu.header, full['left'], full['top'], full['width'], full['height'])

        # return FITS image
        log.info('Readout finished.')
        self._camera_status = ICamera.ExposureStatus.IDLE
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

        # set it
        self._cam.set_filter(filters[filter_name])

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

        # get current position and status
        position, _ = self._cam.get_filter_position_and_status()
        return self._filter_names[position]

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

    def status(self, *args, **kwargs) -> dict:
        """Returns current status of camera.

        Raises:
            ValueError: If status cannot be obtained.
        """

        # get status from parent
        s = super().status()

        # do we have a filter wheel?
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            # get filter
            filter_name = self.get_filter()

            # filter
            s['IFilter'] = {
                'Filter': filter_name
            }

        # get cooling
        enabled, temp, setpoint, _ = self._cam.get_cooling()

        # add cooling stuff
        s['ICooling'] = {
            'Enabled': enabled,
            'SetPoint': setpoint,
            'Temperatures': {
                'CCD': temp
            }
        }

        # finished
        return s


__all__ = ['SbigCamera']
