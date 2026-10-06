#ifndef RunConfiguration_hh
#define RunConfiguration_hh

#include "G4GenericMessenger.hh"
#include "globals.hh"

class G4RunManager;
class G4UIcommand;

namespace atris {

struct RunSettings;

class RunConfiguration
{
  public:
    RunConfiguration(
      G4RunManager* runManager,
      RunSettings& settings,
      const G4String& physicsList
    );

    G4bool IsValid() const { return fIsValid; }

  private:
    void DeclareHistogramBinsCommand(
      const G4String& name,
      void (RunConfiguration::*setter)(G4int, G4int),
      const G4String& guidance
    );
    G4bool InstallPhysicsList(const G4String& requestedPhysicsList);
    void InstallUserActionsIfConfigured();
    void SetPhysicsList(G4String requestedPhysicsList);
    void SetOutputMode(G4String requestedOutputMode);
    void SetOutputFormat(G4String requestedOutputFormat);
    void ReportOutputMode() const;
    void SetDirectionBins(G4int azimuthBins, G4int cosineBins);
    void SetPositionBins(G4int azimuthBins, G4int cosineBins);

    G4RunManager* const fRunManager;
    RunSettings& fSettings;
    const G4bool fHasCommandLineSettings;
    G4bool fHasConfiguredOutputMode;
    G4bool fHasConfiguredOutputFormat = false;
    G4bool fIsValid = true;
    G4bool fHasUserActions = false;
    G4GenericMessenger fMessenger;
    G4UIcommand* fPhysicsListCommand = nullptr;
    G4UIcommand* fOutputModeCommand = nullptr;
    G4UIcommand* fOutputFormatCommand = nullptr;
};

}  // namespace atris

#endif
