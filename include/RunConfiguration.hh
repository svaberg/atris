#ifndef RunConfiguration_hh
#define RunConfiguration_hh

#include "G4GenericMessenger.hh"
#include "G4UImessenger.hh"
#include "globals.hh"

class G4RunManager;
class G4GDMLParser;
class G4UIcommand;

namespace atris {

class PhantomResponses;
struct RunSettings;

class RunConfiguration : public G4UImessenger
{
  public:
    RunConfiguration(
      G4RunManager* runManager,
      RunSettings& settings,
      ::G4GDMLParser& parser,
      PhantomResponses& phantomResponses
    );
    ~RunConfiguration() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

  private:
    void DeclareHistogramBinsCommand(
      const G4String& name,
      void (RunConfiguration::*setter)(G4int, G4int),
      const G4String& guidance
    );
    G4bool InstallPhysicsList(const G4String& requestedPhysicsList);
    void InstallUserActionsIfConfigured();
    void SetGeometryFile(G4String requestedFile);
    void SetEnergyBinsFile(G4String requestedFile);
    void SetOutputFile(G4String requestedFile);
    void SetRandomSeeds(G4long firstSeed, G4long secondSeed);
    void SetPhantomResponse(G4String specification);
    void SetPhysicsList(G4String requestedPhysicsList);
    void SetOutputMode(G4String requestedOutputMode);
    void SetOutputFormat(G4String requestedOutputFormat);
    void ReportOutputMode() const;
    void SetDirectionBins(G4int azimuthBins, G4int cosineBins);
    void SetPositionBins(G4int azimuthBins, G4int cosineBins);

    G4RunManager* const fRunManager;
    RunSettings& fSettings;
    ::G4GDMLParser& fParser;
    PhantomResponses& fPhantomResponses;
    G4bool fHasConfiguredOutputMode = false;
    G4bool fHasConfiguredOutputFormat = false;
    G4bool fHasConfiguredGeometry = false;
    G4bool fHasConfiguredEnergyBins = false;
    G4bool fHasConfiguredOutputFile = false;
    G4bool fHasConfiguredSeeds = false;
    G4bool fHasUserActions = false;
    G4GenericMessenger fMessenger;
    G4GenericMessenger fPhantomMessenger;
    G4UIcommand* fGeometryFileCommand = nullptr;
    G4UIcommand* fEnergyBinsFileCommand = nullptr;
    G4UIcommand* fOutputFileCommand = nullptr;
    G4UIcommand* fRandomSeedsCommand = nullptr;
    G4UIcommand* fPhantomResponseCommand = nullptr;
    G4UIcommand* fPhysicsListCommand = nullptr;
    G4UIcommand* fOutputModeCommand = nullptr;
    G4UIcommand* fOutputFormatCommand = nullptr;
};

}  // namespace atris

#endif
