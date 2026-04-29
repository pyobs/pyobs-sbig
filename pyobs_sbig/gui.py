from astropy.io import fits
from pyobs.utils.enums import ImageFormat
from pyobs.utils.gui.camera import (
    DataDisplayWidget,
    BinningWidget,
    ImageFormatWidget,
    ExposureTimeWidget,
    ExposeWidget,
    ListPickerDialog,
)
from pyobs.utils.gui.camera.windowingwidget import WindowingWidget
from pyobs.utils.parallel import event_wait
import asyncio
import sys
import qasync  # type: ignore
from PySide6 import QtWidgets

from .sbigudrv import SBIGImg, SBIGCam  # type: ignore


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, device_name: bytes) -> None:
        super().__init__()

        # create image and cam
        self._img = SBIGImg()
        self._cam = SBIGCam()

        self._cam.establish_link()
        full_frame = self._cam.full_frame

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        global_layout = QtWidgets.QHBoxLayout()
        self.central_widget.setLayout(global_layout)
        self.widgets_frame = QtWidgets.QGroupBox()
        # self.fits_widget = QFitsWidget()
        self.data_display_widget = DataDisplayWidget()
        global_layout.addWidget(self.widgets_frame)
        global_layout.addWidget(self.data_display_widget)

        layout = QtWidgets.QVBoxLayout()
        self.widgets_frame.setLayout(layout)
        self.window_widget = WindowingWidget(full_frame[2], full_frame[3])
        layout.addWidget(self.window_widget)
        self.binning_widget = BinningWidget([(1, 1), (2, 2)])
        self.binning_widget.binning_changed.connect(self.window_widget.set_binning)
        layout.addWidget(self.binning_widget)
        self.exposure_time = ExposureTimeWidget()
        layout.addWidget(self.exposure_time)
        self.expose = ExposeWidget()
        layout.addWidget(self.expose)

        self.abort_exposure = asyncio.Event()
        self.expose.expose_clicked.connect(self._expose_clicked)
        self.expose.abort_clicked.connect(self._abort_clicked)

    @qasync.asyncSlot()  # type: ignore
    async def _expose_clicked(self) -> None:
        # init image
        self._img.image_can_close = False

        # set exposure time, window and binning
        self._cam.exposure_time = self.exposure_time.value
        self._cam.window = self.window_widget.values
        self._cam.binning = (1, 1)

        # start exposure
        self._cam.start_exposure(self._img, False)

        # wait for it
        while not self._cam.has_exposure_finished():
            await asyncio.sleep(0.01)

        # finish exposure
        self._cam.end_exposure()

        # wait for readout
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._cam.readout, self._img, False)

        # finalize image
        self._img.image_can_close = True

        # download data
        data = self._img.data

        self.expose.set_exposures_left()
        image = fits.PrimaryHDU(data)
        self.data_display_widget.set_data(image)

    @qasync.asyncSlot()  # type: ignore
    async def _abort_clicked(self) -> None:
        self.abort_exposure.set()
        self.abort_exposure = asyncio.Event()


async def async_main(app: QtWidgets.QApplication) -> None:
    # connect()
    devices = QHYCCDDriver.list_devices()
    if len(devices) == 0:
        print("No devices found. Exiting...")
        return
    device_picker = ListPickerDialog([d.decode("utf-8") for d in devices])
    if device_picker.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        print("No device selected. Exiting...")
        return
    device_name = devices[device_picker.comboBox().currentIndex()]

    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)
    main_window = MainWindow(device_name)
    main_window.show()
    await app_close_event.wait()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    asyncio.run(async_main(app), loop_factory=qasync.QEventLoop)  # type: ignore


if __name__ == "__main__":
    main()
