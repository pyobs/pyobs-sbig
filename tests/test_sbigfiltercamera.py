"""Unit tests for the non-hardware logic in SbigFilterCamera: filter-name mapping
and set_filter validation.

The SBIG Universal Driver is mocked out / not touched; only the name<->position
mapping and validation are exercised.
"""

import pytest
from pyobs.utils import exceptions as exc

from pyobs_sbig import SbigFilterCamera


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
