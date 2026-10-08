cmake_minimum_required(VERSION 3.22)

project(AtRIS LANGUAGES CXX)

find_package(Geant4 REQUIRED COMPONENTS gdml multithreaded)

set(ATRIS_SOURCE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
set(ATRIS_VERSION "unknown")
if(EXISTS "${ATRIS_SOURCE_ROOT}/.git")
  execute_process(
    COMMAND git describe --tags --always --dirty --match "v[0-9]*"
    WORKING_DIRECTORY "${ATRIS_SOURCE_ROOT}"
    OUTPUT_VARIABLE ATRIS_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
elseif(EXISTS "${ATRIS_SOURCE_ROOT}/.git_archival.txt")
  file(STRINGS "${ATRIS_SOURCE_ROOT}/.git_archival.txt" ATRIS_ARCHIVE_VERSION
       REGEX "^describe-name: ")
  string(REPLACE "describe-name: " "" ATRIS_VERSION "${ATRIS_ARCHIVE_VERSION}")
endif()
if(NOT ATRIS_VERSION OR ATRIS_VERSION MATCHES "\\$Format")
  set(ATRIS_VERSION "unknown")
endif()
message(STATUS "AtRIS version: ${ATRIS_VERSION}")

set(ATRIS_HEADERS
  include/AnalysisOutput.hh
  include/DetectorConstruction.hh
  include/NtupleSchema.hh
  include/OutputMode.hh
  include/PhantomResponses.hh
  include/PhantomResponseSchema.hh
  include/PrimaryGeneratorAction.hh
  include/RunAction.hh
  include/RunConfiguration.hh
  include/RunSettings.hh
  include/SensitiveDetector.hh
  include/UserActionInitialization.hh
)

set(ATRIS_SOURCES
  src/main.cc
  src/AnalysisOutput.cc
  src/DetectorConstruction.cc
  src/PhantomResponses.cc
  src/PrimaryGeneratorAction.cc
  src/RunAction.cc
  src/RunConfiguration.cc
  src/SensitiveDetector.cc
  src/UserActionInitialization.cc
)

add_executable(AtRIS)
target_sources(AtRIS PRIVATE ${ATRIS_SOURCES} ${ATRIS_HEADERS})
target_include_directories(AtRIS PRIVATE ${PROJECT_SOURCE_DIR}/include)
target_link_libraries(AtRIS PRIVATE ${Geant4_LIBRARIES})
# Compile detailed G4debug diagnostics only in standard Debug builds.
target_compile_definitions(AtRIS PRIVATE
  ATRIS_VERSION="${ATRIS_VERSION}"
  ATRIS_DEBUG_LOGGING=$<CONFIG:Debug>
)
target_compile_features(AtRIS PRIVATE cxx_std_17)
set_property(TARGET AtRIS PROPERTY CXX_EXTENSIONS OFF)
target_compile_options(AtRIS PRIVATE
  $<$<CXX_COMPILER_ID:AppleClang,Clang,GNU>:-Wall;-Wextra;-Wpedantic>
)

#----------------------------------------------------------------------------
# For internal Geant4 use - but has no effect if you build this
# example standalone
#
#add_custom_target(G4ET DEPENDS G4ET)

#----------------------------------------------------------------------------
# Install the executable to 'bin' directory under CMAKE_INSTALL_PREFIX
#
#install(TARGETS G4ET DESTINATION bin)

#configure_file(files/example.gdml ./ COPYONLY)
#configure_file(files/example.bins ./ COPYONLY)
#configure_file(files/example.py ./ COPYONLY)
#configure_file(files/example.mac ./ COPYONLY)
#configure_file(phantoms/icru_response.txt ./ COPYONLY)
#configure_file(phantoms/icru_counting.txt ./ COPYONLY)
#configure_file(phantoms/ramona_fifteen_0.060MeV_detA_response.txt ./ COPYONLY)
#configure_file(phantoms/ramona_fifteen_0.060MeV_detA_counting.txt ./ COPYONLY)
