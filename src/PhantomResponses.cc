#include "PhantomResponses.hh"

#include "PhantomResponseSchema.hh"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>

namespace
{

constexpr G4int kMissingParticleIndex = -1;

struct ResponseTable
{
    std::vector<G4int> pdgs;
    std::vector<G4double> values;
};

G4bool ReadResponseTable(const G4String& fileName, ResponseTable& table)
{
  std::ifstream input(fileName);
  if (!input.is_open())
  {
    G4cerr << "### AtRIS: unable to open phantom file " << fileName << G4endl;
    return false;
  }

  G4String line;
  std::getline(input, line);
  std::stringstream header(line);
  G4int pdg;
  while (header >> pdg)
    table.pdgs.push_back(pdg);
  if (table.pdgs.empty())
  {
    G4cerr << "### AtRIS: phantom file has an empty PDG header: " << fileName << G4endl;
    return false;
  }

  G4double value;
  while (std::getline(input, line))
  {
    std::stringstream values(line);
    while (values >> value)
      table.values.push_back(value);
  }
  return true;
}

G4bool ValidateValueCount(const G4String& fileName, const ResponseTable& table)
{
  const std::size_t expectedValueCount = atris::kPhantomResponseEnergyBins * table.pdgs.size();
  G4debug << "### AtRIS: found " << table.values.size() << " out of expected " << expectedValueCount
          << G4endl;
  if (table.values.size() == expectedValueCount)
  {
    return true;
  }
  G4cerr << "### AtRIS: response value count mismatch in " << fileName << G4endl;
  return false;
}

}  // namespace

namespace atris
{

void PhantomResponses::ConfigureParticleLookup(const std::vector<G4int>& particleCodes,
                                               const G4String& fileName)
{
  fParticleCodes = particleCodes;
  fParticleHeaderFile = fileName;
  fLightParticleIndices.assign(kLightParticleLookupSize, kMissingParticleIndex);
  fIonIndices.clear();
  for (std::size_t particleIndex = 0; particleIndex < particleCodes.size(); ++particleIndex)
  {
    const G4int pdg = particleCodes[particleIndex];
    // Common particles fit the dense signed-PDG lookup. Ion PDG codes
    // are sparse and therefore use a separate map.
    if (std::abs(pdg) < kLightParticlePDGLimit)
    {
      const G4int lookupIndex = pdg + kLightParticlePDGOffset;
      if constexpr (ATRIS_DEBUG_LOGGING)
      {
        G4debug << particleIndex << " adding sensitivity for light particle with PDG= " << pdg
                << " at index " << lookupIndex << G4endl;
      }
      fLightParticleIndices[lookupIndex] = static_cast<G4int>(particleIndex);
    }
    else
    {
      if constexpr (ATRIS_DEBUG_LOGGING)
      {
        G4debug << "Added sensitivity for heavy particle with PDG= " << pdg
                << " under the index j=" << particleIndex << G4endl;
      }
      fIonIndices[pdg] = static_cast<G4int>(particleIndex);
    }
  }
  G4debug << "total" << particleCodes.size() << G4endl;
  G4debug << " ### AtRIS: nricrubins is:" << kPhantomResponseEnergyBins
          << " and nrpdgs is : " << particleCodes.size()
          << ". We are expecting: " << kPhantomResponseEnergyBins * particleCodes.size()
          << " data points in each phantom file." << G4endl;
}

G4bool PhantomResponses::Add(PhantomResponse response)
{
  const auto existing =
    std::find_if(fResponses.begin(), fResponses.end(), [&](const PhantomResponse& storedResponse) {
      return storedResponse.phantomStem == response.phantomStem
             && storedResponse.name == response.name;
    });
  auto table = fTables.find(response.fileName);
  if (table == fTables.end())
  {
    G4cout << "### AtRIS: loading response '" << response.name << "' for phantom '"
           << response.phantomStem << "' from " << response.fileName << G4endl << std::flush;
    ResponseTable loaded;
    if (!ReadResponseTable(response.fileName, loaded)) return false;
    if (fParticleCodes.empty())
    {
      ConfigureParticleLookup(loaded.pdgs, response.fileName);
    }
    else if (loaded.pdgs != fParticleCodes)
    {
      G4cerr << "### AtRIS: PDG header mismatch: " << response.fileName << " does not match "
             << fParticleHeaderFile << G4endl;
      return false;
    }
    if (!ValidateValueCount(response.fileName, loaded))
    {
      return false;
    }
    table = fTables.emplace(response.fileName, std::move(loaded.values)).first;
  }

  fPhantomStems.insert(response.phantomStem);
  response.values = &table->second;
  if (existing == fResponses.end())
  {
    fResponses.push_back(response);
  }
  else
  {
    *existing = response;
  }
  return true;
}

G4int PhantomResponses::FindParticleIndex(const G4int pdg) const
{
  if (fResponses.empty()) return kMissingParticleIndex;
  if (std::abs(pdg) < kLightParticlePDGLimit)
  {
    return fLightParticleIndices[pdg + kLightParticlePDGOffset];
  }
  if (pdg < kFirstSupportedIonPDG) return kMissingParticleIndex;
  const auto found = fIonIndices.find(pdg);
  return found == fIonIndices.end() ? kMissingParticleIndex : found->second;
}

}  // namespace atris
