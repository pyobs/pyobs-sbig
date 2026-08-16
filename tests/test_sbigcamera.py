"""Unit tests for the non-hardware logic in SbigCamera: constructor defaults, the
window/binning setters, and the _run_blocking/_run_blocking_or_raise wrappers.

Hardware I/O (establishing the link, exposing, reading out) is out of scope here.
"""

import asyncio
import threading

import pytest

from pyobs_sbig import SbigCamera


def test_constructor_defaults() -> None:
    camera = SbigCamera()
    assert camera._setpoint == -20
    assert camera._window == (0, 0, 0, 0)
    assert camera._binning == (1, 1)
    assert camera._full_frame == (0, 0, 0, 0)


@pytest.mark.asyncio
async def test_set_window() -> None:
    camera = SbigCamera()
    await camera.set_window(10, 20, 100, 200)
    assert camera._window == (10, 20, 100, 200)


@pytest.mark.asyncio
async def test_set_binning() -> None:
    camera = SbigCamera()
    await camera.set_binning(2, 2)
    assert camera._binning == (2, 2)


@pytest.mark.asyncio
async def test_run_blocking_runs_func_and_returns_true() -> None:
    ran: list[bool] = []

    def fast() -> None:
        ran.append(True)

    assert await SbigCamera._run_blocking(fast) is True
    assert ran == [True]


@pytest.mark.asyncio
async def test_run_blocking_times_out() -> None:
    done = threading.Event()

    def slow() -> None:
        done.wait()

    assert await SbigCamera._run_blocking(slow, timeout=0.01) is False
    done.set()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_run_blocking_or_raise_returns_value() -> None:
    camera = SbigCamera()
    assert await camera._run_blocking_or_raise(lambda: 42) == 42


@pytest.mark.asyncio
async def test_run_blocking_or_raise_reraises() -> None:
    camera = SbigCamera()

    def boom() -> int:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await camera._run_blocking_or_raise(boom)
