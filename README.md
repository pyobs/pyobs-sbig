SBIG module for *pyobs*
========================

This is a [pyobs](https://www.pyobs.org) module for SBIG cameras.


Install SBIG driver
--------------------
Download the SBIG Universal Driver package from ftp://ftp.sbig.com/pub/devsw/LinuxDevKit.tar.gz and follow
the installation instructions in the README.txt.

**Note:** The files in the *src/pyobs_sbig/sbigudrv/* directory are part of this archive, and the *CSBIGCam*
class has been modified to include a *Readout()* method.


Install *pyobs-sbig*
---------------------
Clone the repository:

    git clone https://github.com/pyobs/pyobs-sbig.git
    cd pyobs-sbig

Install it with [uv](https://docs.astral.sh/uv/):

    uv sync

Alternatively, with plain `venv`/`pip`:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install .


Configuration
-------------
The base class for all SBIG cameras is *SbigCamera*, which can be used for camera types without an integrated
filter wheel and adds a single new parameter:

    setpoint:
        The initial setpoint in degrees Celsius for the cooling of the camera.

A basic module configuration would look like this:

    class: pyobs_sbig.SbigCamera
    name: SBIG camera
    setpoint: -10

For cameras with an integrated filter wheel, use *SbigFilterCamera* instead, which adds:

    filter_wheel:
        Model of the filter wheel, e.g. CFW10.
    filter_names:
        List of filter names (default: numbered 1-10).

    class: pyobs_sbig.SbigFilterCamera
    name: SBIG camera
    setpoint: -10
    filter_wheel: CFW10
    filter_names: [Red, Green, Blue, Clear, Halpha]

There is also a special implementation for SBIG-6303E cameras, *Sbig6303eCamera*, which takes the same parameters
as *SbigFilterCamera*.


GUI
---
For testing a camera without a full *pyobs* setup, install the optional `gui` extra:

    uv sync --extra gui

and run:

    uv run sbig-gui


Dependencies
------------
* [pyobs-core](https://github.com/pyobs/pyobs-core) for the core functionality.
* [Cython](https://cython.org/) for wrapping the SBIG Universal Driver.
* [Astropy](http://www.astropy.org/) for FITS file handling.
* [NumPy](http://www.numpy.org/) for array handling.
