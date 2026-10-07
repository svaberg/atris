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
    G4bool InstallPhysicsList(const G4String& requestedPhysicsList);
    void InstallUserActionsIfConfigured();
    void SetGeometryFile(G4String requestedFile);
    void SetEnergyBinsFile(G4String requestedFile);
    void SetOutputStem(G4String requestedStem);
    void SetRandomSeeds(G4long firstSeed, G4long secondSeed);
    void AddPhantomResponse();
    void SetPhysicsList(G4String requestedPhysicsList);
    void SetOutputMode(G4String requestedOutputMode);
    void SetOutputFormat(G4String requestedOutputFormat);
    void ReportOutputMode() const;

    G4RunManager* const fRunManager;
    RunSettings& fSettings;
    ::G4GDMLParser& fParser;
    PhantomResponses& fPhantomResponses;
    G4String fGeometryFileName;
    G4String fEnergyBinsFileName;
    G4bool fHasUserActions = false;
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
    G4UIcommand* fGeometryFileCommand = nullptr;
    G4UIcommand* fEnergyBinsFileCommand = nullptr;
    G4UIcommand* fOutputStemCommand = nullptr;
    G4UIcommand* fRandomSeedsCommand = nullptr;
    G4UIcommand* fAddPhantomResponseCommand = nullptr;
    G4UIcommand* fPhysicsListCommand = nullptr;
    G4UIcommand* fOutputModeCommand = nullptr;
    G4UIcommand* fOutputFormatCommand = nullptr;
};

}  // namespace atris

#endif
