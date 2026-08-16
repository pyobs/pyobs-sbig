"""Smoke tests: import the drivers and instantiate them without hardware, asserting
the interfaces they claim.

The Cython extension (sbigudrv) links the bundled SBIG Universal Driver during
install, but the device link is only established inside open(), so instantiation is
safe with no SBIG hardware attached.
"""

from pyobs.interfaces import IAbortable, IBinning, ICamera, ICooling, IFilters, ITemperatures, IWindow
from pyobs.modules import Module

from pyobs_sbig import Sbig6303eCamera, SbigCamera, SbigFilterCamera


def test_instantiate_camera() -> None:
    camera = SbigCamera()
    assert isinstance(camera, Module)
    assert isinstance(camera, ICamera)
    assert isinstance(camera, IWindow)
    assert isinstance(camera, IBinning)
    assert isinstance(camera, ICooling)
    assert isinstance(camera, ITemperatures)
    assert isinstance(camera, IAbortable)


def test_instantiate_filter_camera() -> None:
    camera = SbigFilterCamera(filter_wheel="CFW10")
    assert isinstance(camera, Module)
    assert isinstance(camera, IFilters)


def test_instantiate_6303e() -> None:
    camera = Sbig6303eCamera(filter_wheel="CFW10")
    assert isinstance(camera, Module)
    assert isinstance(camera, IFilters)
