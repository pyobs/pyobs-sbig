import logging
import threading

from pyobs.images import Image
from .sbigfiltercamera import SbigFilterCamera


log = logging.getLogger(__name__)


class Sbig6303eCamera(SbigFilterCamera):
    """A pyobs module for SBIG6303e cameras."""
    __module__ = 'pyobs_sbig'

    def _expose(self, exposure_time: float, open_shutter: bool, abort_event: threading.Event) -> Image:
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

        # do expsure
        img = SbigFilterCamera._expose(self, exposure_time, open_shutter, abort_event)

        # get binning
        xbin, ybin = self.get_binning()

        # gain is different in binned images
        gain = (1.4, 'Detector gain [e-/ADU]') if xbin == ybin == 1 else (2.3, 'Detector gain [e-/ADU]')
        img.header['DET-GAIN'] = gain

        # finished
        return img


__all__ = ['Sbig6303eCamera']
