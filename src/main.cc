#include "G4RunManager.hh"
#include "G4MTRunManager.hh"
#include "G4Threading.hh"
#include "G4UImanager.hh"
#include "G4GDMLParser.hh"

#include "DetectorConstruction.hh"
#include "OutputMode.hh"
#include "PhantomResponseSchema.hh"
#include "UserActionInitialization.hh"
#include "Randomize.hh"
#include "G4PhysListFactory.hh"
#include "G4StepLimiterPhysics.hh"
#include <array>
#include <charconv>
#include <filesystem>
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
#include <map>
#include <set>
#include <sstream>

G4String outputFileName;
G4String simulationInputPrefix;
G4String physicsListName;
G4int    mode = atris::kResponseOutputMode;
G4int    numberOfDetectors = 0;
G4bool   hasExplicitSeeds = false;
std::array<G4long, 2> explicitSeeds = {0, 0};

// For holding phantom responses
G4int numberOfPhantoms;
std::vector<G4int> lightParticleResponseIndices(atris::kLightParticleLookupSize, 0);
std::map<G4int, G4int> ionResponseIndices;
std::vector<std::vector<G4double>> radiationResponses;
std::vector<std::vector<G4double>> countingResponses;

std::vector<G4double> energyBins;
std::vector<G4double> detectorBins;

namespace {

constexpr std::size_t kChunkSeedDigits = 6;
constexpr G4double kDetectorBinHalfWidth = 0.5;
constexpr std::size_t kLegacyPhysicsListSuffixLength = 4;

}  // namespace

// Functions used by main.
G4bool LoadPhantoms(G4int count);
void DetermineNumberOfDetectors(const G4String& fileName);

