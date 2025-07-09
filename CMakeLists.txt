cmake_minimum_required(VERSION 3.31)
project(sbigudrv LANGUAGES CXX)

find_package (Python3 COMPONENTS Interpreter Development.Module REQUIRED)
#find_package(Python3 3.11 COMPONENTS Interpreter NumPy REQUIRED)
#include_directories(${PYTHON_INCLUDE_DIRS})
#target_link_libraries(c__14 ${PYTHON_LIBRARIES} Python3::NumPy)

include_directories(/home/husser/code/pyobs/pyobs-sbig/.venv/lib/python3.11/site-packages/numpy/_core/include)

#find_package(
#  Python
#  COMPONENTS Interpreter Development.Module
#  REQUIRED)
#find_package(Numpy REQUIRED)
include(UseCython)

cython_transpile(pyobs_sbig/sbigudrv.pyx LANGUAGE CXX OUTPUT_VARIABLE sbigudrv)


add_library(sbigudrv MODULE ${sbigudrv})
target_link_libraries(sbigudrv ${PYTHON3_LIBRARIES} ${PYTHON3_INCLUDE_DIRS} ${NUMPY_LIBRARIES} ${NUMPY_INCLUDE_DIRS})
target_sources(sbigudrv PRIVATE src/csbigcam.cpp src/csbigimg.cpp)

#Python_add_library(simple MODULE "${sbigudrv}" src/csbigcam.cpp src/csbigimg.cpp WITH_SOABI ${PYTHON_LIBRARIES} Python3::Python)
#Python_add_library(simple MODULE "${sbigudrv}" src/csbigcam.cpp src/csbigimg.cpp WITH_SOABI)
#install(TARGETS simple DESTINATION .)
#cython_add_module(sbigudrv "${sbigudrv}" src/csbigcam.cpp src/csbigimg.cpp)