"""Tests for the FITS header the GUI writes."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

try:
    from pyobs_sbig.gui import make_header
except ImportError as e:  # no Qt extras, or the camera library is not installed
    pytest.skip(f"GUI cannot be imported: {e}", allow_module_level=True)


class FakeCam:
    def get_cooling(self) -> tuple[bool, float, float, float]:
        return True, -9.5, -10.0, 0.5


DATE = datetime(2026, 11, 17, 10, 0, 0, tzinfo=UTC)
DATA = np.array([[1, 2], [3, 6]], dtype=np.uint16)


def test_header_has_the_module_keys() -> None:
    h = make_header(FakeCam(), DATE, 5.0, (10, 20, 100, 100), (2, 2), DATA)  # type: ignore[arg-type]
    assert h["EXPTIME"] == 5.0 and h["DATE-OBS"] == "2026-11-17T10:00:00.000000"
    assert h["DET-TEMP"] == -9.5 and h["DET-TSET"] == -10.0 and h["DET-COOL"] == 50
    assert h["DET-BIN1"] == 2 and h["XORGSUBF"] == 20 and h["YORGSUBF"] == 40
    assert (h["DATAMIN"], h["DATAMAX"], h["DATAMEAN"]) == (1.0, 6.0, 3.0)
