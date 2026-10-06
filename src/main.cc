#include "G4RunManager.hh"
#include "G4MTRunManager.hh"
#include "G4Threading.hh"
#include "G4UImanager.hh"
#include "G4UIcommand.hh"
#include "G4GenericMessenger.hh"
#include "G4ApplicationState.hh"
#include "G4Exception.hh"
#include "G4GDMLParser.hh"

#include "DetectorConstruction.hh"
#include "OutputMode.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"
#include "UserActionInitialization.hh"
#include "Randomize.hh"
#include "G4PhysListFactory.hh"
#include "G4StepLimiterPhysics.hh"
#include <array>
#include <vector>
#include <string>
#include <cstddef>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <fstream>
#include <sstream>

namespace {

constexpr std::size_t kChunkSeedDigits = 6;
constexpr G4double kDetectorBinHalfWidth = 0.5;
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

class RunConfiguration {
  public:
    RunConfiguration(
      G4RunManager* runManager,
      atris::RunSettings& settings,
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

    G4bool IsValid() const { return fIsValid; }

  private:
    void DeclareHistogramBinsCommand(
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

    G4bool InstallPhysicsList(const G4String& requestedPhysicsList)
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

    void InstallUserActionsIfConfigured()
    {
      if (
        fHasUserActions
        || fPhysicsList.empty()
        || !fHasConfiguredOutputMode
        || (!fHasCommandLineSettings && !fHasConfiguredOutputFormat)
      ) return;
      fRunManager->SetUserInitialization(
        new atris::UserActionInitialization(fSettings)
      );
      fHasUserActions = true;
    }

    void SetPhysicsList(G4String requestedPhysicsList)
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

    void SetOutputMode(G4String requestedOutputMode)
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

    void SetOutputFormat(G4String requestedOutputFormat)
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

    void ReportOutputMode() const
    {
      if (fOutputMode == atris::kInterfaceOutputMode) {
        G4cout << "### AtRIS: mode 0 writes histograms and interface ntuples"
               << G4endl;
      }
      if (fOutputMode == atris::kStepOutputMode) {
        G4cout << "### AtRIS: mode 1 writes histograms, interface, and "
                  "transport-step ntuples; output may be very large"
               << G4endl;
      }
    }

    void SetDirectionBins(G4int azimuthBins, G4int cosineBins)
    {
      fSettings.directionHistogramBins = {azimuthBins, cosineBins};
    }

    void SetPositionBins(G4int azimuthBins, G4int cosineBins)
    {
      fSettings.positionHistogramBins = {azimuthBins, cosineBins};
    }

    G4RunManager* const fRunManager;
    atris::RunSettings& fSettings;
    G4String fPhysicsList;
    G4int fOutputMode;
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

}  // namespace

G4int DetermineNumberOfDetectors(const G4String& fileName);

struct SimulationRun {
	G4String inputPrefix;
	G4String outputFormat;
	std::array<G4long, 3> seeds = {0, 0, 0}; // CLHEP expects two seeds followed by a zero terminator.
	G4bool hasSeeds = false;
};

SimulationRun ParseSimulationRun(const G4String& argument) {
	SimulationRun run;
	std::string path = argument.c_str();
	std::size_t pathSeparator = path.find_last_of("/\\");
	const std::size_t extensionSeparator = path.find_last_of('.');
	if (
		extensionSeparator != std::string::npos
		&& (pathSeparator == std::string::npos || extensionSeparator > pathSeparator)
	) {
		run.outputFormat = path.substr(extensionSeparator + 1);
		path.erase(extensionSeparator);
	}
	run.inputPrefix = path;
	pathSeparator = path.find_last_of("/\\");
	const std::string name = pathSeparator == std::string::npos
		                     ? path
		                     : path.substr(pathSeparator + 1);
	const std::size_t secondSeparator = name.rfind('_');
	if (secondSeparator == std::string::npos) return run;
	const std::size_t firstSeparator = name.rfind('_', secondSeparator - 1);
	if (firstSeparator == std::string::npos || firstSeparator == 0) return run;

	const std::string firstSeed = name.substr(
		firstSeparator + 1,
		secondSeparator - firstSeparator - 1
	);
	const std::string secondSeed = name.substr(secondSeparator + 1);
	if (
		firstSeed.size() != kChunkSeedDigits
		|| secondSeed.size() != kChunkSeedDigits
	) return run;
	if (firstSeed.find_first_not_of("0123456789") != std::string::npos) return run;
	if (secondSeed.find_first_not_of("0123456789") != std::string::npos) return run;

	run.inputPrefix = name.substr(0, firstSeparator);
	run.seeds[0] = std::stol(firstSeed);
	run.seeds[1] = std::stol(secondSeed);
	run.hasSeeds = true;
	return run;
}

int main(int argc,char** argv){
	const auto totalStart = std::chrono::steady_clock::now();
	if (argc == 2 && std::string(argv[1]) == "--version") {
		std::cout << "AtRIS " << ATRIS_VERSION << '\n';
		return 0;
	}
	const G4bool hasCommandLineSettings = argc == 4 || argc == 5;
	if (argc != 2 && !hasCommandLineSettings){
		G4cout << "Usage: " << argv[0] << " <simulation-name>\n"
		       << "       " << argv[0]
		       << " <physics-list> <simulation-name> <mode> [phantom-count]"
		       << G4endl;
		return 0;
	}
	G4UImanager* const uiManager = G4UImanager::GetUIpointer();
	const G4String simulationArgument = hasCommandLineSettings ? argv[2] : argv[1];
	const G4String commandLinePhysicsList = hasCommandLineSettings ? argv[1] : "";
	atris::RunSettings settings;
	if (hasCommandLineSettings) {
		settings.outputMode = std::stoi(argv[3]);
	}
	atris::PhantomResponses phantomResponses;
	if (!phantomResponses.Load()) return 1;
	settings.phantomCount = phantomResponses.GetCount();
	if (argc == 5) {
		const G4int requestedCount = std::stoi(argv[4]);
		if (requestedCount != settings.phantomCount) {
			G4cerr << "### AtRIS: phantom-count mismatch: command line specifies "
			       << requestedCount << " but found " << settings.phantomCount
			       << " staged phantom pair(s)" << G4endl;
			return 1;
		}
	}
	const SimulationRun simulation = ParseSimulationRun(simulationArgument);
	settings.outputFileName = simulationArgument;
	settings.outputFileFormat = simulation.outputFormat;
	settings.simulationInputPrefix = simulation.inputPrefix;
	settings.hasExplicitSeeds = simulation.hasSeeds;
	if (simulation.hasSeeds) {
		settings.explicitSeeds[0] = simulation.seeds[0];
		settings.explicitSeeds[1] = simulation.seeds[1];
	}
	const G4String gdmlName = simulation.inputPrefix+".gdml";
	settings.detectorCount = DetermineNumberOfDetectors(gdmlName);
	G4cout << "### AtRIS: Generating detbins with the determined number of detectors" << G4endl;
	for(int i=0;i<=settings.detectorCount;i++){
		// Integer detector IDs sit at the centers of these histogram bins.
		settings.detectorBins.push_back(i-kDetectorBinHalfWidth);
	}
	// Create the enbinsa for the histograms
	const G4String binEdgesFile = simulation.inputPrefix+".bins";
	G4double newBinEdge = 0;
	std::ifstream binEdges(binEdgesFile);
	G4int binEdgeCount = 0;
	while (binEdges >> newBinEdge){
		settings.energyBins.push_back(newBinEdge);
		++binEdgeCount;
	}
	G4cout << "### AtRIS: read " << binEdgeCount << " binedges." << G4endl;

	G4Random::setTheEngine(new CLHEP::MTwistEngine); // Choose the Random engine
	G4MTRunManager* const runManager = new G4MTRunManager;   // Instantiate the run manager
	if (simulation.hasSeeds) {
		G4Random::setTheSeeds(simulation.seeds.data());
		G4cout << "### AtRIS: using random seeds " << simulation.seeds[0]
		       << " and " << simulation.seeds[1] << G4endl;
	}
	if (std::getenv("G4FORCENUMBEROFTHREADS") == nullptr) {
		runManager->SetNumberOfThreads(G4Threading::G4GetNumberOfCores());
	}
	G4GDMLParser parser;                             //instantiate a GDML parser
	parser.Read(gdmlName);
	atris::DetectorConstruction* const detector =
		new atris::DetectorConstruction(parser, settings, phantomResponses);
	runManager->SetUserInitialization(detector);
	RunConfiguration runConfiguration(
		runManager,
		settings,
		commandLinePhysicsList,
		settings.outputMode
	);
	if (!runConfiguration.IsValid()) return -1;

	// Select the macro and execute it through Geant4's UI manager.
	G4String macroName = simulation.inputPrefix+".mac";
	if (simulation.hasSeeds) {
		const G4String chunkMacroName = simulation.inputPrefix+".chunk.mac";
		std::ifstream chunkMacro(chunkMacroName);
		if (chunkMacro.good()) macroName = chunkMacroName;
	}
	const G4String command = "/control/execute "+macroName;
	G4cout << "### AtRIS: executing macro " << macroName << G4endl;
	G4cout << "### AtRIS: Starting the simulation " << G4endl;
	const auto macroStart = std::chrono::steady_clock::now();
	const G4int commandStatus = uiManager->ApplyCommand(command);
	const auto macroEnd = std::chrono::steady_clock::now();
	const G4int workerThreads = runManager->GetNumberOfThreads();
	G4cout << "### AtRIS: simulation used " << workerThreads << " worker thread(s)" << G4endl;
	if (commandStatus == 0) {
		G4cout << "### AtRIS: the simulation has completed " << G4endl;
	} else {
		G4cerr << "### AtRIS: macro execution failed with Geant4 status " << commandStatus << G4endl;
	}
	delete runManager;
	const auto totalEnd = std::chrono::steady_clock::now();
	const double macroSeconds =
		std::chrono::duration<double>(macroEnd - macroStart).count();
	const double totalSeconds =
		std::chrono::duration<double>(totalEnd - totalStart).count();
	std::ostringstream timingOutput;
	timingOutput << std::fixed << std::setprecision(3)
		<< "### AtRIS timing: Geant4 macro wall time: " << macroSeconds
		<< " s using " << workerThreads << " worker thread(s)\n"
		<< "### AtRIS timing: setup/cleanup wall time: "
		<< totalSeconds - macroSeconds << " s\n"
		<< "### AtRIS timing: total wall time: " << totalSeconds << " s";
	G4cout << timingOutput.str() << G4endl;
	if (commandStatus == 0) {
		G4cout << "### AtRIS: Run completed successfully." << G4endl;
	} else {
		G4cerr << "### AtRIS: Run failed." << G4endl;
	}
	return commandStatus == 0 ? 0 : 1;
}

G4int DetermineNumberOfDetectors(const G4String& fileName)
{
	// Each GDML auxiliary tag marks one sensitive detector.
	G4String line;
	const G4String auxiliaryTag = "<auxiliary";
	G4String token;
	G4int detectorCount = 0;
	std::ifstream input(fileName);
	while (std::getline(input, line)) {
		std::stringstream words(line);
		while (words >> token) {
			if (token == auxiliaryTag) ++detectorCount;
			if (token == "</gdml>") return detectorCount;
		}
	}
	G4cout << "### AtRIS: number of detectors: " << detectorCount << G4endl;
	return detectorCount;
}
