#include "PhantomResponses.hh"

#include "PhantomResponseSchema.hh"

#include <charconv>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <set>
#include <sstream>
#include <string>
#include <utility>

namespace {

struct ResponseTable
{
  std::vector<G4int> pdgs;
  std::vector<G4double> values;
};

G4bool ParsePhantomIndex(
  const std::string& fileName,
  const std::string& prefix,
  G4int& index
)
{
  const std::string suffix = ".txt";
  if (
    fileName.size() <= prefix.size() + suffix.size()
    || fileName.compare(0, prefix.size(), prefix) != 0
    || fileName.compare(fileName.size() - suffix.size(), suffix.size(), suffix) != 0
  ) return false;

  const char* const first = fileName.data() + prefix.size();
  const char* const last = fileName.data() + fileName.size() - suffix.size();
  const auto result = std::from_chars(first, last, index);
  if (result.ec != std::errc() || result.ptr != last || index < 0) return false;
  return fileName == prefix + std::to_string(index) + suffix;
}

G4bool DiscoverPhantomCount(G4int& count)
{
  const std::string radiationPrefix = "radiation_phantom";
  const std::string countingPrefix = "counting_phantom";
  std::set<G4int> radiationIndices;
  std::set<G4int> countingIndices;
  for (const auto& entry : std::filesystem::directory_iterator(".")) {
    const std::string fileName = entry.path().filename().string();
    G4int index;
    if (ParsePhantomIndex(fileName, radiationPrefix, index)) {
      radiationIndices.insert(index);
    }
    if (ParsePhantomIndex(fileName, countingPrefix, index)) {
      countingIndices.insert(index);
    }
  }

  for (const G4int index : radiationIndices) {
    if (countingIndices.count(index) == 0) {
      G4cerr << "### AtRIS: staged phantom " << index << " is missing "
             << countingPrefix << index << ".txt" << G4endl;
      return false;
    }
  }
  for (const G4int index : countingIndices) {
    if (radiationIndices.count(index) == 0) {
      G4cerr << "### AtRIS: staged phantom " << index << " is missing "
             << radiationPrefix << index << ".txt" << G4endl;
      return false;
    }
  }

  count = 0;
  for (const G4int index : radiationIndices) {
    if (index != count) {
      G4cerr << "### AtRIS: staged phantom IDs must be contiguous from 0; "
             << "expected " << count << " but found " << index << G4endl;
      return false;
    }
    ++count;
  }
  return true;
}

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

}  // namespace

namespace atris {

G4bool PhantomResponses::Load()
{
  G4int count;
  if (!DiscoverPhantomCount(count)) return false;

  G4cout << "### AtRIS: proceeding to load " << count << " phantom(s)."
         << G4endl << std::flush;
  std::vector<G4int> expectedPDGs;
  G4String expectedHeaderName;
  G4int expectedValueCount = 0;
  fLightParticleIndices.assign(kLightParticleLookupSize, 0);

  for (G4int phantomIndex = 0; phantomIndex < count; ++phantomIndex) {
    const G4String radiationName =
      "radiation_phantom" + std::to_string(phantomIndex) + ".txt";
    G4cout << "### AtRIS: loading radiation response matrix for phantom "
           << phantomIndex << " from " << radiationName
           << G4endl << std::flush;
    ResponseTable radiation;
    if (!ReadResponseTable(radiationName, radiation)) return false;

    if (phantomIndex == 0) {
      expectedPDGs = radiation.pdgs;
      expectedHeaderName = radiationName;
      for (std::size_t particleIndex = 0;
           particleIndex < expectedPDGs.size();
           ++particleIndex) {
        const G4int pdg = expectedPDGs[particleIndex];
        // Common particles fit the dense signed-PDG lookup. Ion PDG codes
        // are sparse and therefore use a separate map.
        if (std::abs(pdg) < kLightParticlePDGLimit) {
          const G4int lookupIndex = pdg + kLightParticlePDGOffset;
          G4cout << particleIndex
                 << " adding sensitivity for light particle with PDG= "
                 << pdg << " at index " << lookupIndex << G4endl;
          fLightParticleIndices[lookupIndex] =
            static_cast<G4int>(particleIndex);
        } else {
          G4cout << "Added sensitivity for heavy particle with PDG= "
                 << pdg << " under the index j=" << particleIndex << G4endl;
          fIonIndices[pdg] = static_cast<G4int>(particleIndex);
        }
      }
      G4cout << "total" << expectedPDGs.size() << G4endl;
      expectedValueCount = static_cast<G4int>(
        kPhantomResponseEnergyBins * expectedPDGs.size()
      );
      G4cout << " ### AtRIS: nricrubins is:"
             << kPhantomResponseEnergyBins << " and nrpdgs is : "
             << expectedPDGs.size() << ". We are expecting: "
             << expectedValueCount << " data points in the phantom file."
             << G4endl;
    } else if (radiation.pdgs != expectedPDGs) {
      G4cerr << "### AtRIS: PDG header mismatch: " << radiationName
             << " does not match " << expectedHeaderName << G4endl;
      return false;
    }

    G4cout << "### AtRIS: found " << radiation.values.size()
           << " out of expected " << expectedValueCount << G4endl;
    if (radiation.values.size() != static_cast<std::size_t>(expectedValueCount)) {
      G4cerr << "### AtRIS: response value count mismatch in "
             << radiationName << G4endl;
      return false;
    }
    fRadiation.push_back(std::move(radiation.values));

    const G4String countingName =
      "counting_phantom" + std::to_string(phantomIndex) + ".txt";
    G4cout << "### AtRIS: loading counting response matrix for phantom "
           << phantomIndex << " from " << countingName
           << G4endl << std::flush;
    ResponseTable counting;
    if (!ReadResponseTable(countingName, counting)) return false;
    if (counting.pdgs != expectedPDGs) {
      G4cerr << "### AtRIS: PDG header mismatch: " << countingName
             << " does not match " << expectedHeaderName << G4endl;
      return false;
    }
    G4cout << "### AtRIS: found " << counting.values.size()
           << " out of expected " << expectedValueCount << G4endl;
    if (counting.values.size() != static_cast<std::size_t>(expectedValueCount)) {
      G4cerr << "### AtRIS: response value count mismatch in "
             << countingName << G4endl;
      return false;
    }
    fCounting.push_back(std::move(counting.values));
  }
  return true;
}

G4int PhantomResponses::FindParticleIndex(const G4int pdg) const
{
  if (std::abs(pdg) < kLightParticlePDGLimit) {
    const G4int index = fLightParticleIndices[pdg + kLightParticlePDGOffset];
    return index != 0 || pdg == kPhotonPDG ? index : -1;
  }
  if (pdg < kFirstSupportedIonPDG) return -1;
  const auto found = fIonIndices.find(pdg);
  return found == fIonIndices.end() ? -1 : found->second;
}

}  // namespace atris
