from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy

extensions = [
    Extension(
        'pyobs_sbig.sbigudrv',
        ['pyobs_sbig/sbigudrv.pyx', 'src/csbigcam.cpp', 'src/csbigimg.cpp'],
        libraries=['sbigudrv', 'cfitsio'],
        include_dirs=[numpy.get_include(), '/usr/include/cfitsio'],
        extra_compile_args=['-fPIC']
    )
]

# setup
setup(
    name='pyobs-sbig',
    version='0.10',
    description='pyobs module for SBIG cameras',
    packages=['pyobs_sbig'],
    ext_modules=cythonize(extensions),
    install_requires=[
        'cython',
        'numpy',
        'astropy'
    ]
)
