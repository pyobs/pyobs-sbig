from setuptools import Extension, Distribution
import numpy
from Cython.Build import cythonize
from Cython.Distutils.build_ext import new_build_ext as cython_build_ext


def build():
    extensions = [
        Extension(
            'pyobs_sbig.sbigudrv',
            ['pyobs_sbig/sbigudrv.pyx', 'src/csbigcam.cpp', 'src/csbigimg.cpp'],
            libraries=['sbigudrv', 'cfitsio'],
            include_dirs=[numpy.get_include(), '/usr/include/cfitsio'],
            extra_compile_args=['-fPIC']
        )
    ]
    ext_modules = cythonize(
        extensions,
        compiler_directives={
            "binding": True,
            "language_level": "3"
        },
    )

    distribution = Distribution({
        "name": "extended",
        "ext_modules": ext_modules,
        "cmdclass": {
            "build_ext": cython_build_ext,
        },
    })
    #distribution.package_dir = "extended"

    distribution.run_command("build_ext")
    build_ext_cmd = distribution.get_command_obj("build_ext")
    build_ext_cmd.copy_extensions_to_source()


if __name__ == "__main__":
    build()
