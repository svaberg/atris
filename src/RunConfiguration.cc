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
#include "Randomize.hh"

#include <array>
#include <filesystem>
#include <fstream>
#include <utility>
#include <vector>

namespace {

atris::OutputMode OutputModeValue(const G4String& name)
{
  if (name == "response") return atris::OutputMode::kResponse;
  if (name == "profile") return atris::OutputMode::kProfile;
  if (name == "shower") return atris::OutputMode::kShower;
  return atris::OutputMode::kInvalid;
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

void DeclareHistogramBinsProperties(
  G4GenericMessenger& messenger,
  std::array<G4int, 2>& bins
)
{
  auto& azimuthBins = messenger.DeclareProperty(
    "azimuthBins",
    bins[0],
    "Set the number of azimuth bins."
  );
  azimuthBins.SetParameterName("azimuthBins", false);
  azimuthBins.SetRange("azimuthBins>0");
  azimuthBins.SetStates(G4State_PreInit);

  auto& cosineBins = messenger.DeclareProperty(
    "cosineBins",
    bins[1],
    "Set the number of cosine bins."
  );
  cosineBins.SetParameterName("cosineBins", false);
  cosineBins.SetRange("cosineBins>0");
  cosineBins.SetStates(G4State_PreInit);
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
    fDirectionHistogramMessenger(
      this,
      "/atris/directionHistogram/",
      "Source-direction histogram configuration."
    ),
    fPositionHistogramMessenger(
      this,
      "/atris/positionHistogram/",
      "Source-position histogram configuration."
    ),
    fPhantomMessenger(
      this,
      "/atris/phantom/",
      "AtRIS phantom response files."
    ),
    fPhantomResponseMessenger(
      this,
      "/atris/phantom/response/",
      "One response for the selected phantom."
    )
{
  fMessenger.DeclareProperty(
    "geometryFile",
    fSettings.geometryFileName,
    "Read the run geometry from a GDML file."
  ).SetStates(G4State_PreInit);

  fMessenger.DeclareProperty(
    "energyBinsFile",
    fSettings.energyBinsFileName,
    "Read the primary-energy histogram edges from a file."
  ).SetStates(G4State_PreInit);

  fMessenger.DeclareProperty(
    "outputStem",
    fSettings.outputStem,
    "Set the filename stem shared by the analysis outputs."
  ).SetStates(G4State_PreInit);

  auto& randomSeedsCommand = fMessenger.DeclareMethod(
    "randomSeeds",
    &RunConfiguration::SetRandomSeeds,
    "Set the two random seeds for this run."
  );
  randomSeedsCommand.SetParameterName(G4int{0}, "firstSeed", false);
  randomSeedsCommand.SetParameterName(G4int{1}, "secondSeed", false);
  randomSeedsCommand.SetRange("firstSeed>0 && secondSeed>0");
  randomSeedsCommand.SetStates(G4State_PreInit);

  fPhantomMessenger.DeclareProperty(
    "name",
    fPendingResponse.phantomStem,
    "Select the phantom receiving subsequent responses."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "name",
    fPendingResponse.name,
    "Set the response histogram name."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "tableFile",
    fPendingResponse.fileName,
    "Set the particle- and energy-dependent response-table file."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "scaleByCrossingEnergy",
    fPendingResponse.scaleByCrossingEnergy,
    "Multiply the table coefficient by crossing kinetic energy in eV."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "scaleByRadiationWeight",
    fPendingResponse.scaleByRadiationWeight,
    "Multiply the response by the particle radiation weight."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "scaleByInversePhantomMass",
    fPendingResponse.scaleByInversePhantomMass,
    "Divide this response by phantom mass during post-processing."
  ).SetStates(G4State_PreInit);

  auto& addPhantomResponseCommand = fPhantomResponseMessenger.DeclareMethod(
    "add",
    &RunConfiguration::AddPhantomResponse,
    "Add the configured response to the selected phantom."
  );
  addPhantomResponseCommand.SetStates(G4State_PreInit);
  fAddPhantomResponseCommand = addPhantomResponseCommand.command;

  fMessenger.DeclareProperty(
    "physicsList",
    fSettings.physicsListName,
    "Set the Geant4 reference physics list."
  ).SetStates(G4State_PreInit);

  auto& outputModeCommand = fMessenger.DeclareMethod(
    "outputMode",
    &RunConfiguration::SetOutputMode,
    "Set the AtRIS output mode."
  );
  outputModeCommand.SetCandidates("response profile shower");
  outputModeCommand.SetStates(G4State_PreInit);

  fMessenger.DeclareProperty(
    "outputFormat",
    fSettings.outputFileFormat,
    "Set the Geant4 analysis output format."
  ).SetStates(G4State_PreInit);

  auto& initializeCommand = fMessenger.DeclareMethod(
    "initialize",
    &RunConfiguration::Initialize,
    "Apply the final AtRIS configuration and initialize Geant4."
  );
  initializeCommand.SetStates(G4State_PreInit);
  fInitializeCommand = initializeCommand.command;

  DeclareHistogramBinsProperties(
    fDirectionHistogramMessenger,
    fSettings.directionHistogramBins
  );
  DeclareHistogramBinsProperties(
    fPositionHistogramMessenger,
    fSettings.positionHistogramBins
  );

}

void RunConfiguration::SetRandomSeeds(
  const G4long firstSeed,
  const G4long secondSeed
)
{
  fSettings.explicitSeeds = {firstSeed, secondSeed};
}

void RunConfiguration::SetOutputMode(G4String outputModeName)
{
  fSettings.outputMode = OutputModeValue(outputModeName);
}

void RunConfiguration::AddPhantomResponse()
{
  if (
    fPendingResponse.phantomStem.empty()
    || fPendingResponse.name.empty()
    || fPendingResponse.fileName.empty()
  ) {
    G4ExceptionDescription message;
    message << "Set /atris/phantom/name, /atris/phantom/response/name, and "
               "/atris/phantom/response/tableFile before "
               "/atris/phantom/response/add.";
    fAddPhantomResponseCommand->CommandFailed(message);
    return;
  }
  if (!fPhantomResponses.Add(fPendingResponse)) {
    G4ExceptionDescription message;
    message << "Could not configure response '"
            << fPendingResponse.name << "' for phantom '"
            << fPendingResponse.phantomStem << "'.";
    fAddPhantomResponseCommand->CommandFailed(message);
    return;
  }
  const G4String phantomStem = fPendingResponse.phantomStem;
  fPendingResponse = {};
  fPendingResponse.phantomStem = phantomStem;
}

void RunConfiguration::Initialize()
{
  if (fSettings.outputStem.empty()) {
    G4ExceptionDescription message;
    message << "AtRIS initialization requires outputStem.";
    fInitializeCommand->CommandFailed(message);
    return;
  }

  std::ifstream energyBinsFile(fSettings.energyBinsFileName);
  std::vector<G4double> energyBins;
  G4double energyBinEdge;
  while (energyBinsFile >> energyBinEdge) energyBins.push_back(energyBinEdge);
  if (!energyBinsFile.eof() || energyBins.size() < 2) {
    G4ExceptionDescription message;
    message << "AtRIS energy-bin file '" << fSettings.energyBinsFileName
            << "' must contain at least two numeric edges.";
    fInitializeCommand->CommandFailed(message);
    return;
  }
  fSettings.energyBins = std::move(energyBins);
  G4cout << "### AtRIS: read " << fSettings.energyBins.size()
         << " energy-bin edges from " << fSettings.energyBinsFileName << G4endl;

  if (fSettings.outputMode == OutputMode::kProfile) {
    G4cout << "### AtRIS: profile mode writes histograms and interface ntuples"
           << G4endl;
  }
  if (fSettings.outputMode == OutputMode::kShower) {
    G4cout << "### AtRIS: shower mode writes histograms, interface, and "
              "transport-step ntuples; output may be very large"
           << G4endl;
  }

  fParser.Read(fSettings.geometryFileName);
  std::filesystem::path inputPath(fSettings.geometryFileName.c_str());
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
  G4PhysListFactory factory;
  G4VModularPhysicsList* const physicsList =
    factory.GetReferencePhysList(fSettings.physicsListName);
  physicsList->RegisterPhysics(new G4StepLimiterPhysics());
  fRunManager->SetUserInitialization(physicsList);
  fRunManager->SetUserInitialization(
    new UserActionInitialization(fSettings, fPhantomResponses)
  );

  if (fSettings.explicitSeeds[0] != 0) {
    // CLHEP expects two seeds followed by a zero terminator.
    const std::array<G4long, 3> seeds = {
      fSettings.explicitSeeds[0],
      fSettings.explicitSeeds[1],
      0,
    };
    G4Random::setTheSeeds(seeds.data());
    G4cout << "### AtRIS: using random seeds " << fSettings.explicitSeeds[0]
           << " and " << fSettings.explicitSeeds[1] << G4endl;
  }
  fRunManager->Initialize();
}

}  // namespace atris
