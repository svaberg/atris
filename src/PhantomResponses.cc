#include "PhantomResponses.hh"

#include "PhantomResponseSchema.hh"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>

namespace {

struct ResponseTable
{
  std::vector<G4int> pdgs;
  std::vector<G4double> values;
};

G4bool ReadResponseTable(const G4String& fileName, ResponseTable& table)
{
  std::ifstream input(fileName);
  if (!input.is_open()) {
    G4cerr << "### AtRIS: unable to open phantom file " << fileName << G4endl;
    return false;
  }

  G4String line;
  std::getline(input, line);
  std::stringstream header(line);
  G4int pdg;
  while (header >> pdg) table.pdgs.push_back(pdg);
  if (table.pdgs.empty()) {
    G4cerr << "### AtRIS: phantom file has an empty PDG header: "
           << fileName << G4endl;
    return false;
  }

  G4double value;
  while (std::getline(input, line)) {
    std::stringstream values(line);
    while (values >> value) table.values.push_back(value);
  }
  return true;
}

G4bool ValidateValueCount(
  const G4String& fileName,
  const ResponseTable& table,
  const G4int expectedValueCount
)
{
  G4cout << "### AtRIS: found " << table.values.size()
         << " out of expected " << expectedValueCount << G4endl;
  if (table.values.size() == static_cast<std::size_t>(expectedValueCount)) {
    return true;
  }
  G4cerr << "### AtRIS: response value count mismatch in "
         << fileName << G4endl;
  return false;
}

}  // namespace

namespace atris {

void PhantomResponses::ConfigureParticleLookup(
  const std::vector<G4int>& particleCodes,
  const G4String& fileName
)
{
  fParticleCodes = particleCodes;
  fParticleHeaderFile = fileName;
  fExpectedValueCount = static_cast<G4int>(
    kPhantomResponseEnergyBins * particleCodes.size()
  );
  fLightParticleIndices.assign(kLightParticleLookupSize, 0);
  fIonIndices.clear();
  for (std::size_t particleIndex = 0;
       particleIndex < particleCodes.size();
       ++particleIndex) {
    const G4int pdg = particleCodes[particleIndex];
    // Common particles fit the dense signed-PDG lookup. Ion PDG codes
    // are sparse and therefore use a separate map.
    if (std::abs(pdg) < kLightParticlePDGLimit) {
      const G4int lookupIndex = pdg + kLightParticlePDGOffset;
      G4cout << particleIndex
             << " adding sensitivity for light particle with PDG= "
             << pdg << " at index " << lookupIndex << G4endl;
      fLightParticleIndices[lookupIndex] = static_cast<G4int>(particleIndex);
    } else {
      G4cout << "Added sensitivity for heavy particle with PDG= "
             << pdg << " under the index j=" << particleIndex << G4endl;
      fIonIndices[pdg] = static_cast<G4int>(particleIndex);
    }
  }
  G4cout << "total" << particleCodes.size() << G4endl;
  G4cout << " ### AtRIS: nricrubins is:" << kPhantomResponseEnergyBins
         << " and nrpdgs is : " << particleCodes.size()
         << ". We are expecting: " << fExpectedValueCount
         << " data points in each phantom file." << G4endl;
}

G4bool PhantomResponses::Add(
  const G4String& phantomStem,
  const G4String& responseName,
  const G4String& fileName,
  const G4bool scaleByCrossingEnergy,
  const G4bool scaleByRadiationWeight,
  const G4bool scaleByInversePhantomMass
)
{
  const auto duplicate = std::find_if(
    fResponses.begin(),
    fResponses.end(),
    [&](const PhantomResponse& response) {
      return response.phantomStem == phantomStem
        && response.name == responseName;
    }
  );
  if (duplicate != fResponses.end()) {
    G4cerr << "### AtRIS: response '" << responseName
           << "' is configured more than once for phantom '"
           << phantomStem << "'" << G4endl;
    return false;
  }

  auto table = fTables.find(fileName);
  if (table == fTables.end()) {
    G4cout << "### AtRIS: loading response '" << responseName
           << "' for phantom '" << phantomStem << "' from " << fileName
           << G4endl << std::flush;
    ResponseTable loaded;
    if (!ReadResponseTable(fileName, loaded)) return false;
    if (fParticleCodes.empty()) {
      ConfigureParticleLookup(loaded.pdgs, fileName);
    } else if (loaded.pdgs != fParticleCodes) {
      G4cerr << "### AtRIS: PDG header mismatch: " << fileName
             << " does not match " << fParticleHeaderFile << G4endl;
      return false;
    }
    if (!ValidateValueCount(fileName, loaded, fExpectedValueCount)) {
      return false;
    }
    table = fTables.emplace(
      fileName,
      std::move(loaded.values)
    ).first;
  }

  fPhantomStems.insert(phantomStem);
  fResponses.push_back({
    phantomStem,
    responseName,
    fileName,
    scaleByCrossingEnergy,
    scaleByRadiationWeight,
    scaleByInversePhantomMass,
    &table->second,
  });
  return true;
}

G4int PhantomResponses::FindParticleIndex(const G4int pdg) const
{
  if (fResponses.empty()) return -1;
  if (std::abs(pdg) < kLightParticlePDGLimit) {
    const G4int index = fLightParticleIndices[pdg + kLightParticlePDGOffset];
    return index != 0 || pdg == kPhotonPDG ? index : -1;
  }
  if (pdg < kFirstSupportedIonPDG) return -1;
  const auto found = fIonIndices.find(pdg);
  return found == fIonIndices.end() ? -1 : found->second;
}

}  // namespace atris
