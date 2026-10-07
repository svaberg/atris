#include "PhantomResponses.hh"
#include "RunConfiguration.hh"
#include "RunSettings.hh"

#include "G4GDMLParser.hh"
#include "G4MTRunManager.hh"
#include "G4Threading.hh"
#include "G4UImanager.hh"
#include "Randomize.hh"

#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

int main(int argc,char** argv){
	const auto totalStart = std::chrono::steady_clock::now();
	if (argc == 2 && std::string(argv[1]) == "--version") {
		std::cout << "AtRIS " << ATRIS_VERSION << '\n';
		return 0;
	}
	if (argc != 2){
		G4cerr << "Usage: " << argv[0] << " <macro-file>" << G4endl;
		return 1;
	}
	const G4String macroName = argv[1];
	atris::RunSettings settings;
	atris::PhantomResponses phantomResponses;

	G4Random::setTheEngine(new CLHEP::MTwistEngine); // Choose the Random engine
	G4MTRunManager* const runManager = new G4MTRunManager;   // Instantiate the run manager
	if (std::getenv("G4FORCENUMBEROFTHREADS") == nullptr) {
		runManager->SetNumberOfThreads(G4Threading::G4GetNumberOfCores());
	}
	G4GDMLParser parser;                             //instantiate a GDML parser
	atris::RunConfiguration runConfiguration(
		runManager,
		settings,
		parser,
		phantomResponses
	);

	// Execute the explicitly selected run macro through Geant4's UI manager.
	const G4String command = "/control/execute "+macroName;
	G4cout << "### AtRIS: executing macro " << macroName << G4endl;
	G4cout << "### AtRIS: Starting the simulation " << G4endl;
	const auto macroStart = std::chrono::steady_clock::now();
	const G4int commandStatus = G4UImanager::GetUIpointer()->ApplyCommand(command);
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
