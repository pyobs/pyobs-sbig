# distutils: language = c++

import logging
import threading
from datetime import datetime
from astropy.io import fits

from pyobs.events import FilterChangedEvent
from pyobs.interfaces import ICamera, ICameraWindow, ICameraBinning, IFilters, ICooling
from pyobs.modules.camera.basecamera import BaseCamera
from pyobs.utils.threads import LockWithAbort

from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigCamera(BaseCamera, ICamera, ICameraWindow, ICameraBinning, ICooling):
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
        self._filter_names[FilterWheelPosition.UNKNOWN] = 'UNKNOWN'

        # if we have a filter wheel, add base class
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            cls = self.__class__
            self.__class__ = cls.__class__("SbigCamera", tuple([cls] + [IFilters]), {})

            # update interfaces description
            self._get_interfaces_and_methods()
            self.comm.module = self

        # allow to abort motion (filter wheel)
        self._lock_motion = threading.Lock()
        self._abort_motion = threading.Event()

        # window and binning
        self._full_frame = None
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
        self._binning = (1, 1)

        # cooling
        self.set_cooling(self._setpoint is not None, self._setpoint)

        # set binning to 1x1 and get full frame
        self._cam.binning = self._binning
        self._full_frame = (0, 0, *self._cam.full_frame)

        # subscribe to events
        if self.comm:
            self.comm.register_event(FilterChangedEvent)

    def close(self):
        """Close module."""
        BaseCamera.close(self)

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

        # set window
        wnd = (self._window[0], self._window[1], self._window[2] / self._binning[0], self._window[3] / self._binning[1])
        self._cam.window = wnd

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

        # filter
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            hdu.header['FILTER'] = (self.get_filter(), 'Current filter')

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

    def get_cooling_status(self, *args, **kwargs) -> (bool,  float, float):
        """Returns the current status for the cooling.

        Returns:
            Tuple containing:
                Enabled (bool):         Whether the cooling is enabled
                SetPoint (float):       Setpoint for the cooling in celsius.
                Power (float):          Current cooling power in percent or None.
        """
        enabled, temp, setpoint, _ = self._cam.get_cooling()
        return enabled, temp, 0, {'CCD': temp}

    def get_temperatures(self, *args, **kwargs) -> dict:
        """Returns all temperatures measured by this module.

        Returns:
            Dict containing temperatures.
        """
        _, temp, _, _ = self._cam.get_cooling()
        return {
            'CCD': temp
        }

    def _abort_exposure(self):
        """Abort the running exposure. Should be implemented by derived class.

        Raises:
            ValueError: If an error occured.
        """
        self._cam.abort()
        self._change_exposure_status(ICamera.ExposureStatus.IDLE)


__all__ = ['SbigCamera']
