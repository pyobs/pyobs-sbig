# distutils: language = c++
import time

import numpy as np
cimport numpy as np
np.import_array()

from .sbigudrv cimport CSBIGCam, CSBIGImg, SBIG_DARK_FRAME


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

        # reshape it
        return arr.reshape((height, width))


cdef class SBIGCam:
    cdef CSBIGCam* obj

    def __cinit__(self):
        self.obj = new CSBIGCam(SBIG_DEVICE_TYPE.DEV_USB)

    def establish_link(self):
        res = self.obj.EstablishLink()
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))

    @property
    def readout_mode(self):
        return self.obj.GetReadoutMode()

    @readout_mode.setter
    def readout_mode(self, rm):
        self.obj.SetReadoutMode(rm)

    @property
    def full_frame(self):
        # define width and height
        cdef int width = 0
        cdef int height = 0

        # call library
        res = self.obj.GetFullFrame(width, height)
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))

        # finished
        return width, height

    @property
    def window(self):
        # define left, top, width and height
        cdef int left = 0
        cdef int top = 0
        cdef int width = 0
        cdef int height = 0

        # call library
        self.obj.GetSubFrame(left, top, width, height)
        return {'left': left, 'top': top, 'width': width, 'height': height}

    @window.setter
    def window(self, wnd: dict):
        # set window
        self.obj.SetSubFrame(wnd['left'], wnd['top'], wnd['width'], wnd['height'])

    @property
    def binning(self):
        # get readout mode
        mode = self.obj.GetReadoutMode()

        # return it
        # 0 = No binning, high resolution
        # 1 = 2x2 on-chip binning, medium resolution
        # 2 = 3x3 on-chip binning, low resolution (ST-7/8/etc/237 only)
        if mode in [0, 1, 2]:
            return {'x': mode + 1, 'y': mode + 1}
        else:
            raise ValueError('Unknown readout mode.')

    @binning.setter
    def binning(self, binning):
        # check
        if binning['x'] != binning['y'] or binning['x'] < 0 or binning['x'] > 2:
            raise ValueError('Only 1x1, 2x2, and 3x3 binnings supported.')

        # set it
        self.obj.SetReadoutMode(binning['x'] - 1)

    @property
    def exposure_time(self):
        return self.obj.GetExposureTime()

    @exposure_time.setter
    def exposure_time(self, exp):
        self.obj.SetExposureTime(exp)

    @property
    def temperature(self):
        # get temp
        cdef double temp = 0
        res = self.obj.GetCCDTemperature(temp)
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))
        return temp

    def set_cooling(self, enable: bool, setpoint: float):
        res = self.obj.SetTemperatureRegulation(enable, setpoint)
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))

    def get_cooling(self):
        # define vars
        cdef MY_LOGICAL enabled = 0
        cdef double temp = 0.
        cdef double setpoint = 0.
        cdef double power = 0.

        # get it
        res = self.obj.QueryTemperatureStatus(enabled, temp, setpoint, power)
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))

        # return it
        return enabled == 1, temp, setpoint, power

    def expose(self, img: SBIGImg, shutter: bool):
        # define vars
        cdef MY_LOGICAL complete = 0

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
            raise ValueError(self.obj.GetErrorString(res))

        # wait for exposure
        while True:
            # is complete?
            res = self.obj.IsExposureComplete(complete)

            # break on error or if complete
            if res != 0  or complete:
                break

            # sleep a little
            time.sleep(0.1)

        # end exposure
        res = self.obj.EndExposure()
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))

    def readout(self, img: SBIGImg, shutter: bool):
        # get mode
        mode = SBIG_DARK_FRAME.SBDF_LIGHT_ONLY if shutter else SBIG_DARK_FRAME.SBDF_DARK_ONLY

        # do readout
        res = self.obj.Readout(img.obj, mode)
        if res != 0:
            raise ValueError(self.obj.GetErrorString(res))