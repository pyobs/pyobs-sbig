SBIG module for *pytel*
=======================

Install SBIG driver
-------------------
Download the SBIG Universal Driver package from ftp://ftp.sbig.com/pub/devsw/LinuxDevKit.tar.gz and follow
the installation instructions in the README.txt.

**Note:** The files in the *src/* directory are part of this archive, and the *CSBIGCam* class has been modified to include a 
*Readout()* method.


Install *pyobs-sbig*
--------------------
Clone the repository:

    git clone https://github.com/pyobs/pyobs-sbig.git


Install dependencies:

    cd pytel-sbig
    pip3 install -r requirements
        
And install it:

    python3 setup.py install


Configuration
-------------
The *SbigCamera* class is derived from *BaseCamera* (see *pyobs* documentation) and adds a single new parameter:

    setpoint:
        The initial setpoint in degrees Celsius for the cooling of the camera.

The class works fine with its default parameters, so a basic module configuration would look like this:

    module:
      class: pyobs_sbig.SbigCamera
      name: SBIG camera

Dependencies
------------
* **pyobs** for the core funcionality. It is not included in the *requirements.txt*, so needs to be installed 
  separately.
* [Cython](https://cython.org/) for wrapping the SBIG Universal Driver.
* [Astropy](http://www.astropy.org/) for FITS file handling.
* [NumPy](http://www.numpy.org/) for array handling.