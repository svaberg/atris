#include "RunConfiguration.hh"

#include "G4ApplicationState.hh"
#include "G4Exception.hh"
#include "G4GDMLParser.hh"
#include "G4PhysListFactory.hh"
#include "G4RunManager.hh"
#include "G4StepLimiterPhysics.hh"
#include "G4UIcommand.hh"
#include "Randomize.hh"

#include "DetectorConstruction.hh"
#include "OutputMode.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"
#include "UserActionInitialization.hh"

#include <array>
#include <filesystem>
#include <fstream>
#include <utility>
#include <vector>

namespace
{

atris::OutputMode OutputModeValue(const G4String& name)
{
  if (name == "response") return atris::OutputMode::kResponse;
  if (name == "profile") return atris::OutputMode::kProfile;
  if (name == "shower") return atris::OutputMode::kShower;
  return atris::OutputMode::kInvalid;
}

G4int CountSensitiveDetectors(const G4GDMLParser& gdmlParser)
{
  G4int detectorCount = 0;
  const G4GDMLAuxMapType* const auxiliaryMap = gdmlParser.GetAuxMap();
  for (const auto& [volume, auxiliaries] : *auxiliaryMap)
  {
    static_cast<void>(volume);
    for (const auto& auxiliary : auxiliaries)
    {
      if (auxiliary.type == "SensDet") ++detectorCount;
    }
  }
  return detectorCount;
}

void DeclareHistogramBinsProperties(G4GenericMessenger& messenger, std::array<G4int, 2>& bins)
{
  auto& azimuthBinsCommand =
    messenger.DeclareProperty("azimuthBins", bins[0], "Set the number of azimuth bins.");
  azimuthBinsCommand.SetParameterName("azimuthBins", false);
  azimuthBinsCommand.SetRange("azimuthBins>0");
  azimuthBinsCommand.SetStates(G4State_PreInit);

  auto& cosineBinsCommand =
    messenger.DeclareProperty("cosineBins", bins[1], "Set the number of cosine bins.");
  cosineBinsCommand.SetParameterName("cosineBins", false);
  cosineBinsCommand.SetRange("cosineBins>0");
  cosineBinsCommand.SetStates(G4State_PreInit);
}

}  // namespace

