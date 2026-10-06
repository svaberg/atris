#ifndef PhantomResponses_hh
#define PhantomResponses_hh

#include "globals.hh"

#include <map>
#include <string>
#include <vector>

namespace atris {

class PhantomResponses
{
  public:
    G4bool Add(
      G4int phantomIndex,
      const G4String& radiationFile,
      const G4String& countingFile
    );

    G4int GetCount() const { return static_cast<G4int>(fRadiation.size()); }
    G4int FindParticleIndex(G4int pdg) const;
    G4double GetRadiation(G4int phantomIndex, G4int responseIndex) const
    {
      return fRadiation[phantomIndex][responseIndex];
    }
    G4double GetCounting(G4int phantomIndex, G4int responseIndex) const
    {
      return fCounting[phantomIndex][responseIndex];
    }

  private:
    void ConfigureParticleLookup(
      const std::vector<G4int>& particleCodes,
      const G4String& fileName
    );

    std::vector<G4int> fParticleCodes;
    G4String fParticleHeaderFile;
    G4int fExpectedValueCount = 0;
    std::vector<G4int> fLightParticleIndices;
    std::map<G4int, G4int> fIonIndices;
    std::vector<std::vector<G4double>> fRadiation;
    std::vector<std::vector<G4double>> fCounting;
};

}  // namespace atris

#endif
