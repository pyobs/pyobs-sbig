# distutils: language = c++

import logging
import threading
from datetime import datetime
import numpy as np
from astropy.io import fits

from pytel.interfaces import ICamera, ICameraWindow, ICameraBinning, IFilters, ICooling
from pytel.modules.camera.basecamera import BaseCamera

from .sbigudrv import *


log = logging.getLogger(__name__)


class SbigCamera(BaseCamera, ICamera, ICameraWindow, ICameraBinning, IFilters, ICooling):
    def __init__(self, filter_wheel: str = 'UNKNOWN', filter_names: list = None, setpoint: float = -20,
                 *args, **kwargs):
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

    def open(self) -> bool:
        if not BaseCamera.open(self):
            return False

        # set filter wheel model
        if self._filter_wheel != FilterWheelModel.UNKNOWN:
            log.info('Initialising filter wheel...')
            try:
                self._cam.set_filter_wheel(self._filter_wheel)
            except ValueError as e:
                log.error('Could not set filter wheel: %s', e)
                return False

        # open driver
        log.info('Opening SBIG driver...')
        try:
            self._cam.establish_link()
        except ValueError as e:
            log.error('Could not establish link: %s', e)
            return False

        # get window and binning from camera
        self._window = self.get_full_frame()
        self._binning = {'x': 1, 'y': 1}

        # cooling
        self.set_cooling(self._setpoint is not None, self._setpoint)

    def close(self):
        BaseCamera.close(self)

    def get_full_frame(self, *args, **kwargs) -> dict:
        width, height = self._cam.full_frame
        return {'left': 0, 'top': 0, 'width': width, 'height': height}

    def get_window(self, *args, **kwargs) -> dict:
        return self._window

    def get_binning(self, *args, **kwargs) -> dict:
        return self._binning

    def set_window(self, left: int, top: int, width: int, height: int, *args, **kwargs) -> bool:
        self._window = {'left': int(left), 'top': int(top), 'width': int(width), 'height': int(height)}
        log.info('Setting window to %dx%d at %d,%d...', width, height, left, top)
        return True

    def set_binning(self, x: int, y: int, *args, **kwargs) -> bool:
        self._binning = {'x': int(x), 'y': int(y)}
        log.info('Setting binning to %dx%d...', x, y)
        return True

    def _expose(self, exposure_time: int, open_shutter: bool, abort_event: threading.Event) -> fits.PrimaryHDU:
        # set window/binning and exposure time
        self._cam.binning = self._binning
        self._cam.window = self._window
        self._cam.exposure_time = exposure_time / 1000.

        # set exposing
        self._camera_status = ICamera.CameraStatus.EXPOSING

        # get date obs
        log.info('Starting exposure with %s shutter for %.2f seconds...',
                 'open' if open_shutter else 'closed', exposure_time / 1000.)
        date_obs = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")

        # init image
        self._img.image_can_close = False

        # do exposure
        try:
            # start exposure
            self._cam.expose(self._img, open_shutter)
        except ValueError as e:
            log.error('Could not take image: %s', e)
            return None

        # wait for readout
        log.info('Exposure finished, reading out...')
        self._camera_status = ICamera.CameraStatus.READOUT
        try:
            # start readout
            self._cam.readout(self._img, open_shutter)
        except ValueError as e:
            log.error('Could not read out image: %s', e)
            return None

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
        self._camera_status = ICamera.CameraStatus.IDLE
        return hdu

    def set_cooling(self, enabled: bool, setpoint: float, *args, **kwargs) -> bool:
        # log
        if enabled:
            log.info('Enabling cooling with a setpoint of %.2f°C...', setpoint)
        else:
            log.info('Disabling cooling and setting setpoint to 20°C...')

        # do it
        try:
            self._cam.set_cooling(enabled, setpoint)
        except ValueError as e:
            log.error('Could not set cooling: %s', e)
            return False

        # success
        return True

    def set_filter(self, filter_name: str, *args, **kwargs) -> bool:
        # do we have a filter wheel?
        if self._filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # reverse dict and search for name
        filters = {y: x for x, y in self._filter_names.items()}
        if filter_name not in filters:
            raise ValueError('Unknown filter: %s', filter_name)

        # set it
        try:
            self._cam.set_filter(filters[filter_name])
            return True
        except ValueError as e:
            log.error('Could not set filter: %s', e)
            return False

    def get_filter(self, *args, **kwargs) -> str:
        # do we have a filter wheel?
        if self._filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        # get current position and status
        position, _ = self._cam.GetCFWPositionAndStatus()
        return self._filter_names[position]

    def list_filters(self, *args, **kwargs) -> list:
        # do we have a filter wheel?
        if self._filter_wheel == FilterWheelModel.UNKNOWN:
            raise NotImplementedError

        return [f for f in self._filter_names.values() if f is not None]

    def status(self, *args, **kwargs) -> dict:
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
