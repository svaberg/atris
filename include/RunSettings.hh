#ifndef RunSettings_hh
#define RunSettings_hh

#include "OutputMode.hh"

#include "globals.hh"

#include <array>
#include <vector>

namespace atris {

struct RunSettings
{
  G4String outputStem;
  G4String outputFileFormat = "csv";
  G4String simulationInputPrefix;
  G4String physicsListName = "FTFP_BERT_HP";
  G4int outputMode = kInvalidOutputMode;
  G4int detectorCount = 0;
  std::array<G4long, 2> explicitSeeds = {0, 0};
  std::vector<G4double> energyBins;
  std::vector<G4double> detectorBins;
  std::array<G4int, 2> directionHistogramBins = {120, 60};
  std::array<G4int, 2> positionHistogramBins = {120, 60};
};

}  // namespace atris

#endif
