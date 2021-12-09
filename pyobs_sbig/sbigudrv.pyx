# distutils: language = c++
import threading
import time
from enum import Enum
from contextlib import contextmanager
from typing import Tuple

import numpy as np
cimport numpy as np
np.import_array()

from .sbigudrv cimport *


@contextmanager
def acquire_lock(lock):
    if not lock.acquire(timeout=1):
        raise ValueError('Could not acquire exclusive lock on camera.')
    yield
    lock.release()


class FilterWheelModel(Enum):
    UNKNOWN = CFW_MODEL_SELECT.CFWSEL_UNKNOWN
    CFW2 = CFW_MODEL_SELECT.CFWSEL_CFW2
    CFW5 = CFW_MODEL_SELECT.CFWSEL_CFW5
    CFW8 = CFW_MODEL_SELECT.CFWSEL_CFW8
    CFWL = CFW_MODEL_SELECT.CFWSEL_CFWL
    CFW402 = CFW_MODEL_SELECT.CFWSEL_CFW402
    AUTO = CFW_MODEL_SELECT.CFWSEL_AUTO
    CFW6A = CFW_MODEL_SELECT.CFWSEL_CFW6A
    CFW10 = CFW_MODEL_SELECT.CFWSEL_CFW10
    CFW10_SERIAL = CFW_MODEL_SELECT.CFWSEL_CFW10_SERIAL
    CFW9 = CFW_MODEL_SELECT.CFWSEL_CFW9
    CFWL8 = CFW_MODEL_SELECT.CFWSEL_CFWL8
    CFWL8G = CFW_MODEL_SELECT.CFWSEL_CFWL8G
    CFW1603 = CFW_MODEL_SELECT.CFWSEL_CFW1603
    FW5_STX = CFW_MODEL_SELECT.CFWSEL_FW5_STX
    FW5_8300 = CFW_MODEL_SELECT.CFWSEL_FW5_8300
    FW8_8300 = CFW_MODEL_SELECT.CFWSEL_FW8_8300
    FW7_STX = CFW_MODEL_SELECT.CFWSEL_FW7_STX
    FW8_STT = CFW_MODEL_SELECT.CFWSEL_FW8_STT


class FilterWheelComPort(Enum):
    COM1 = CFW_COM_PORT.CFWPORT_COM1
    COM2 = CFW_COM_PORT.CFWPORT_COM2
    COM3 = CFW_COM_PORT.CFWPORT_COM3
    COM4 = CFW_COM_PORT.CFWPORT_COM4


class FilterWheelPosition(Enum):
    UNKNOWN = CFW_POSITION.CFWP_UNKNOWN
    CFWP_1 = CFW_POSITION.CFWP_1
    CFWP_2 = CFW_POSITION.CFWP_2
    CFWP_3 = CFW_POSITION.CFWP_3
    CFWP_4 = CFW_POSITION.CFWP_4
    CFWP_5 = CFW_POSITION.CFWP_5
    CFWP_6 = CFW_POSITION.CFWP_6
    CFWP_7 = CFW_POSITION.CFWP_7
    CFWP_8 = CFW_POSITION.CFWP_8
    CFWP_9 = CFW_POSITION.CFWP_9
    CFWP_10 = CFW_POSITION.CFWP_10


class FilterWheelStatus(Enum):
    UNKNOWN = CFW_STATUS.CFWS_UNKNOWN
    IDLE = CFW_STATUS.CFWS_IDLE
    BUSY = CFW_STATUS.CFWS_BUSY


class ActiveSensor(Enum):
    IMAGING = CCD_REQUEST.CCD_IMAGING
    TRACKING = CCD_REQUEST.CCD_TRACKING
    EXT_TRACKING = CCD_REQUEST.CCD_EXT_TRACKING


