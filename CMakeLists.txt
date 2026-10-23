cmake_minimum_required(VERSION 3.16)
project(shape_based_matching VERSION 0.1.0 LANGUAGES CXX)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
option(SBM_ENABLE_SIMD "Use the bundled MIPP SIMD implementation" ON)
set(_sbm_openmp_default ON)
if(MSVC)
    # The legacy MSVC OpenMP runtime lacks the required user-defined reduction.
    set(_sbm_openmp_default OFF)
endif()
option(SBM_ENABLE_OPENMP "Enable parallel search when OpenMP is available" ${_sbm_openmp_default})
option(SBM_BUILD_EXAMPLE "Build the command-line matching example" ON)

find_package(OpenCV 4 REQUIRED COMPONENTS core imgproc highgui imgcodecs)
if(SBM_ENABLE_OPENMP)
    if(MSVC)
        message(FATAL_ERROR "This build does not enable MSVC OpenMP; set SBM_ENABLE_OPENMP=OFF.")
    endif()
    find_package(OpenMP COMPONENTS CXX)
endif()

# A static library avoids requiring platform-specific DLL export annotations.
add_library(shape_based_matching STATIC line2Dup.cpp)
add_library(shape_based_matching::shape_based_matching ALIAS shape_based_matching)
target_compile_features(shape_based_matching PUBLIC cxx_std_14)
set_target_properties(shape_based_matching PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(shape_based_matching PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/MIPP>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/shape_based_matching>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/shape_based_matching/MIPP>)
target_link_libraries(shape_based_matching PUBLIC ${OpenCV_LIBS})

# MIPP appears in the public header: consumers need the same SIMD settings.
# Avoid -march=native so the builder's CPU does not silently set requirements.
if(NOT SBM_ENABLE_SIMD)
    target_compile_definitions(shape_based_matching PUBLIC MIPP_NO_INTRINSICS)
elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang" AND
       CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64|i.86)$")
    target_compile_options(shape_based_matching PUBLIC -mssse3 -msse4.1)
endif()

set(SBM_WITH_OPENMP OFF)
if(SBM_ENABLE_OPENMP AND OpenMP_CXX_FOUND)
    target_link_libraries(shape_based_matching PUBLIC OpenMP::OpenMP_CXX)
    set(SBM_WITH_OPENMP ON)
endif()
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(shape_based_matching PRIVATE -Wall -Wextra -Wno-sign-compare -Wno-unused-function)
endif()
if(SBM_BUILD_EXAMPLE)
    add_executable(match_example examples/match.cpp)
    target_link_libraries(match_example PRIVATE shape_based_matching::shape_based_matching)
endif()

install(TARGETS shape_based_matching EXPORT shape_based_matchingTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES line2Dup.h line2Dup_local.hpp line2Dup_matches.hpp
    line2Dup_response.hpp line2Dup_search.hpp line2Dup_spread.hpp
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/shape_based_matching)
install(DIRECTORY MIPP/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/shape_based_matching/MIPP
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hxx")
install(FILES LICENSE THIRD_PARTY_NOTICES.md
    DESTINATION ${CMAKE_INSTALL_DATADIR}/shape_based_matching)
configure_package_config_file(cmake/shape_based_matchingConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/shape_based_matchingConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/shape_based_matching)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/shape_based_matchingConfigVersion.cmake
    VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(EXPORT shape_based_matchingTargets NAMESPACE shape_based_matching::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/shape_based_matching)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/shape_based_matchingConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/shape_based_matchingConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/shape_based_matching)
