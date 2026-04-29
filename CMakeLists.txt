cmake_minimum_required(VERSION 3.21)
project(pyobs_sbig LANGUAGES CXX)

# --- Ensure we use the build environment Python ---
set(Python3_FIND_VIRTUALENV ONLY)
set(Python3_FIND_STRATEGY LOCATION)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# --- Paths ---
set(PYX_FILE "${CMAKE_CURRENT_SOURCE_DIR}/src/pyobs_sbig/sbigudrv.pyx")
set(CXX_FILE "${CMAKE_CURRENT_BINARY_DIR}/sbigudrv.cpp")
set(CSBIGCAM_FILE "${CMAKE_CURRENT_SOURCE_DIR}/src/sbigudrv/csbigcam.cpp")
set(CSBIGIMG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/src/sbigudrv/csbigimg.cpp")

# --- Run Cython manually ---
add_custom_command(
  OUTPUT ${CXX_FILE}
  COMMAND "${Python3_EXECUTABLE}" -m cython
          ${PYX_FILE}
          --output-file ${CXX_FILE}
          --cplus
  DEPENDS ${PYX_FILE}
  COMMENT "Running Cython on sbigudrv.pyx"
)

# --- Get NumPy include dir ---
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c
          "import numpy; print(numpy.get_include())"
  OUTPUT_VARIABLE NUMPY_INCLUDE_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

# --- Build extension module ---
add_library(sbigudrv MODULE
  ${CXX_FILE}
  ${CSBIGCAM_FILE}
  ${CSBIGIMG_FILE}
)
set_source_files_properties(${CXX_FILE} PROPERTIES LANGUAGE CXX)
target_include_directories(sbigudrv PRIVATE
  ${Python3_INCLUDE_DIRS}
  ${NUMPY_INCLUDE_DIR}
  ${CMAKE_CURRENT_SOURCE_DIR}/src/sbigudrv/
)

# --- Correct Python module naming (VERY IMPORTANT) ---
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c
          "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))"
  OUTPUT_VARIABLE PY_EXT_SUFFIX
  OUTPUT_STRIP_TRAILING_WHITESPACE
)
set_target_properties(sbigudrv PROPERTIES
  PREFIX ""
  OUTPUT_NAME "sbigudrv"
  SUFFIX "${PY_EXT_SUFFIX}"
  POSITION_INDEPENDENT_CODE ON
)
message(STATUS "ext: ${PY_EXT_SUFFIX}")

# --- sbigudrv ---
target_include_directories(sbigudrv PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/lib/usr/local/include/
)

# --- Link ---
find_library(CFITSIO_LIB cfitsio REQUIRED)
find_path(CFITSIO_INCLUDE_DIR fitsio.h REQUIRED)
target_include_directories(sbigudrv PRIVATE ${CFITSIO_INCLUDE_DIR})
target_link_libraries(sbigudrv PRIVATE ${CFITSIO_LIB})

find_library(SBIGUDRV_LIB sbigudrv REQUIRED PATHS /usr/local/lib)
target_link_libraries(sbigudrv PRIVATE ${SBIGUDRV_LIB})

# --- Install into package ---
install(TARGETS sbigudrv
  LIBRARY DESTINATION ${SKBUILD_PROJECT_NAME}
)
