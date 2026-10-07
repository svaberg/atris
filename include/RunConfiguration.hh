#ifndef RunConfiguration_hh
#define RunConfiguration_hh

#include "G4GenericMessenger.hh"
#include "globals.hh"

class G4RunManager;
class G4GDMLParser;
class G4UIcommand;

namespace atris {

class PhantomResponses;
struct RunSettings;

class RunConfiguration
{
  public:
    RunConfiguration(
      G4RunManager* runManager,
      RunSettings& settings,
      ::G4GDMLParser& parser,
      PhantomResponses& phantomResponses
    );

  private:
    void SetRandomSeeds(G4long firstSeed, G4long secondSeed);
    void AddPhantomResponse();
    void Initialize();

    G4RunManager* const fRunManager;
    RunSettings& fSettings;
    ::G4GDMLParser& fParser;
    PhantomResponses& fPhantomResponses;
    G4String fGeometryFileName = "simulation.gdml";
    G4String fEnergyBinsFileName = "simulation.bins";
    G4String fOutputModeName = "response";
    G4GenericMessenger fMessenger;
    G4GenericMessenger fDirectionHistogramMessenger;
    G4GenericMessenger fPositionHistogramMessenger;
    G4GenericMessenger fPhantomMessenger;
    G4GenericMessenger fPhantomResponseMessenger;
    G4String fPhantomName;
    G4String fPhantomResponseName;
    G4String fPhantomResponseTableFile;
    G4bool fPhantomResponseScaleByCrossingEnergy = false;
    G4bool fPhantomResponseScaleByRadiationWeight = false;
    G4bool fPhantomResponseScaleByInversePhantomMass = false;
    G4UIcommand* fAddPhantomResponseCommand = nullptr;
    G4UIcommand* fInitializeCommand = nullptr;
};

}  // namespace atris

#endif
