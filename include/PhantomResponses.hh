#ifndef PhantomResponses_hh
#define PhantomResponses_hh

#include "globals.hh"

#include <map>
#include <set>
#include <vector>

namespace atris {

struct PhantomResponse
{
  G4String phantomStem;
  G4String name;
  G4String fileName;
  G4bool scaleByCrossingEnergy;
  G4bool scaleByRadiationWeight;
  G4bool scaleByInversePhantomMass;
  const std::vector<G4double>* values;
};

class PhantomResponses
{
  public:
    G4bool Add(
      const G4String& phantomStem,
      const G4String& responseName,
      const G4String& fileName,
      G4bool scaleByCrossingEnergy,
      G4bool scaleByRadiationWeight,
      G4bool scaleByInversePhantomMass
    );

    const std::vector<PhantomResponse>& GetAll() const { return fResponses; }
    G4int GetPhantomCount() const
    {
      return static_cast<G4int>(fPhantomStems.size());
    }
    G4int FindParticleIndex(G4int pdg) const;

  private:
    void ConfigureParticleLookup(
      const std::vector<G4int>& particleCodes,
      const G4String& fileName
    );

    std::vector<G4int> fParticleCodes;
    G4String fParticleHeaderFile;
    std::vector<G4int> fLightParticleIndices;
    std::map<G4int, G4int> fIonIndices;
    std::set<G4String> fPhantomStems;
    std::map<G4String, std::vector<G4double>> fTables;
    std::vector<PhantomResponse> fResponses;
};

}  // namespace atris

#endif
