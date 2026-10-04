# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries for releases before this file existed were generated from commit subjects.

## [2.0.4] - 2026-09-28

- Maintenance release (dependency and metadata updates only).

## [2.0.3] - 2026-09-28

- Add IResettable.full_reset() override, moving cooling setup out of open()

## [2.0.2] - 2026-09-03

- Add DET-COOL (cooler power) FITS header (#872)
- Require stable pyobs-core>=2.0.0
- Fix RTD build: correct src/ layout, drop pip install .

## [2.0.1] - 2026-09-01

- Maintenance release (dependency and metadata updates only).

## [2.0.0] - 2026-08-26

- Require stable pyobs-core>=2.0.0
- Fix RTD build: correct src/ layout, drop pip install .
- Remove tracked __pycache__ files, add .gitignore
- Gate auto-merge on the PR author, not the event actor
- Enable Dependabot auto-merge for patch/minor updates
- Add cooperative-init construction test for SbigFilterCamera
- Convert SbigFilterCamera to cooperative super().__init__() chain
- Camera driver/GUI split: binning + abort fixes, driver close, gui offload, lock gap (#71)
- tests: assert comm.set_state call shape in window/binning tests
- pyrefly: exclude gui.py from type checking
- Add baseline test suite and CI (pytest, pyrefly), grouped Dependabot
- Build and publish manylinux wheels via cibuildwheel
- Upgrade uv.lock to clear open Dependabot alerts
- Require pyobs-core>=2.0.0.dev48
- Add dependabot.yml, targeting develop for PRs
- Run SBIG SDK calls through a background thread instead of the event loop
- Raise InvalidArgumentError for unknown filter name
- Raise AbortedError instead of bare InterruptedError on abort
- Rewrite README for uv-based install, config docs, and GUI
- Use pyobs-core[gui] extra instead of separate Qt packages
- updated ruff workflow to disable auto-sync
- added ruff workflow
- publish sdist only
- removed DEVELOPMENT.md after completing pyobs 2.0 migration steps
- refactored sbig module to modernize interfaces and align with pyobs 2.0 standards
- removed unused encoding comment in Sphinx config
- refactored type hints and imports across sbig module to align with modern Python standards
- migrated from flake8 to ruff, removed flake8 config and dependencies
- added DEVELOPMENT.md outlining pyobs 2.0 migration steps and module updates
- changed underscore parameters for vfs, comm, etc
- renamed Object parameters (comm, observer, ...) to start with an underscore

## [1.3.0] - 2026-04-29

- pypi
- cleaned up
- moved to uv

## [1.2.2] - 2025-07-09

- back to poetry for building cython...

## [1.2.1] - 2025-07-09

- back to poetry for building cython...
- new lock file

## [1.2.0] - 2025-07-07

- migrated to uv
- datetime.utcnow() to datetime.utc(timezone.utc)

## [1.1.0] - 2024-03-21

- Maintenance release (dependency and metadata updates only).

## [1.0.7] - 2024-03-21

- fixed docs

## [1.0.6] - 2023-11-10

- added list_binnings

## [1.0.5] - 2023-07-31

- updated dependencies

## [1.0.4] - 2023-07-04

- removed lock

## [1.0.3] - 2023-07-03

- accept Python 3.11

## [1.0.2] - 2023-07-03

- increased lock wait time

## [1.0.1] - 2023-03-22

- implemented ICooling

## [1.0.0] - 2022-09-13

- added license

## [0.20.0] - 2022-07-20

- upgrade to pyobs-core >0.20
- added IAbortable

## [0.18.0] - 2022-05-14

- cast to str
- moved import of sbigudrv into methods for rtd
- added # type: ignore
- moved import of sbigudrv into __init__ for rtd
- fixed rtd
- added intersphinx connection to core
- basic docs

## [0.16.0] - 2022-01-14

- alpha version
- set InterruptedError instead of AbortedError
- replaced AbortedError with builtin InterruptedError
- new exceptions for cameras
- added black and pre-commit to dev dependencies
- added .pre-commit-config.yaml
- running black
- added black config

## [0.15.0] - 2021-12-29

- changed used Python version to 3.9
- release gil
- don't release gil in readout
- added locks again
- simplified driver
- fixed some bugs
- simplified structure
- with asyncio we don't need locks so removed them
- implement abstract methods
- Pushed requirements to Python>=3.9 and astropy>=5.0, closes #55
- added abstract methods
- fixed bugs
- asyncio
- github action
- copy_extensions_to_source
- cython/poetry test
- use poetry
- v0.14
- kwargs
- added config
- Added type hints
- fixed cooling status
- fixed import
- sbig driver tests
- create driver from dict
- v0.13
- documentation
- added __module__
- made add_thread_func and add_child_func public
- updated docstrings
- moved IMotion.Status to utils.enums.MotionStatus
- moved ExposureStatus to utils.enums
- import base
- changed to full imports instead of relative ones
- fixed type hints
- don't run driver through add_child_object
- returning full frame for 1x1 binning
- fixed bug
- fixed filter wheel
- added import
- first version of a new sbig driver that is separated from the module to be used as shared module
- added missing import
- don't build wheel
- install cython and numpy in github action
- v0.12
- working on type hints
- exposure_time in seconds instead of ms
- only set motion status after Module is opened
- GitHub workflow for publishing to PyPI
- new derived SBIG class that correctly handles GAIN for SBIG6303e
- v0.10
- filter wheel and restricted access to sbig object
- cleaning up
- better dealing with blocked device
- fun with initialization
- react on failed lock
- lock for driver access
- added with nogil
- testing nogil for readout
- CSbigCam seems to want all binned pixels
- CSbigCam seems to have all binned pixels
- re-formatted code to test binning
- check for current filter before changing
- set filter wheel status on startup
- added IFilters to motion status
- v0.9
- removed pyobs-core from requirements
- init mixin
- created new class for cameras with filter wheel

## [0.8.1] - 2019-11-18

- added pyobs-core to requirements
- moved all requirements to setup.py
- - distutils -> setuptools - v0.8
- fixed change of interface
- update interfaces and methods
- changing exposure status on abort
- fixed bug
- aborted as int
- added cython bool support...
- moved aborted
- moved self.aborted into __init__
- image orientation
- aborting exposure
- transpose?
- flip image
- skip transposing
- add IFilters base class dynamically
- data type
- transpose manually
- transpose image
- add filter to fits header
- get full frame for 1x1 binning on open and store it
- changed version number to 0.2
- set window to unbinned size
- added missing import
- locking filter wheel motion
- removed debug output
- added UNKNOWN to list of displayed filters
- removed UNKNOWN from list of displayed filters
- fixed typo
- parsing enum
- enum error
- waiting for filter to set
- parsing enums
- values of enums
- sending value of enum
- new ITemperatures interface
- fixed bug with binning
- binning/window again
- fixed buf
- new binning/window interfaces
- removed unused import
- add include paths
- pytel -> pyobs
- removed IStatus interface
- new get_cooling_status()
- changed to match new interfaces
- added new ExposureStatusChanged event
- renamed pytel to pyobs
- using Exceptions for error propagation, and added docstrings
- added filter wheel support
- removed import
- removed pytel from requirements
- added README
- hopefully fixed copying of data
- waiting for exposure in python, not in C (due to GIL...)
- first commit
