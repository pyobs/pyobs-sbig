pyobs-sbig
##########

This is a `pyobs <https://www.pyobs.org>`_ (`documentation <https://docs.pyobs.org>`_) module for SBIG cameras.


Example configuration
*********************

This is an example configuration for a SBIG-6303E camera::

    class: pyobs_sbig.Sbig6303eCamera

    # cooling setpoint
    setpoint: -10

    # file naming
    filenames: /cache/pyobs-{DAY-OBS|date:}-{FRAMENUM|string:04d}-{IMAGETYP|type}00.fits

    # additional fits headers
    fits_headers:
      'INSTRUME': ['sbig', 'Name of instrument']
      'DET-PIXL': [0.009, 'Size of detector pixels (square) [mm]']
      'DET-NAME': ['KAF-6303E', 'Name of detector']
      'DET-RON': [13.5, 'Detector readout noise [e-]']
      'DET-SATU': [100000, 'Detector saturation limit [e-]']
      'DET-DARK': [0.3, 'Detector dark current [e-/s]']

    # opto-mechanical centre
    centre: [1536.0, 1024.0]

    # rotation (east of north)
    rotation: -1.76
    flip: True

    # filter wheel
    filter_wheel: AUTO
    filter_names: [Red, Green, Blue, Clear, Halpha]

    # location
    timezone: utc
    location:
      longitude: 9.944333
      latitude: 51.560583
      elevation: 201.

    # communication
    comm:
      jid: test@example.com
      password: ***

    # virtual file system
    vfs:
      class: pyobs.vfs.VirtualFileSystem
      roots:
        cache:
          class: pyobs.vfs.HttpFile
          upload: http://localhost:37075/


Available classes
*****************

The base class for all SBIG cameras is :ref:`SbigCamera`, which can be used for all camera types without an integrated
filter wheel. For those that do have one, you must use :ref:`SbigFilterCamera`. There is a special implementation
for SBIG-6303E cameras in :ref:`Sbig6303eCamera`.

SbigCamera
==========
.. autoclass:: pyobs_sbig.SbigCamera
   :members:
   :show-inheritance:

SbigFilterCamera
================
.. autoclass:: pyobs_sbig.SbigFilterCamera
   :members:
   :show-inheritance:

Sbig6303eCamera
===============
.. autoclass:: pyobs_sbig.Sbig6303eCamera
   :members:
   :show-inheritance: