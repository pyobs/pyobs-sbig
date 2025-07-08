cmake_minimum_required(VERSION 3.10)
project(sbigudrv)

find_package (Python3 3.11 REQUIRED COMPONENTS Interpreter Development.Module REQUIRED)
#find_package(Python3 3.11 COMPONENTS Interpreter NumPy REQUIRED)
include_directories(${PYTHON_INCLUDE_DIRS})
#target_link_libraries(c__14 ${PYTHON_LIBRARIES} Python3::NumPy)

#find_package(
#  Python
#  COMPONENTS Interpreter Development.Module
#  REQUIRED)
#find_package(Numpy REQUIRED)
include(UseCython)

cython_transpile(pyobs_sbig/sbigudrv.pyx LANGUAGE CXX OUTPUT_VARIABLE sbigudrv)

python_add_library(simple MODULE "${sbigudrv}" src/csbigcam.cpp src/csbigimg.cpp WITH_SOABI ${PYTHON_LIBRARIES} Python3::Python)
install(TARGETS simple DESTINATION .)