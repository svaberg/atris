#ifndef PhantomResponses_hh
#define PhantomResponses_hh

#include "globals.hh"

#include <map>
#include <vector>

namespace atris {

class PhantomResponses
{
  public:
    G4bool Load();

    G4int GetCount() const;
    G4int FindParticleIndex(G4int pdg) const;
    G4double GetRadiation(G4int phantomIndex, G4int responseIndex) const;
    G4double GetCounting(G4int phantomIndex, G4int responseIndex) const;

  private:
    std::vector<G4int> fLightParticleIndices;
    std::map<G4int, G4int> fIonIndices;
    std::vector<std::vector<G4double>> fRadiation;
    std::vector<std::vector<G4double>> fCounting;
};

}  // namespace atris

#endif
