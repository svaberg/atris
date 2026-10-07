#include "PhantomResponses.hh"
#include "RunConfiguration.hh"
#include "RunSettings.hh"

#include "G4GDMLParser.hh"
#include "G4MTRunManager.hh"
#include "G4Threading.hh"
#include "G4UIcommandStatus.hh"
#include "G4UImanager.hh"
#include "Randomize.hh"

#include <chrono>
#include <cstdlib>
#include <iomanip>

int main(int argc,char** argv){
	const auto totalStart = std::chrono::steady_clock::now();
	if (argc == 2 && G4String(argv[1]) == "--version") {
		G4cout << "AtRIS " << ATRIS_VERSION << G4endl;
		return 0;
	}
	if (argc != 2){
		G4cerr << "Usage: " << argv[0] << " <macro-file>" << G4endl;
		return 1;
	}
	const G4String macroName = argv[1];
	atris::RunSettings settings;
	atris::PhantomResponses phantomResponses;

	// Set the master random engine before the run manager captures it for workers.
	G4Random::setTheEngine(new CLHEP::MTwistEngine);
	G4MTRunManager* const runManager = new G4MTRunManager;
	// Respect an explicit thread override; otherwise use all available cores.
	if (std::getenv("G4FORCENUMBEROFTHREADS") == nullptr) {
		runManager->SetNumberOfThreads(G4Threading::G4GetNumberOfCores());
	}
	G4GDMLParser parser;
	// Keep the command messengers and their backing state alive for the macro.
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
	if (commandStatus == fCommandSucceeded) {
		G4cout << "### AtRIS: the simulation has completed " << G4endl;
	} else {
		G4cerr << "### AtRIS: macro execution failed with Geant4 status " << commandStatus << G4endl;
	}
	// Include Geant4 teardown in the total time, but not in the macro time.
	delete runManager;
	const auto totalEnd = std::chrono::steady_clock::now();
	const double macroSeconds =
		std::chrono::duration<double>(macroEnd - macroStart).count();
	const double totalSeconds =
		std::chrono::duration<double>(totalEnd - totalStart).count();
	G4cout << std::fixed << std::setprecision(3)
		<< "### AtRIS timing: Geant4 macro wall time: " << macroSeconds
		<< " s using " << workerThreads << " worker thread(s)\n"
		<< "### AtRIS timing: setup/cleanup wall time: "
		<< totalSeconds - macroSeconds << " s\n"
		<< "### AtRIS timing: total wall time: " << totalSeconds << " s"
		<< G4endl;
	if (commandStatus == fCommandSucceeded) {
		G4cout << "### AtRIS: Run completed successfully." << G4endl;
	} else {
		G4cerr << "### AtRIS: Run failed." << G4endl;
	}
	// Preserve the detailed Geant4 status above and expose a conventional exit code.
	return commandStatus == fCommandSucceeded ? EXIT_SUCCESS : EXIT_FAILURE;
}
