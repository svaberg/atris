#include "RunAction.hh"
#include "G4ParticleTable.hh"
#include "G4Run.hh"
#include "globals.hh"
#include "G4RunManager.hh"
#include "HistoManager.hh"
#include "G4AnalysisManager.hh"
#include "OutputMode.hh"
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdlib>


extern G4String outputFileName;                       // from src/main.cc
extern G4int mode;
extern std::chrono::steady_clock::time_point startupStart;

namespace atris {

namespace {

std::chrono::duration<double> runTimeLimit{0};
using Clock = std::chrono::steady_clock;
Clock::time_point runStart;
thread_local Clock::time_point workerStart;
std::atomic<G4bool> timeLimitReached{false};

class TimedRun final : public G4Run
{
  public:
    void RecordEvent(const G4Event* event) override
    {
      G4Run::RecordEvent(event);
      if (runTimeLimit.count() == 0 || Clock::now() - runStart < runTimeLimit) return;
      timeLimitReached.store(true);
      // This worker has scored a complete event; stop its own event loop.
      G4RunManager::GetRunManager()->AbortRun(true);
    }
};

}  // namespace

RunAction::RunAction(G4bool role)
  : fHisto(nullptr)
{
  SetMaster(role);

  if (!(G4ParticleTable::GetParticleTable()->GetReadiness()))
  {
    const G4String msg = " You are instantiating RunAction BEFORE your G4VUserPhysicsList \n";
    G4Exception("atris::RunAction::RunAction()", "Run0041", FatalException, msg);
  }
}


RunAction::~RunAction()
{
  if (IsMaster()) {
    G4cout << "### AtRIS: now writing out histograms... " << G4endl;
    G4cout << "=== MASTER: " << IsMaster() << G4endl;
    // At this point we implement the scaling according to mass, volume, surface area
  }
  delete fHisto;
}

G4Run* RunAction::GenerateRun()
{
  G4cout << "### AtRIS: executing GenerateRun" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  return new TimedRun;
}


void RunAction::BeginOfRunAction(const G4Run*)
{
  if (IsMaster()) {
    timeLimitReached.store(false);
    runTimeLimit = std::chrono::duration<double>{0};
    if (const char* value = std::getenv("ATRIS_TIME_LIMIT")) {
      char* end = nullptr;
      const double seconds = std::strtod(value, &end);
      if (end == value || *end != '\0' || !std::isfinite(seconds) || seconds <= 0) {
        G4Exception("atris::RunAction::BeginOfRunAction()", "AtRISTimeLimit001",
                    FatalException, "ATRIS_TIME_LIMIT must be a finite positive number of seconds.");
      }
      runTimeLimit = std::chrono::duration<double>{seconds};
    }
  }
  G4cout << "### AtRIS: executing BeginOfRunAction" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
  analysis->SetDefaultFileType(mode == kPhantomOutputMode ? "root" : "csv");
  if (WritesMetadataNtuple(mode)) analysis->SetNtupleMerging(true);
  fHisto = new HistoManager();
  if (analysis->IsActive()) {
    analysis->SetFileName(outputFileName);
    if (!analysis->OpenFile()) {
      G4ExceptionDescription message;
      message << "Cannot open analysis output '" << outputFileName
              << "'. Its filename extension may not be supported by this "
                 "Geant4 installation.";
      G4Exception(
        "atris::RunAction::BeginOfRunAction()",
        "AtRISOutput001",
        FatalException,
        message
      );
    }
    fHisto->FillMetadata();
  }
  // Geant4 releases workers after the master's run initialization completes.
  if (IsMaster()) runStart = Clock::now();
  if (!IsMaster()) {
    workerStart = Clock::now();
    G4cout << "### AtRIS timing: Elapsed before worker run: "
           << std::chrono::duration<double>(workerStart - startupStart).count()
           << " s" << G4endl;
  }
}

void RunAction::EndOfRunAction(const G4Run* run)
{
  // Geant4 merges the G4Run before this callback; histogram merging follows below.
  if (!IsMaster()) {
    G4cout << "### AtRIS timing: Worker run before histogram merging took "
           << std::chrono::duration<double>(Clock::now() - workerStart).count()
           << " s" << G4endl;
  }
  if (IsMaster()) {
    G4cout << "### AtRIS run: completed " << run->GetNumberOfEvent()
           << " of " << run->GetNumberOfEventToBeProcessed() << " requested events; "
           << (timeLimitReached.load() ? "time limit reached" : "event limit reached")
           << "; event-loop wall time: " << std::chrono::duration<double>(Clock::now() - runStart).count()
           << " s; time limit: " << runTimeLimit.count() << " s (0 means unset)" << G4endl;
  }
  G4cout << "### AtRIS: executing EndOfRunAction" << G4endl;
  auto* const analysis = G4AnalysisManager::Instance();
  if (analysis->IsActive()) {
    analysis->SetVerboseLevel(1);
    const auto outputStart = Clock::now();
    analysis->Write();
    analysis->CloseFile();
    const auto outputEnd = Clock::now();
    G4cout << "### AtRIS: histograms written, closed. " << G4endl;
    G4cout << "### AtRIS timing: "
           << (IsMaster() ? "Writing histograms took " : "Merging histograms and closing took ")
           << std::chrono::duration<double>(outputEnd - outputStart).count()
           << " s" << G4endl;
  }
}

}  // namespace atris
