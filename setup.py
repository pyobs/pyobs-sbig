from distutils.core import setup, Extension
import os
from Cython.Build import cythonize

extensions = [
    Extension(
        'pytel_sbig.sbigudrv',
        ['pytel_sbig/sbigudrv.pyx', 'src/csbigcam.cpp', 'src/csbigimg.cpp'],
        libraries=['sbigudrv', 'cfitsio'],
        extra_compile_args=['-fPIC']
    )
]

# setup
setup(name='pytel_sbig',
      version='0.1',
      description='pytel component for SBIG cameras',
      packages=['pytel_sbig'],
      ext_modules=cythonize(extensions),
      requires=['pytel', 'astropy', 'numpy'])
