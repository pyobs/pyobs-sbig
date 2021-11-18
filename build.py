import os

# See if Cython is installed
try:
    from Cython.Build import cythonize
# Do nothing if Cython is not available
except ImportError:
    # Got to provide this function. Otherwise, poetry will fail
    def build(setup_kwargs):
        pass
# Cython is installed. Compile
else:
    from setuptools import Extension
    from setuptools.dist import Distribution
    from distutils.command.build_ext import build_ext
    import numpy

    # This function will be executed in setup.py:
    def build(setup_kwargs):
        # define extension
        extension = Extension(
            'pyobs_sbig.sbigudrv',
            ['pyobs_sbig/sbigudrv.pyx', 'src/csbigcam.cpp', 'src/csbigimg.cpp'],
            libraries=['sbigudrv', 'cfitsio'],
            include_dirs=[numpy.get_include(), '/usr/include/cfitsio'],
            extra_compile_args=['-fPIC']
        )

        # gcc arguments hack: enable optimizations
        os.environ['CFLAGS'] = '-O3'

        # Build
        setup_kwargs.update({
            'ext_modules': cythonize([extension]),
            'cmdclass': {'build_ext': build_ext}
        })
