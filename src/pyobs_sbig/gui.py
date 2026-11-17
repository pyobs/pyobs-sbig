import asyncio
import sys
import time
from datetime import UTC, datetime
from typing import Any

import qasync  # type: ignore
from astropy.io import fits
from numpy.typing import NDArray
from pyobs.utils.frameheader import FrameSettings, make_frame_header
from pyobs.utils.gui.camera import (
    BinningWidget,
    DataDisplayWidget,
    ExposeWidget,
    ExposureTimeWidget,
)
from pyobs.utils.gui.camera.windowingwidget import WindowingWidget
from PySide6 import QtWidgets

from .sbigudrv import SBIGCam, SBIGImg  # type: ignore


def make_header(
    cam: SBIGCam,
    date_obs: datetime,
    exposure_time: float,
    window: tuple[int, int, int, int],
    binning: tuple[int, int],
    data: NDArray[Any],
) -> fits.Header:
    """Builds the FITS header for a frame, reading temperature and cooling from the camera (blocking).

    Args:
        cam: Camera to read the cooling from.
        date_obs: UTC time the exposure was started.
        exposure_time: Exposure time in seconds.
        window: Left, top, width and height of the window in binned pixels, as the camera takes them.
        binning: Binning in x and y.
        data: The frame.

    Returns:
        The header.
    """
    _, temp, setpoint, power = cam.get_cooling()
    return make_frame_header(
        FrameSettings(
            date_obs=date_obs,
            exposure_time=exposure_time,
            binning=binning,
            # the camera takes the window in binned pixels, FITS wants unbinned ones
            window=(
                window[0] * binning[0],
                window[1] * binning[1],
                window[2] * binning[0],
                window[3] * binning[1],
            ),
            temperature=temp,
            setpoint=setpoint,
            cooler_power=round(power * 100),
            data=data,
        )
    )


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
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
        # get current binning from the widget
        binning = self.binning_widget._binnings[self.binning_widget.combo_binnings.currentIndex()]

        # init image
        self._img.image_can_close = False

        loop = asyncio.get_running_loop()

        # set exposure time, window and binning, then start the exposure off the Qt thread
        date_obs = datetime.now(UTC)
        exposure_time = self.exposure_time.value
        window = self.window_widget.values

        def _start() -> None:
            self._cam.exposure_time = exposure_time
            self._cam.window = window
            self._cam.binning = binning
            self._cam.start_exposure(self._img, False)

        self.abort_exposure.clear()
        await loop.run_in_executor(None, _start)

        # wait for it off the Qt thread, checking the abort event
        def _wait() -> bool:
            while not self._cam.has_exposure_finished():
                if self.abort_exposure.is_set():
                    return True
                time.sleep(0.01)
            return False

        aborted = await loop.run_in_executor(None, _wait)

        if aborted:
            # abort the exposure in the camera
            await loop.run_in_executor(None, self._cam.end_exposure)
            self._img.image_can_close = True
            self.expose.set_exposures_left()
            return

        # finish exposure
        await loop.run_in_executor(None, self._cam.end_exposure)

        # wait for readout
        await loop.run_in_executor(None, self._cam.readout, self._img, False)

        # finalize image
        self._img.image_can_close = True

        # download data
        data = self._img.data

        self.expose.set_exposures_left()
        header = await loop.run_in_executor(
            None, make_header, self._cam, date_obs, exposure_time, window, binning, data
        )
        image = fits.PrimaryHDU(data, header=header)
        self.data_display_widget.set_data(image)

    @qasync.asyncSlot()  # type: ignore
    async def _abort_clicked(self) -> None:
        self.abort_exposure.set()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._cam.close()
        super().closeEvent(event)


async def async_main(app: QtWidgets.QApplication) -> None:
    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)
    main_window = MainWindow()
    main_window.show()
    await app_close_event.wait()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    asyncio.run(async_main(app), loop_factory=qasync.QEventLoop)  # type: ignore


if __name__ == "__main__":
    main()
