#include "RunConfiguration.hh"

#include "DetectorConstruction.hh"
#include "OutputMode.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"
#include "UserActionInitialization.hh"

#include "G4ApplicationState.hh"
#include "G4Exception.hh"
#include "G4GDMLParser.hh"
#include "G4PhysListFactory.hh"
#include "G4RunManager.hh"
#include "G4StepLimiterPhysics.hh"
#include "G4UIcommand.hh"
#include "G4UIparameter.hh"
#include "Randomize.hh"

#include <array>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <utility>
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

G4int CountSensitiveDetectors(const G4GDMLParser& parser)
{
  G4int detectorCount = 0;
  const G4GDMLAuxMapType* const auxiliaryMap = parser.GetAuxMap();
  for (const auto& [volume, auxiliaries] : *auxiliaryMap) {
    static_cast<void>(volume);
    for (const auto& auxiliary : auxiliaries) {
      if (auxiliary.type == "SensDet") ++detectorCount;
    }
  }
  return detectorCount;
}

}  // namespace

namespace atris {

RunConfiguration::RunConfiguration(
  G4RunManager* runManager,
  RunSettings& settings,
  ::G4GDMLParser& parser,
  PhantomResponses& phantomResponses
)
  : fRunManager(runManager),
    fSettings(settings),
    fParser(parser),
    fPhantomResponses(phantomResponses),
    fMessenger(this, "/atris/", "AtRIS run configuration."),
    fPhantomMessenger(
      this,
      "/atris/phantom/",
      "AtRIS phantom response files."
    )
{
  auto& geometryFileCommand = fMessenger.DeclareMethod(
    "geometryFile",
    &RunConfiguration::SetGeometryFile,
    "Read the run geometry from a GDML file."
  );
  geometryFileCommand.SetStates(G4State_PreInit);
  fGeometryFileCommand = geometryFileCommand.command;

  auto& energyBinsFileCommand = fMessenger.DeclareMethod(
    "energyBinsFile",
    &RunConfiguration::SetEnergyBinsFile,
    "Read the primary-energy histogram edges from a file."
  );
  energyBinsFileCommand.SetStates(G4State_PreInit);
  fEnergyBinsFileCommand = energyBinsFileCommand.command;

  auto& outputFileCommand = fMessenger.DeclareMethod(
    "outputFile",
    &RunConfiguration::SetOutputFile,
    "Set the analysis output filename."
  );
  outputFileCommand.SetStates(G4State_PreInit);
  fOutputFileCommand = outputFileCommand.command;

  auto& randomSeedsCommand = fMessenger.DeclareMethod(
    "randomSeeds",
    &RunConfiguration::SetRandomSeeds,
    "Set the two random seeds for this run."
  );
  randomSeedsCommand.SetParameterName(G4int{0}, "firstSeed", false);
  randomSeedsCommand.SetParameterName(G4int{1}, "secondSeed", false);
  randomSeedsCommand.SetRange("firstSeed>0 && secondSeed>0");
  randomSeedsCommand.SetStates(G4State_PreInit);
  fRandomSeedsCommand = randomSeedsCommand.command;

  fPhantomResponseCommand = new G4UIcommand(
    "/atris/phantom/response",
    this
  );
  fPhantomResponseCommand->SetGuidance(
    "Add a named response table for a phantom."
  );
  fPhantomResponseCommand->SetParameter(
    new G4UIparameter("phantomStem", 's', false)
  );
  fPhantomResponseCommand->SetParameter(
    new G4UIparameter("responseName", 's', false)
  );
  auto* const accumulationParameter = new G4UIparameter(
    "accumulation",
    's',
    false
  );
  accumulationParameter->SetParameterCandidates(
    "coefficient energy radiation-weighted-energy"
  );
  fPhantomResponseCommand->SetParameter(accumulationParameter);
  fPhantomResponseCommand->SetParameter(
    new G4UIparameter("file", 's', false)
  );
  fPhantomResponseCommand->AvailableForStates(G4State_PreInit);

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

}

RunConfiguration::~RunConfiguration()
{
  delete fPhantomResponseCommand;
}

void RunConfiguration::SetNewValue(
  G4UIcommand* const command,
  G4String newValue
)
{
  if (command == fPhantomResponseCommand) SetPhantomResponse(newValue);
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
    || !fHasConfiguredGeometry
    || !fHasConfiguredEnergyBins
    || !fHasConfiguredOutputFile
    || fSettings.physicsListName.empty()
    || !fHasConfiguredOutputMode
    || !fHasConfiguredOutputFormat
  ) return;
  fRunManager->SetUserInitialization(
    new UserActionInitialization(fSettings, fPhantomResponses)
  );
  fHasUserActions = true;
}

void RunConfiguration::SetGeometryFile(G4String requestedFile)
{
  if (fHasConfiguredGeometry) {
    if (requestedFile == fSettings.geometryFileName) return;
    G4ExceptionDescription message;
    message << "AtRIS geometry-file conflict: the run already selects '"
            << fSettings.geometryFileName << "' but the macro later requests '"
            << requestedFile << "'.";
    fGeometryFileCommand->CommandFailed(message);
    return;
  }

  std::ifstream geometry(requestedFile);
  if (!geometry.good()) {
    G4ExceptionDescription message;
    message << "Cannot open AtRIS geometry file '" << requestedFile << "'.";
    fGeometryFileCommand->CommandFailed(message);
    return;
  }
  geometry.close();

  fParser.Read(requestedFile);
  fSettings.geometryFileName = requestedFile;
  std::filesystem::path inputPath(requestedFile.c_str());
  inputPath.replace_extension();
  fSettings.simulationInputPrefix = inputPath.string();
  fSettings.detectorCount = CountSensitiveDetectors(fParser);
  fSettings.detectorBins.clear();
  fSettings.detectorBins.reserve(fSettings.detectorCount + 1);
  constexpr G4double detectorBinHalfWidth = 0.5;
  for (G4int index = 0; index <= fSettings.detectorCount; ++index) {
    fSettings.detectorBins.push_back(index - detectorBinHalfWidth);
  }
  G4cout << "### AtRIS: geometry contains " << fSettings.detectorCount
         << " sensitive detectors" << G4endl;

  fRunManager->SetUserInitialization(
    new DetectorConstruction(fParser, fSettings, fPhantomResponses)
  );
  fHasConfiguredGeometry = true;
  InstallUserActionsIfConfigured();
}

