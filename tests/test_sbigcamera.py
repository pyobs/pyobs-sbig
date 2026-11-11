"""Unit tests for the non-hardware logic in SbigCamera: constructor defaults, the
window/binning setters, and the _run_blocking/_run_blocking_or_raise wrappers.

Hardware I/O (establishing the link, exposing, reading out) is out of scope here.
"""

import asyncio
import threading
from unittest.mock import AsyncMock

import pytest
from pyobs.interfaces import IBinning, IWindow

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
    camera.comm.set_state = AsyncMock()  # type: ignore[method-assign]

    await camera.set_window(10, 20, 100, 200)

    assert camera._window == (10, 20, 100, 200)
    assert camera.comm.set_state.await_args is not None
    interface, state = camera.comm.set_state.await_args.args
    assert interface is IWindow
    assert (state.x, state.y, state.width, state.height) == (10, 20, 100, 200)


@pytest.mark.asyncio
async def test_set_binning() -> None:
    camera = SbigCamera()
    camera.comm.set_state = AsyncMock()  # type: ignore[method-assign]

    await camera.set_binning(2, 3)

    assert camera._binning == (2, 3)
    assert camera.comm.set_state.await_args is not None
    interface, state = camera.comm.set_state.await_args.args
    assert interface is IBinning
    assert (state.x, state.y) == (2, 3)


@pytest.mark.asyncio
async def test_full_reset_restores_cooling() -> None:
    camera = SbigCamera(setpoint=-15.0)
    camera.reset = AsyncMock()  # type: ignore[method-assign]
    camera.set_cooling = AsyncMock()  # type: ignore[method-assign]

    await camera.full_reset()

    camera.reset.assert_awaited_once()
    camera.set_cooling.assert_awaited_once_with(True, -15.0)


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


def make_cooling_camera(temp: float = -9.5, setpoint: float = -10.0, enabled: bool = True) -> SbigCamera:
    """Camera with a fake SBIG driver whose sensor follows the setpoint."""
    from unittest.mock import MagicMock

    camera = SbigCamera()
    camera.comm.set_state = AsyncMock()  # type: ignore[method-assign]
    state = {"enabled": enabled, "setpoint": setpoint, "temp": temp}

    def set_cooling(on: bool, value: float) -> None:
        state["enabled"], state["setpoint"] = on, value
        if on:
            state["temp"] = value + 0.5

    cam = MagicMock()
    cam.set_cooling.side_effect = set_cooling
    cam.get_cooling.side_effect = lambda: (state["enabled"], state["temp"], state["setpoint"], 0.3)
    camera._cam = cam
    return camera


@pytest.mark.asyncio
async def test_set_cooling_queues_ramp_without_touching_camera() -> None:
    camera = make_cooling_camera()

    await camera.set_cooling(True, -20.0)

    assert camera.cooling_ramping
    camera._cam.set_cooling.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ramp_steps_down_from_hardware_setpoint() -> None:
    camera = make_cooling_camera()
    await camera.set_cooling(True, -13.0)

    while camera.cooling_ramping:
        await camera._cooling_tick()

    calls = camera._cam.set_cooling.call_args_list  # type: ignore[attr-defined]
    assert [c.args for c in calls] == [(True, -11.0), (True, -12.0), (True, -13.0)]


@pytest.mark.asyncio
async def test_disable_warms_up_then_switches_off_with_20_degrees() -> None:
    camera = make_cooling_camera()
    await camera.set_cooling(False, 0.0)

    for _ in range(100):
        if not camera.cooling_ramping:
            break
        await camera._cooling_tick()

    calls = camera._cam.set_cooling.call_args_list  # type: ignore[attr-defined]
    assert calls[0].args == (True, -9.0)  # raised step by step first
    assert calls[-1].args == (False, 20.0)
    assert not camera.cooling_ramping