cdef class SBIGImg:
    cdef CSBIGImg* obj

    def __cinit__(self):
        self.obj = new CSBIGImg()

    @property
    def image_can_close(self) -> bool:
        return self.obj.GetImageCanClose()

    @image_can_close.setter
    def image_can_close(self, can_do: bool):
        self.obj.SetImageCanClose(can_do)

    @property
    def data(self):
        # get image dimensions
        width, height = self.obj.GetWidth(), self.obj.GetHeight()

        # create a C array to describe the shape of the ndarray
        cdef np.npy_intp shape[1]
        shape[0] = <np.npy_intp>(width * height)

        # Use the PyArray_SimpleNewFromData function from numpy to create a
        # new Python object pointing to the existing data
        arr = np.PyArray_SimpleNewFromData(1, shape, np.NPY_USHORT, <void *>self.obj.GetImagePointer())

        # reshape it to 2D
        return arr.reshape(height, width)


cdef class SBIGCam:
    cdef CSBIGCam* obj
    cdef object aborted
    cdef object lock

    def __cinit__(self):
        self.obj = new CSBIGCam(SBIG_DEVICE_TYPE.DEV_USB)

    def __init__(self):
        self.aborted = False
        self.lock = threading.Lock()

    def establish_link(self):
        res = self.obj.EstablishLink()
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))

    @property
    def sensor(self) -> ActiveSensor:
        with acquire_lock(self.lock):
            return ActiveSensor(self.obj.GetActiveCCD())

    @sensor.setter
    def sensor(self, camera: ActiveSensor):
        with acquire_lock(self.lock):
            self.obj.SetActiveCCD(camera.value)

    @property
    def readout_mode(self):
        with acquire_lock(self.lock):
            return self.obj.GetReadoutMode()

    @readout_mode.setter
    def readout_mode(self, rm):
        with acquire_lock(self.lock):
            self.obj.SetReadoutMode(rm)

    @property
    def full_frame(self) -> Tuple[int, int, int, int]:
        # define width and height
        cdef int width = 0
        cdef int height = 0

        # acquire lock
        with acquire_lock(self.lock):
            # call library
            res = self.obj.GetFullFrame(width, height)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))
            return 0, 0, width, height

    @property
    def window(self):
        # define left, top, width and height
        cdef int left = 0
        cdef int top = 0
        cdef int width = 0
        cdef int height = 0

        # acquire lock
        with acquire_lock(self.lock):
            # call library
            self.obj.GetSubFrame(left, top, width, height)
            return left, top, width, height

    @window.setter
    def window(self, wnd):
        # set window
        with acquire_lock(self.lock):
            self.obj.SetSubFrame(wnd[0], wnd[1], wnd[2], wnd[3])

    @property
    def binning(self):
        # acquire lock
        with acquire_lock(self.lock):
            # get readout mode
            mode = self.obj.GetReadoutMode()

            # return it
            # 0 = No binning, high resolution
            # 1 = 2x2 on-chip binning, medium resolution
            # 2 = 3x3 on-chip binning, low resolution (ST-7/8/etc/237 only)
            if mode in [0, 1, 2]:
                return mode + 1, mode + 1
            else:
                raise ValueError('Unknown readout mode.')

    @binning.setter
    def binning(self, binning):
        # check
        if binning[0] != binning[1] or binning[0] < 1 or binning[0] > 3:
            raise ValueError('Only 1x1, 2x2, and 3x3 binnings supported.')

        # set it
        with acquire_lock(self.lock):
            self.obj.SetReadoutMode(binning[0] - 1)

    @property
    def exposure_time(self):
        with acquire_lock(self.lock):
            return self.obj.GetExposureTime()

    @exposure_time.setter
    def exposure_time(self, exp):
        with acquire_lock(self.lock):
            self.obj.SetExposureTime(exp)

    @property
    def temperature(self):
        cdef double temp = 0

        # acquire lock
        with acquire_lock(self.lock):
            # get temp
            res = self.obj.GetCCDTemperature(temp)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))
            return temp

    def set_cooling(self, enable: bool, setpoint: float):
        # acquire lock
        with acquire_lock(self.lock):
            res = self.obj.SetTemperatureRegulation(enable, setpoint)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))

    def get_cooling(self):
        # define vars
        cdef MY_LOGICAL enabled = 0
        cdef double temp = 0.
        cdef double setpoint = 0.
        cdef double power = 0.

        # acquire lock
        with acquire_lock(self.lock):
            # get it
            res = self.obj.QueryTemperatureStatus(enabled, temp, setpoint, power)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))
            return enabled == 1, temp, setpoint, power

    def abort(self):
        # abort exposure
        self.aborted = True

    def was_aborted(self):
        return self.aborted

    def start_exposure(self, img: SBIGImg, shutter: bool):
         # define vars
        cdef MY_LOGICAL complete = 0

        # acquire lock
        with acquire_lock(self.lock):
            # not aborted
            self.aborted = False

            # get mode
            mode = SBIG_DARK_FRAME.SBDF_LIGHT_ONLY if shutter else SBIG_DARK_FRAME.SBDF_DARK_ONLY

            # do setup
            res = self.obj.GrabSetup(img.obj, mode)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))

            # end current exposure, if any
            res = self.obj.EndExposure()
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))

            # start exposure
            shutter_cmd = SHUTTER_COMMAND.SC_OPEN_SHUTTER if shutter else  SHUTTER_COMMAND.SC_CLOSE_SHUTTER
            res = self.obj.StartExposure(shutter_cmd)
            if res != 0:
                raise ValueError('Could not start exposure: ' + self.obj.GetErrorString(res))

    def has_exposure_finished(self):
         # define vars
        cdef MY_LOGICAL complete = 0

        # acquire lock
        with acquire_lock(self.lock):
            # is complete?
            res = self.obj.IsExposureComplete(complete)
            if res != 0:
                raise ValueError('Could not get exposure status: ' + self.obj.GetErrorString(res))

            # break on error or if complete or aborted
            return res != 0 or complete

    def end_exposure(self):
        # acquire lock
        with acquire_lock(self.lock):
            res = self.obj.EndExposure()
            if res != 0:
                raise ValueError('Could not end exposure: ' + self.obj.GetErrorString(res))

    @staticmethod
    cdef int _readout(CSBIGCam *cam, CSBIGImg *img, SBIG_DARK_FRAME mode) nogil:
        cdef int res = cam.Readout(img, mode)
        return res

    def readout(self, img: SBIGImg, shutter: bool):
        # get mode
        cdef SBIG_DARK_FRAME mode = SBIG_DARK_FRAME.SBDF_LIGHT_ONLY if shutter else SBIG_DARK_FRAME.SBDF_DARK_ONLY
        cdef int res = 0

        # acquire lock
        with acquire_lock(self.lock):
            # do readout
            with nogil:
                res = int(SBIGCam._readout(self.obj, img.obj, mode))
            if res != 0:
                raise ValueError(self.obj.GetErrorString(int(res)))

    def set_filter_wheel(self, wheel: FilterWheelModel, com_port: FilterWheelComPort = FilterWheelComPort.COM1):
        # acquire lock
        with acquire_lock(self.lock):
            res = self.obj.SetCFWModel(wheel.value, com_port.value)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))

    def set_filter(self, position: FilterWheelPosition):
        # acquire lock
        with acquire_lock(self.lock):
            res = self.obj.SetCFWPosition(position.value)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))

    def get_filter_position_and_status(self):
        # define vars
        cdef CFW_POSITION position = CFW_POSITION.CFWP_UNKNOWN
        cdef CFW_STATUS status = CFW_STATUS.CFWS_UNKNOWN

        # acquire lock
        with acquire_lock(self.lock):
            # request from driver
            res = self.obj.GetCFWPositionAndStatus(position, status)
            if res != 0:
                raise ValueError(self.obj.GetErrorString(res))

            # parse it, since for whatever reason, position can be a value not defined in CFW_POSITION...
            try:
                pos = FilterWheelPosition(position)
            except ValueError:
                pos = FilterWheelPosition.UNKNOWN

            # return it
            return pos, FilterWheelStatus(status)