void RunConfiguration::SetEnergyBinsFile(G4String requestedFile)
{
  if (fHasConfiguredEnergyBins) {
    if (requestedFile == fSettings.energyBinsFileName) return;
    G4ExceptionDescription message;
    message << "AtRIS energy-bins-file conflict: the run already selects '"
            << fSettings.energyBinsFileName << "' but the macro later requests '"
            << requestedFile << "'.";
    fEnergyBinsFileCommand->CommandFailed(message);
    return;
  }

  std::ifstream input(requestedFile);
  std::vector<G4double> edges;
  G4double edge;
  while (input >> edge) edges.push_back(edge);
  if (!input.eof() || edges.size() < 2) {
    G4ExceptionDescription message;
    message << "AtRIS energy-bin file '" << requestedFile
            << "' must contain at least two numeric edges.";
    fEnergyBinsFileCommand->CommandFailed(message);
    return;
  }

  fSettings.energyBinsFileName = requestedFile;
  fSettings.energyBins = std::move(edges);
  fHasConfiguredEnergyBins = true;
  G4cout << "### AtRIS: read " << fSettings.energyBins.size()
         << " energy-bin edges from " << requestedFile << G4endl;
  InstallUserActionsIfConfigured();
}

void RunConfiguration::SetOutputFile(G4String requestedFile)
{
  if (fHasConfiguredOutputFile) {
    if (requestedFile == fSettings.outputFileName) return;
    G4ExceptionDescription message;
    message << "AtRIS output-file conflict: the run already selects '"
            << fSettings.outputFileName << "' but the macro later requests '"
            << requestedFile << "'.";
    fOutputFileCommand->CommandFailed(message);
    return;
  }
  if (requestedFile.empty()) {
    G4ExceptionDescription message;
    message << "AtRIS output filename cannot be empty.";
    fOutputFileCommand->CommandFailed(message);
    return;
  }

  fSettings.outputFileName = requestedFile;
  fHasConfiguredOutputFile = true;
  InstallUserActionsIfConfigured();
}

void RunConfiguration::SetRandomSeeds(
  const G4long firstSeed,
  const G4long secondSeed
)
{
  if (fHasConfiguredSeeds) {
    if (
      firstSeed == fSettings.explicitSeeds[0]
      && secondSeed == fSettings.explicitSeeds[1]
    ) return;
    G4ExceptionDescription message;
    message << "AtRIS random seeds are configured more than once with "
               "different values.";
    fRandomSeedsCommand->CommandFailed(message);
    return;
  }

  // CLHEP expects two seeds followed by a zero terminator.
  const std::array<G4long, 3> seeds = {firstSeed, secondSeed, 0};
  G4Random::setTheSeeds(seeds.data());
  fSettings.explicitSeeds = {firstSeed, secondSeed};
  fSettings.hasExplicitSeeds = true;
  fHasConfiguredSeeds = true;
  G4cout << "### AtRIS: using random seeds " << firstSeed << " and "
         << secondSeed << G4endl;
}

void RunConfiguration::SetPhantomResponse(G4String specification)
{
  std::istringstream fields(specification);
  G4String phantomStem;
  G4String responseName;
  G4String accumulationName;
  G4String fileName;
  G4String extra;
  if (
    !(fields >> phantomStem >> responseName >> accumulationName >> fileName)
    || fields >> extra
  ) {
    G4ExceptionDescription message;
    message << "Expected: <phantom-stem> <response-name> "
            << "<accumulation> <file>.";
    fPhantomResponseCommand->CommandFailed(message);
    return;
  }
  if (!fPhantomResponses.Add(
        phantomStem,
        responseName,
        accumulationName,
        fileName
      )) {
    G4ExceptionDescription message;
    message << "Could not configure response '" << responseName
            << "' for phantom '" << phantomStem << "'.";
    fPhantomResponseCommand->CommandFailed(message);
    return;
  }
}

void RunConfiguration::SetPhysicsList(G4String requestedPhysicsList)
{
  if (!fSettings.physicsListName.empty()) {
    if (requestedPhysicsList == fSettings.physicsListName) return;

    G4ExceptionDescription message;
    message << "AtRIS physics-list conflict: the run already selects '"
            << fSettings.physicsListName << "' but the macro requests '"
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
  InstallUserActionsIfConfigured();
}

void RunConfiguration::SetOutputMode(G4String requestedOutputMode)
{
  const G4int requestedValue = OutputModeValue(requestedOutputMode);
  if (fHasConfiguredOutputMode) {
    if (requestedValue == fSettings.outputMode) return;

    G4ExceptionDescription message;
    message << "AtRIS output mode is configured more than once with "
               "different values.";
    fOutputModeCommand->CommandFailed(message);
    return;
  }

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
  if (fSettings.outputMode == kInterfaceOutputMode) {
    G4cout << "### AtRIS: mode 0 writes histograms and interface ntuples"
           << G4endl;
  }
  if (fSettings.outputMode == kStepOutputMode) {
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
