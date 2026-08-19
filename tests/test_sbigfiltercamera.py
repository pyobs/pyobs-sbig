"""Unit tests for the non-hardware logic in SbigFilterCamera: filter-name mapping
and set_filter validation.

The SBIG Universal Driver is mocked out / not touched; only the name<->position
mapping and validation are exercised.
"""

import pytest
from pyobs.utils import exceptions as exc
from pyobs.utils.enums import MotionStatus

from pyobs_sbig import SbigFilterCamera


def test_constructor_threads_kwargs_cooperatively() -> None:
    """Locks in the cooperative-super()-chain conversion: SbigFilterCamera(MotionStatusMixin,
    SbigCamera, ...) used to call SbigCamera.__init__() then a separate, redundant
    MotionStatusMixin.__init__(self, **kwargs, motion_status_interfaces=[...]).

    Unlike the equivalent fix in pyobs-alpaca/pyobs-brot/pyobs-iagvt, there's no kwarg that
    demonstrates a "raises pre-fix, passes post-fix" regression here: motion_status_interfaces
    is the only kwarg MotionStatusMixin's chain needs and it's hardcoded at the call site, so a
    caller passing it explicitly collides (`got multiple values`) both before and after this fix
    rather than leaking. Every other kwarg these live configs set (filter_wheel, filter_names,
    setpoint, fits_headers, comm) is already consumed by SbigCamera's own chain and re-consumes
    cleanly on the old redundant second pass too. This test instead locks in that construction
    with a representative, live-config-shaped kwarg set succeeds and mixin state lands
    correctly -- the actual fix is a correctness/consistency cleanup, not a crash fix, for this
    particular class."""
    camera = SbigFilterCamera(
        filter_wheel="CFW10",
        setpoint=-15.0,
        fits_headers={"DET-PIXL": (0.0054, "Pixel size")},
        comm={"class": "pyobs.comm.dummy.DummyComm"},
    )
    assert camera.motion_status() == MotionStatus.UNKNOWN


def test_filter_names_default() -> None:
    camera = SbigFilterCamera(filter_wheel="CFW10")
    assert "UNKNOWN" in camera._filter_names.values()
    assert len(camera._filter_names) == 11  # 10 positions + UNKNOWN


def test_filter_names_custom() -> None:
    names = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    camera = SbigFilterCamera(filter_wheel="CFW10", filter_names=names)
    assert set(names).issubset(set(camera._filter_names.values()))


@pytest.mark.asyncio
async def test_set_filter_unknown_name() -> None:
    camera = SbigFilterCamera(filter_wheel="CFW10")
    with pytest.raises(exc.InvalidArgumentError):
        await camera.set_filter("does-not-exist")
