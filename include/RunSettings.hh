#ifndef RunSettings_hh
#define RunSettings_hh

#include "OutputMode.hh"

#include "globals.hh"

#include <array>
#include <vector>

namespace atris {

/**
 * Resolved settings shared by the Geant4 objects participating in one run.
 *
 * RunConfiguration begins with the defaults declared here, applies commands
 * from the selected macro, and derives geometry-dependent values during
 * `/atris/initialize`. After initialization, detector and action objects borrow
 * this structure as read-only run state.
 */
struct RunSettings
{
  /// Filename stem passed to the Geant4 analysis manager.
  G4String outputStem;

  /// Geant4 analysis backend name, such as `csv` or `root`.
  G4String outputFileFormat = "csv";

  /// Geometry filename without its extension, recorded in output metadata.
  G4String simulationInputPrefix;

  /// Name passed to Geant4's reference physics-list factory.
  G4String physicsListName = "FTFP_BERT_HP";

  /// Amount of event-level detail written by the simulation.
  OutputMode outputMode = OutputMode::kInvalid;

  /// Number of sensitive volumes found in the GDML auxiliary metadata.
  G4int detectorCount = 0;

  /// Explicit CLHEP seed pair; two zeros request Geant4's runtime defaults.
  std::array<G4long, 2> explicitSeeds = {0, 0};

  /// Primary-energy histogram edges read from the configured bins file.
  std::vector<G4double> energyBins;

  /// Histogram edges centered on the integer sensitive-detector IDs.
  std::vector<G4double> detectorBins;

  /// Numbers of azimuth and polar-cosine bins in the source-direction plot.
  std::array<G4int, 2> directionHistogramBins = {120, 60};

  /// Numbers of azimuth and polar-cosine bins in the source-position plot.
  std::array<G4int, 2> positionHistogramBins = {120, 60};
};

}  // namespace atris

#endif