namespace atris
{

RunConfiguration::RunConfiguration(G4RunManager* runManager, RunSettings& runSettings,
                                   ::G4GDMLParser& gdmlParser, PhantomResponses& phantomResponses)
  : fRunManager(runManager),
    fRunSettings(runSettings),
    fGDMLParser(gdmlParser),
    fPhantomResponses(phantomResponses),
    fRunMessenger(this, "/atris/", "AtRIS run configuration."),
    fDirectionHistogramMessenger(this, "/atris/directionHistogram/",
                                 "Source-direction histogram configuration."),
    fPositionHistogramMessenger(this, "/atris/positionHistogram/",
                                "Source-position histogram configuration."),
    fPhantomMessenger(this, "/atris/phantom/", "AtRIS phantom response files."),
    fPhantomResponseMessenger(this, "/atris/phantom/response/",
                              "One response for the selected phantom.")
{
  fRunMessenger
    .DeclareProperty("geometryFile", fRunSettings.geometryFileName,
                     "Read the run geometry from a GDML file.")
    .SetStates(G4State_PreInit);

  fRunMessenger
    .DeclareProperty("energyBinsFile", fRunSettings.energyBinsFileName,
                     "Read the primary-energy histogram edges from a file.")
    .SetStates(G4State_PreInit);

  fRunMessenger
    .DeclareProperty("outputStem", fRunSettings.outputStem,
                     "Set the filename stem shared by the analysis outputs.")
    .SetStates(G4State_PreInit);

  auto& randomSeedsCommand = fRunMessenger.DeclareMethod(
    "randomSeeds", &RunConfiguration::SetRandomSeeds, "Set the two random seeds for this run.");
  randomSeedsCommand.SetParameterName(G4int{0}, "firstSeed", false);
  randomSeedsCommand.SetParameterName(G4int{1}, "secondSeed", false);
  randomSeedsCommand.SetRange("firstSeed>0 && secondSeed>0");
  randomSeedsCommand.SetStates(G4State_PreInit);

  fPhantomMessenger
    .DeclareProperty("name", fPendingResponse.phantomStem,
                     "Select the phantom receiving subsequent responses.")
    .SetStates(G4State_PreInit);

  fPhantomResponseMessenger
    .DeclareProperty("name", fPendingResponse.name, "Set the response histogram name.")
    .SetStates(G4State_PreInit);

  fPhantomResponseMessenger
    .DeclareProperty("tableFile", fPendingResponse.fileName,
                     "Set the particle- and energy-dependent response-table file.")
    .SetStates(G4State_PreInit);

  fPhantomResponseMessenger
    .DeclareProperty("scaleByCrossingEnergy", fPendingResponse.scaleByCrossingEnergy,
                     "Multiply the table coefficient by crossing kinetic energy in eV.")
    .SetStates(G4State_PreInit);

  fPhantomResponseMessenger
    .DeclareProperty("scaleByRadiationWeight", fPendingResponse.scaleByRadiationWeight,
                     "Multiply the response by the particle radiation weight.")
    .SetStates(G4State_PreInit);

  fPhantomResponseMessenger
    .DeclareProperty("scaleByInversePhantomMass", fPendingResponse.scaleByInversePhantomMass,
                     "Divide this response by phantom mass during post-processing.")
    .SetStates(G4State_PreInit);

  auto& addPhantomResponseCommand =
    fPhantomResponseMessenger.DeclareMethod("add", &RunConfiguration::AddPhantomResponse,
                                            "Add the configured response to the selected phantom.");
  addPhantomResponseCommand.SetStates(G4State_PreInit);
  fAddPhantomResponseCommand = addPhantomResponseCommand.command;

  fRunMessenger
    .DeclareProperty("physicsList", fRunSettings.physicsListName,
                     "Set the Geant4 reference physics list.")
    .SetStates(G4State_PreInit);

  auto& outputModeCommand = fRunMessenger.DeclareMethod(
    "outputMode", &RunConfiguration::SetOutputMode, "Set the AtRIS output mode.");
  outputModeCommand.SetCandidates("response profile shower");
  outputModeCommand.SetStates(G4State_PreInit);

  fRunMessenger
    .DeclareProperty("outputFormat", fRunSettings.outputFileFormat,
                     "Set the Geant4 analysis output format.")
    .SetStates(G4State_PreInit);

  auto& initializeCommand =
    fRunMessenger.DeclareMethod("initialize", &RunConfiguration::Initialize,
                                "Apply the final AtRIS configuration and initialize Geant4.");
  initializeCommand.SetStates(G4State_PreInit);
  fInitializeCommand = initializeCommand.command;

  DeclareHistogramBinsProperties(fDirectionHistogramMessenger, fRunSettings.directionHistogramBins);
  DeclareHistogramBinsProperties(fPositionHistogramMessenger, fRunSettings.positionHistogramBins);
}

void RunConfiguration::SetRandomSeeds(const G4long firstSeed, const G4long secondSeed)
{
  fRunSettings.explicitSeeds = {firstSeed, secondSeed};
}

void RunConfiguration::SetOutputMode(G4String outputModeName)
{
  fRunSettings.outputMode = OutputModeValue(outputModeName);
}

void RunConfiguration::AddPhantomResponse()
{
  if (fPendingResponse.phantomStem.empty() || fPendingResponse.name.empty()
      || fPendingResponse.fileName.empty())
  {
    G4ExceptionDescription message;
    message << "Set /atris/phantom/name, /atris/phantom/response/name, and "
               "/atris/phantom/response/tableFile before "
               "/atris/phantom/response/add.";
    fAddPhantomResponseCommand->CommandFailed(message);
    return;
  }
  if (!fPhantomResponses.Add(fPendingResponse))
  {
    G4ExceptionDescription message;
    message << "Could not configure response '" << fPendingResponse.name << "' for phantom '"
            << fPendingResponse.phantomStem << "'.";
    fAddPhantomResponseCommand->CommandFailed(message);
    return;
  }
  const G4String phantomStem = fPendingResponse.phantomStem;
  fPendingResponse = {};
  fPendingResponse.phantomStem = phantomStem;
}

G4bool RunConfiguration::ReadEnergyBins()
{
  std::ifstream energyBinsFile(fRunSettings.energyBinsFileName);
  std::vector<G4double> energyBins;
  G4double energyBinEdge;
  while (energyBinsFile >> energyBinEdge)
    energyBins.push_back(energyBinEdge);
  if (!energyBinsFile.eof() || energyBins.size() < 2)
  {
    G4ExceptionDescription message;
    message << "AtRIS energy-bin file '" << fRunSettings.energyBinsFileName
            << "' must contain at least two numeric edges.";
    fInitializeCommand->CommandFailed(message);
    return false;
  }
  fRunSettings.energyBins = std::move(energyBins);
  G4cout << "### AtRIS: read " << fRunSettings.energyBins.size() << " energy-bin edges from "
         << fRunSettings.energyBinsFileName << G4endl;
  return true;
}

void RunConfiguration::DescribeOutputMode() const
{
  if (fRunSettings.outputMode == OutputMode::kProfile)
  {
    G4cout << "### AtRIS: profile mode writes histograms and interface ntuples" << G4endl;
  }
  if (fRunSettings.outputMode == OutputMode::kShower)
  {
    G4cout << "### AtRIS: shower mode writes histograms, interface, and "
              "transport-step ntuples; output may be very large"
           << G4endl;
  }
}

void RunConfiguration::PrepareGeometry()
{
  fGDMLParser.Read(fRunSettings.geometryFileName);
  std::filesystem::path inputPath(fRunSettings.geometryFileName.c_str());
  inputPath.replace_extension();
  fRunSettings.simulationInputPrefix = inputPath.string();
  fRunSettings.detectorCount = CountSensitiveDetectors(fGDMLParser);
  fRunSettings.detectorBins.clear();
  fRunSettings.detectorBins.reserve(fRunSettings.detectorCount + 1);
  constexpr G4double detectorBinHalfWidth = 0.5;
  for (G4int index = 0; index <= fRunSettings.detectorCount; ++index)
  {
    fRunSettings.detectorBins.push_back(index - detectorBinHalfWidth);
  }
  G4cout << "### AtRIS: geometry contains " << fRunSettings.detectorCount << " sensitive detectors"
         << G4endl;
}

void RunConfiguration::InstallRunComponents()
{
  fRunManager->SetUserInitialization(
    new DetectorConstruction(fGDMLParser, fRunSettings, fPhantomResponses));
  G4PhysListFactory physicsListFactory;
  G4VModularPhysicsList* const physicsList =
    physicsListFactory.GetReferencePhysList(fRunSettings.physicsListName);
  physicsList->RegisterPhysics(new G4StepLimiterPhysics());
  fRunManager->SetUserInitialization(physicsList);
  fRunManager->SetUserInitialization(new UserActionInitialization(fRunSettings, fPhantomResponses));
}

void RunConfiguration::ApplyRandomSeeds() const
{
  if (fRunSettings.explicitSeeds[0] != 0)
  {
    // CLHEP expects two seeds followed by a zero terminator.
    const std::array<G4long, 3> seeds = {
      fRunSettings.explicitSeeds[0],
      fRunSettings.explicitSeeds[1],
      0,
    };
    G4Random::setTheSeeds(seeds.data());
    G4cout << "### AtRIS: using random seeds " << fRunSettings.explicitSeeds[0] << " and "
           << fRunSettings.explicitSeeds[1] << G4endl;
  }
}

void RunConfiguration::Initialize()
{
  if (fRunSettings.outputStem.empty())
  {
    G4ExceptionDescription message;
    message << "AtRIS initialization requires outputStem.";
    fInitializeCommand->CommandFailed(message);
    return;
  }
  if (!ReadEnergyBins()) return;

  DescribeOutputMode();
  PrepareGeometry();
  InstallRunComponents();
  ApplyRandomSeeds();
  fRunManager->Initialize();
}

}  // namespace atris
