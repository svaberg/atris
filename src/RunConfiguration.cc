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

G4int OutputModeValue(const G4String& name)
{
  if (name == "response") return atris::kResponseOutputMode;
  if (name == "profile") return atris::kInterfaceOutputMode;
  if (name == "shower") return atris::kStepOutputMode;
  return atris::kInvalidOutputMode;
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
    fGeometryFileName,
    "Read the run geometry from a GDML file."
  ).SetStates(G4State_PreInit);

  fMessenger.DeclareProperty(
    "energyBinsFile",
    fEnergyBinsFileName,
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
    "name", fPhantomName, "Select the phantom receiving subsequent responses."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "name", fPhantomResponseName, "Set the response histogram name."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "tableFile",
    fPhantomResponseTableFile,
    "Set the particle- and energy-dependent response-table file."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "scaleByCrossingEnergy",
    fPhantomResponseScaleByCrossingEnergy,
    "Multiply the table coefficient by crossing kinetic energy in eV."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "scaleByRadiationWeight",
    fPhantomResponseScaleByRadiationWeight,
    "Multiply the response by the particle radiation weight."
  ).SetStates(G4State_PreInit);

  fPhantomResponseMessenger.DeclareProperty(
    "scaleByInversePhantomMass",
    fPhantomResponseScaleByInversePhantomMass,
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

  auto& outputModeCommand = fMessenger.DeclareProperty(
    "outputMode",
    fOutputModeName,
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

void RunConfiguration::AddPhantomResponse()
{
  if (
    fPhantomName.empty()
    || fPhantomResponseName.empty()
    || fPhantomResponseTableFile.empty()
  ) {
    G4ExceptionDescription message;
    message << "Set /atris/phantom/name, /atris/phantom/response/name, and "
               "/atris/phantom/response/tableFile before "
               "/atris/phantom/response/add.";
    fAddPhantomResponseCommand->CommandFailed(message);
    return;
  }
  if (!fPhantomResponses.Add(
        fPhantomName,
        fPhantomResponseName,
        fPhantomResponseTableFile,
        fPhantomResponseScaleByCrossingEnergy,
        fPhantomResponseScaleByRadiationWeight,
        fPhantomResponseScaleByInversePhantomMass
      )) {
    G4ExceptionDescription message;
    message << "Could not configure response '" << fPhantomResponseName
            << "' for phantom '" << fPhantomName << "'.";
    fAddPhantomResponseCommand->CommandFailed(message);
    return;
  }
  fPhantomResponseName.clear();
  fPhantomResponseTableFile.clear();
  fPhantomResponseScaleByCrossingEnergy = false;
  fPhantomResponseScaleByRadiationWeight = false;
  fPhantomResponseScaleByInversePhantomMass = false;
}

void RunConfiguration::Initialize()
{
  if (fSettings.outputStem.empty()) {
    G4ExceptionDescription message;
    message << "AtRIS initialization requires outputStem.";
    fInitializeCommand->CommandFailed(message);
    return;
  }

  std::ifstream energyBinsFile(fEnergyBinsFileName);
  std::vector<G4double> energyBins;
  G4double energyBinEdge;
  while (energyBinsFile >> energyBinEdge) energyBins.push_back(energyBinEdge);
  if (!energyBinsFile.eof() || energyBins.size() < 2) {
    G4ExceptionDescription message;
    message << "AtRIS energy-bin file '" << fEnergyBinsFileName
            << "' must contain at least two numeric edges.";
    fInitializeCommand->CommandFailed(message);
    return;
  }
  fSettings.energyBins = std::move(energyBins);
  G4cout << "### AtRIS: read " << fSettings.energyBins.size()
         << " energy-bin edges from " << fEnergyBinsFileName << G4endl;

  fSettings.outputMode = OutputModeValue(fOutputModeName);
  if (fSettings.outputMode == kInterfaceOutputMode) {
    G4cout << "### AtRIS: profile mode writes histograms and interface ntuples"
           << G4endl;
  }
  if (fSettings.outputMode == kStepOutputMode) {
    G4cout << "### AtRIS: shower mode writes histograms, interface, and "
              "transport-step ntuples; output may be very large"
           << G4endl;
  }

  fParser.Read(fGeometryFileName);
  std::filesystem::path inputPath(fGeometryFileName.c_str());
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
