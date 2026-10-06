#include "RunConfiguration.hh"

#include "OutputMode.hh"
#include "RunSettings.hh"
#include "UserActionInitialization.hh"

#include "G4ApplicationState.hh"
#include "G4Exception.hh"
#include "G4PhysListFactory.hh"
#include "G4RunManager.hh"
#include "G4StepLimiterPhysics.hh"
#include "G4UIcommand.hh"

#include <vector>

namespace {

constexpr std::size_t kLegacyPhysicsListSuffixLength = 4;
constexpr G4int kInvalidOutputMode = 2;

G4int OutputModeValue(const G4String& name)
{
  if (name == "response") return atris::kResponseOutputMode;
  if (name == "profile") return atris::kInterfaceOutputMode;
  if (name == "shower") return atris::kStepOutputMode;
  return kInvalidOutputMode;
}

G4String OutputModeName(const G4int value)
{
  if (value == atris::kResponseOutputMode) return "response";
  if (value == atris::kInterfaceOutputMode) return "profile";
  if (value == atris::kStepOutputMode) return "shower";
  return "invalid";
}

}  // namespace

namespace atris {

RunConfiguration::RunConfiguration(
  G4RunManager* runManager,
  RunSettings& settings,
  const G4String& physicsList,
  const G4int outputMode
)
  : fRunManager(runManager),
    fSettings(settings),
    fPhysicsList(physicsList),
    fOutputMode(outputMode),
    fHasCommandLineSettings(!physicsList.empty()),
    fHasConfiguredOutputMode(fHasCommandLineSettings),
    fMessenger(this, "/atris/", "AtRIS run configuration.")
{
  auto& physicsListCommand = fMessenger.DeclareMethod(
    "physicsList",
    &RunConfiguration::SetPhysicsList,
    "Set the Geant4 reference physics list."
  );
  physicsListCommand.SetStates(G4State_PreInit);
  fPhysicsListCommand = physicsListCommand.command;

  auto& outputModeCommand = fMessenger.DeclareMethod(
    "outputMode",
    &RunConfiguration::SetOutputMode,
    "Set the AtRIS output mode."
  );
  outputModeCommand.SetCandidates("response profile shower");
  outputModeCommand.SetStates(G4State_PreInit);
  fOutputModeCommand = outputModeCommand.command;

  auto& outputFormatCommand = fMessenger.DeclareMethod(
    "outputFormat",
    &RunConfiguration::SetOutputFormat,
    "Set the Geant4 analysis output format."
  );
  outputFormatCommand.SetStates(G4State_PreInit);
  fOutputFormatCommand = outputFormatCommand.command;

  DeclareHistogramBinsCommand(
    "directionBins",
    &RunConfiguration::SetDirectionBins,
    "Set the azimuth and cosine bin counts for the source-direction histogram."
  );
  DeclareHistogramBinsCommand(
    "positionBins",
    &RunConfiguration::SetPositionBins,
    "Set the azimuth and cosine bin counts for the source-position histogram."
  );

  if (fHasCommandLineSettings) {
    if (!InstallPhysicsList(fPhysicsList)) {
      fIsValid = false;
    } else {
      InstallUserActionsIfConfigured();
      ReportOutputMode();
    }
  }
}

G4bool RunConfiguration::IsValid() const
{
  return fIsValid;
}

void RunConfiguration::DeclareHistogramBinsCommand(
  const G4String& name,
  void (RunConfiguration::*setter)(G4int, G4int),
  const G4String& guidance
)
{
  auto& command = fMessenger.DeclareMethod(name, setter, guidance);
  command.SetParameterName(G4int{0}, "azimuthBins", false);
  command.SetParameterName(G4int{1}, "cosineBins", false);
  command.SetRange("azimuthBins>0 && cosineBins>0");
  command.SetStates(G4State_PreInit);
}

G4bool RunConfiguration::InstallPhysicsList(
  const G4String& requestedPhysicsList
)
{
  G4PhysListFactory factory;
  // Legacy validation also retries after removing four trailing characters.
  // The full name is still passed to Geant4, so this does not normalize input.
  const G4bool isValid = factory.IsReferencePhysList(requestedPhysicsList)
    || factory.IsReferencePhysList(
      requestedPhysicsList.substr(
        0,
        requestedPhysicsList.size() - kLegacyPhysicsListSuffixLength
      )
    );
  if (!isValid) {
    G4cout << "### AtRIS: " << requestedPhysicsList
           << " is not valid! use: " << G4endl;
    const std::vector<G4String> available = factory.AvailablePhysLists();
    for (const G4String& availablePhysicsList : available) {
      G4cout << availablePhysicsList << G4endl;
    }
    return false;
  }

  G4VModularPhysicsList* const physicsList =
    factory.GetReferencePhysList(requestedPhysicsList);
  physicsList->RegisterPhysics(new G4StepLimiterPhysics());
  fRunManager->SetUserInitialization(physicsList);
  fSettings.physicsListName = requestedPhysicsList;
  return true;
}

void RunConfiguration::InstallUserActionsIfConfigured()
{
  if (
    fHasUserActions
    || fPhysicsList.empty()
    || !fHasConfiguredOutputMode
    || (!fHasCommandLineSettings && !fHasConfiguredOutputFormat)
  ) return;
  fRunManager->SetUserInitialization(new UserActionInitialization(fSettings));
  fHasUserActions = true;
}

void RunConfiguration::SetPhysicsList(G4String requestedPhysicsList)
{
  if (!fPhysicsList.empty()) {
    if (requestedPhysicsList == fPhysicsList) return;

    G4ExceptionDescription message;
    message << "AtRIS physics-list conflict: ";
    if (fHasCommandLineSettings) {
      message << "the command line selects '";
    } else {
      message << "the run already selects '";
    }
    message << fPhysicsList << "' but the macro requests '"
            << requestedPhysicsList << "'.";
    fPhysicsListCommand->CommandFailed(message);
    return;
  }

  if (!InstallPhysicsList(requestedPhysicsList)) {
    G4ExceptionDescription message;
    message << "'" << requestedPhysicsList
            << "' is not a valid Geant4 reference physics list.";
    fPhysicsListCommand->CommandFailed(message);
    return;
  }
  fPhysicsList = requestedPhysicsList;
  InstallUserActionsIfConfigured();
}

void RunConfiguration::SetOutputMode(G4String requestedOutputMode)
{
  const G4int requestedValue = OutputModeValue(requestedOutputMode);
  if (fHasCommandLineSettings) {
    if (requestedValue == fOutputMode) return;

    G4ExceptionDescription message;
    message << "AtRIS output-mode conflict: the command line selects '"
            << OutputModeName(fOutputMode) << "' (" << fOutputMode
            << ") but the macro requests '" << requestedOutputMode
            << "' (" << requestedValue << ").";
    fOutputModeCommand->CommandFailed(message);
    return;
  }

  if (fHasConfiguredOutputMode) {
    if (requestedValue == fOutputMode) return;

    G4ExceptionDescription message;
    message << "AtRIS output-mode conflict: the run already selects '"
            << OutputModeName(fOutputMode) << "' (" << fOutputMode
            << ") but the macro later requests '" << requestedOutputMode
            << "' (" << requestedValue << ").";
    fOutputModeCommand->CommandFailed(message);
    return;
  }

  fOutputMode = requestedValue;
  fSettings.outputMode = requestedValue;
  fHasConfiguredOutputMode = true;
  InstallUserActionsIfConfigured();
  ReportOutputMode();
}

void RunConfiguration::SetOutputFormat(G4String requestedOutputFormat)
{
  if (
    !fSettings.outputFileFormat.empty()
    && requestedOutputFormat != fSettings.outputFileFormat
  ) {
    G4ExceptionDescription message;
    message << "AtRIS output-format conflict: the run already selects '"
            << fSettings.outputFileFormat << "' but the macro later requests '"
            << requestedOutputFormat << "'.";
    fOutputFormatCommand->CommandFailed(message);
    return;
  }

  fSettings.outputFileFormat = requestedOutputFormat;
  fHasConfiguredOutputFormat = true;
  InstallUserActionsIfConfigured();
}

void RunConfiguration::ReportOutputMode() const
{
  if (fOutputMode == kInterfaceOutputMode) {
    G4cout << "### AtRIS: mode 0 writes histograms and interface ntuples"
           << G4endl;
  }
  if (fOutputMode == kStepOutputMode) {
    G4cout << "### AtRIS: mode 1 writes histograms, interface, and "
              "transport-step ntuples; output may be very large"
           << G4endl;
  }
}

void RunConfiguration::SetDirectionBins(
  const G4int azimuthBins,
  const G4int cosineBins
)
{
  fSettings.directionHistogramBins = {azimuthBins, cosineBins};
}

void RunConfiguration::SetPositionBins(
  const G4int azimuthBins,
  const G4int cosineBins
)
{
  fSettings.positionHistogramBins = {azimuthBins, cosineBins};
}

}  // namespace atris