struct SimulationRun {
	G4String inputPrefix;
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

G4bool ParsePhantomIndex(
	const std::string& fileName,
	const std::string& prefix,
	G4int& index
) {
	const std::string suffix = ".txt";
	if (
		fileName.size() <= prefix.size() + suffix.size()
		|| fileName.compare(0, prefix.size(), prefix) != 0
		|| fileName.compare(fileName.size() - suffix.size(), suffix.size(), suffix) != 0
	) return false;

	const char* const first = fileName.data() + prefix.size();
	const char* const last = fileName.data() + fileName.size() - suffix.size();
	const auto result = std::from_chars(first, last, index);
	if (result.ec != std::errc() || result.ptr != last || index < 0) return false;

	return fileName == prefix + std::to_string(index) + suffix;
}

G4bool DiscoverPhantomCount(G4int& count)
{
	const std::string radiationPrefix = "radiation_phantom";
	const std::string countingPrefix = "counting_phantom";
	std::set<G4int> radiationIndices;
	std::set<G4int> countingIndices;
	for (const auto& entry : std::filesystem::directory_iterator(".")) {
		const std::string fileName = entry.path().filename().string();
		G4int index;
		if (ParsePhantomIndex(fileName, radiationPrefix, index)) {
			radiationIndices.insert(index);
		}
		if (ParsePhantomIndex(fileName, countingPrefix, index)) {
			countingIndices.insert(index);
		}
	}

	for (const G4int index : radiationIndices) {
		if (countingIndices.count(index) == 0) {
			G4cerr << "### AtRIS: staged phantom " << index << " is missing "
			       << countingPrefix << index << ".txt" << G4endl;
			return false;
		}
	}
	for (const G4int index : countingIndices) {
		if (radiationIndices.count(index) == 0) {
			G4cerr << "### AtRIS: staged phantom " << index << " is missing "
			       << radiationPrefix << index << ".txt" << G4endl;
			return false;
		}
	}

	G4int expectedIndex = 0;
	for (const G4int index : radiationIndices) {
		if (index != expectedIndex) {
			G4cerr << "### AtRIS: staged phantom IDs must be contiguous from 0; "
			       << "expected " << expectedIndex << " but found " << index
			       << G4endl;
			return false;
		}
		++expectedIndex;
	}
	count = expectedIndex;
	return true;
}



int main(int argc,char** argv){
	if (argc == 2 && std::string(argv[1]) == "--version") {
		std::cout << "AtRIS " << ATRIS_VERSION << '\n';
		return 0;
	}
	if (argc != 4 && argc != 5){
		G4cout << "Usage: " << argv[0]
		       << " <physics-list> <simulation-name> <mode> [phantom-count]" << G4endl;
		return 0;
	}
	const auto totalStart = std::chrono::steady_clock::now();
	mode = std::stoi(argv[3]);
	if (!DiscoverPhantomCount(numberOfPhantoms)) return 1;
	if (argc == 5) {
		const G4int requestedCount = std::stoi(argv[4]);
		if (requestedCount != numberOfPhantoms) {
			G4cerr << "### AtRIS: phantom-count mismatch: command line specifies "
			       << requestedCount << " but found " << numberOfPhantoms
			       << " staged phantom pair(s)" << G4endl;
			return 1;
		}
	}
	// The simulation name selects the geometry, energy bins, and macro inputs;
	// staged numbered files select the radiation and counting responses.
	if (!LoadPhantoms(numberOfPhantoms)) return 1;
	const SimulationRun simulation = ParseSimulationRun(argv[2]);
	outputFileName    = argv[2];
	simulationInputPrefix = simulation.inputPrefix;
	hasExplicitSeeds = simulation.hasSeeds;
	if (simulation.hasSeeds) {
		explicitSeeds[0] = simulation.seeds[0];
		explicitSeeds[1] = simulation.seeds[1];
	}
	const G4String gdmlName = simulation.inputPrefix+".gdml";
	DetermineNumberOfDetectors(gdmlName);
	G4cout << "### AtRIS: Generating detbins with the determined number of detectors" << G4endl;
	for(int i=0;i<=numberOfDetectors;i++){
		// Integer detector IDs sit at the centers of these histogram bins.
		detectorBins.push_back(i-kDetectorBinHalfWidth);
	}
	// Create the enbinsa for the histograms
	const G4String binEdgesFile = simulation.inputPrefix+".bins";
	G4double newBinEdge = 0;
	std::ifstream binEdges(binEdgesFile);
	G4int binEdgeCount = 0;
	while (binEdges >> newBinEdge){
		energyBins.push_back(newBinEdge);
		++binEdgeCount;
	}
	G4cout << "### AtRIS: read " << binEdgeCount << " binedges." << G4endl;

	// The log files could be necessary for the data analysis.
	// Therefore, we redirect them to a file. 
	G4UImanager* const uiManager = G4UImanager::GetUIpointer();
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
	atris::DetectorConstruction* const detector = new atris::DetectorConstruction(parser);
	runManager->SetUserInitialization(detector);
	const G4String physics = argv[1]; 			 //Setting up the physics list
	physicsListName = physics;
	G4PhysListFactory factory;                       // initialize physics list
	// Legacy validation also retries after removing four trailing characters.
	// The full name is still passed to Geant4, so this does not normalize input.
	const G4bool validPhysicsList = factory.IsReferencePhysList(physics)
		|| factory.IsReferencePhysList(
			physics.substr(0,physics.size()-kLegacyPhysicsListSuffixLength)
		);
	if (validPhysicsList) {
		G4VModularPhysicsList* const physicsList = factory.GetReferencePhysList(physics);
		physicsList->RegisterPhysics(new G4StepLimiterPhysics());
		runManager->SetUserInitialization(physicsList);
	} else {
		G4cout << "### AtRIS: " << physics << " is not valid! use: "<<G4endl;
		const std::vector<G4String> available = factory.AvailablePhysLists();
		for (std::size_t i = 0; i < available.size(); ++i){
			G4cout << available[i] << G4endl;
		}
		return -1;
	}
	if (mode == atris::kInterfaceOutputMode) {
		G4cout << "### AtRIS: mode 0 writes histograms and interface ntuples to "
		       << outputFileName << G4endl;
	}
	if (mode == atris::kStepOutputMode) {
		G4cout << "### AtRIS: mode 1 writes histograms, interface, and transport-step ntuples to "
		       << outputFileName << "; output may be very large" << G4endl;
	}

	atris::UserActionInitialization* const userAction = new atris::UserActionInitialization();
	runManager->SetUserInitialization(userAction);


	// Get the pointer to the user interface manager and start the batch mode
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

void DetermineNumberOfDetectors(const G4String& fileName)
{
	// Each GDML auxiliary tag marks one sensitive detector.
	G4String line;
	const G4String auxiliaryTag = "<auxiliary";
	G4String token;
	std::ifstream input(fileName);
	while (std::getline(input, line)) {
		std::stringstream words(line);
		while (words >> token) {
			if (token == auxiliaryTag) ++numberOfDetectors;
			if (token == "</gdml>") return;
		}
	}
	G4cout << "### AtRIS: number of detectors: " << numberOfDetectors << G4endl;
}

G4bool LoadPhantoms(G4int count)
{
	G4int expectedValueCount = 0;
	std::vector<G4int> expectedPDGs;
	G4String expectedHeaderName;
	G4cout << "### AtRIS: proceeding to load " << count << " phantom(s)."
	       << G4endl << std::flush;
	for (G4int phantomIndex = 0; phantomIndex < count; ++phantomIndex) {
		std::vector<G4double> radiationResponse;
		const G4String radiationPhantomName =
			"radiation_phantom" + std::to_string(phantomIndex) + ".txt";
		G4cout << "### AtRIS: loading radiation response matrix for phantom "
		       << phantomIndex << " from " << radiationPhantomName
		       << G4endl << std::flush;
		std::ifstream radiationFile(radiationPhantomName);
		if (!radiationFile.is_open()) {
			G4cerr << "### AtRIS: unable to open phantom file "
			       << radiationPhantomName << G4endl;
			return false;
		}

		G4String line;
		std::getline(radiationFile, line);
		std::stringstream header(line);
		std::vector<G4int> pdgs;
		G4int pdg;
		while (header >> pdg) pdgs.push_back(pdg);
		if (pdgs.empty()) {
			G4cerr << "### AtRIS: phantom file has an empty PDG header: "
			       << radiationPhantomName << G4endl;
			return false;
		}

		if (phantomIndex == 0) {
			expectedPDGs = pdgs;
			expectedHeaderName = radiationPhantomName;
			for (std::size_t particleIndex = 0; particleIndex < pdgs.size(); ++particleIndex) {
				pdg = pdgs[particleIndex];
				// Common particles fit the dense signed-PDG lookup. Ion PDG codes
				// are sparse and therefore use a separate map.
				if (std::abs(pdg) < atris::kLightParticlePDGLimit) {
					const G4int lookupIndex = pdg + atris::kLightParticlePDGOffset;
					G4cout << particleIndex
					       << " adding sensitivity for light particle with PDG= "
					       << pdg << " at index " << lookupIndex << G4endl;
					lightParticleResponseIndices[lookupIndex] =
						static_cast<G4int>(particleIndex);
				} else {
					G4cout << "Added sensitivity for heavy particle with PDG= "
					       << pdg << " under the index j=" << particleIndex << G4endl;
					ionResponseIndices[pdg] = static_cast<G4int>(particleIndex);
				}
			}
			G4cout << "total" << pdgs.size() << G4endl;
			expectedValueCount = static_cast<G4int>(
				atris::kPhantomResponseEnergyBins * pdgs.size()
			);
			G4cout << " ### AtRIS: nricrubins is:"
			       << atris::kPhantomResponseEnergyBins << " and nrpdgs is : "
			       << pdgs.size() << ". We are expecting: " << expectedValueCount
			       << " data points in the phantom file." << G4endl;
		} else if (pdgs != expectedPDGs) {
			G4cerr << "### AtRIS: PDG header mismatch: " << radiationPhantomName
			       << " does not match " << expectedHeaderName << G4endl;
			return false;
		}

		G4double responseValue;
		G4int valueCount = 0;
		while (std::getline(radiationFile, line)) {
			std::stringstream values(line);
			while (values >> responseValue) {
				radiationResponse.push_back(responseValue);
				++valueCount;
			}
		}
		G4cout << "### AtRIS: found " << valueCount << " out of expected "
		       << expectedValueCount << G4endl;
		if (valueCount != expectedValueCount) {
			G4cout << " ### AtRIS: check phantoms file for empty ending characters!"
			       << G4endl;
		}
		radiationResponses.push_back(radiationResponse);

		std::vector<G4double> countingResponse;
		const G4String countingPhantomName =
			"counting_phantom" + std::to_string(phantomIndex) + ".txt";
		G4cout << "### AtRIS: loading counting response matrix for phantom "
		       << phantomIndex << " from " << countingPhantomName
		       << G4endl << std::flush;
		valueCount = 0;
		std::ifstream countingFile(countingPhantomName);
		if (!countingFile.is_open()) {
			G4cerr << "### AtRIS: unable to open phantom file "
			       << countingPhantomName << G4endl;
			return false;
		}
		std::getline(countingFile, line);
		std::stringstream countingHeader(line);
		pdgs.clear();
		while (countingHeader >> pdg) pdgs.push_back(pdg);
		if (pdgs != expectedPDGs) {
			G4cerr << "### AtRIS: PDG header mismatch: " << countingPhantomName
			       << " does not match " << expectedHeaderName << G4endl;
			return false;
		}
		while (std::getline(countingFile, line)) {
			std::stringstream values(line);
			while (values >> responseValue) {
				countingResponse.push_back(responseValue);
				++valueCount;
			}
		}
		G4cout << "### AtRIS: found " << valueCount << " out of expected "
		       << expectedValueCount << G4endl;
		if (valueCount != expectedValueCount) {
			G4cout << " ### AtRIS: check phantoms file for empty ending characters!"
			       << G4endl;
		}
		countingResponses.push_back(countingResponse);
	}
	return true;
}
