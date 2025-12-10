cmake_minimum_required(VERSION 3.22)
project(geoslice VERSION 0.0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include(FetchContent)

option(BUILD_PYTHON "Build Python bindings" ON)
option(BUILD_TESTS "Build tests" ON)

# Core library
add_library(geoslice_core STATIC
    src/mmap_reader.cpp
    src/geo_transform.cpp
    src/window_cache.cpp
)
target_include_directories(geoslice_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_options(geoslice_core PRIVATE -O3 -march=native -ffast-math)

# Python bindings
if(BUILD_PYTHON)
    find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
    
    # Fetch pybind11
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG v2.11.1
    )
    FetchContent_MakeAvailable(pybind11)
    
    pybind11_add_module(_geoslice_cpp src/bindings.cpp)
    target_link_libraries(_geoslice_cpp PRIVATE geoslice_core)
endif()

# Tests
if(BUILD_TESTS)
    enable_testing()
    
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG v1.14.0
    )
    FetchContent_MakeAvailable(googletest)
    
    add_executable(geoslice_tests
        tests/test_mmap_reader.cpp
        tests/test_geo_transform.cpp
        tests/test_window_cache.cpp
    )
    target_link_libraries(geoslice_tests PRIVATE geoslice_core GTest::gtest_main)
    
    include(GoogleTest)
    gtest_discover_tests(geoslice_tests)
endif()

# Install
install(TARGETS geoslice_core EXPORT geoslice-targets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
install(DIRECTORY include/geoslice DESTINATION include)