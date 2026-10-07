#include "RunAction.hh"

#include "G4AnalysisManager.hh"
#include "G4Exception.hh"
#include "G4Run.hh"

#include "HistoManager.hh"
#include "OutputMode.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"

namespace atris
{

RunAction::RunAction(G4bool isMaster, const RunSettings& settings,
                     const PhantomResponses& phantomResponses)
  : fHisto(nullptr), fSettings(settings), fPhantomResponses(phantomResponses)
{
  SetMaster(isMaster);
}

RunAction::~RunAction()
{
  if (IsMaster())
  {
    G4cout << "### AtRIS: now writing out histograms... " << G4endl;
    G4cout << "=== MASTER: " << IsMaster() << G4endl;
  }
  delete fHisto;
}

G4Run* RunAction::GenerateRun()
{
  G4cout << "### AtRIS: executing GenerateRun" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  return new G4Run;
}

void RunAction::BeginOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing BeginOfRunAction" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
  analysis->SetDefaultFileType(fSettings.outputFileFormat);
  if (fSettings.outputFileFormat == "root" || WritesInterfaceNtuple(fSettings.outputMode))
  {
    analysis->SetNtupleMerging(true);
  }
  fHisto = new HistoManager(fSettings, fPhantomResponses);
  if (analysis->IsActive())
  {
    analysis->SetFileName(fSettings.outputStem);
    if (!analysis->OpenFile())
    {
      G4ExceptionDescription message;
      message << "Cannot open analysis output '" << fSettings.outputStem
              << "'. Its filename extension may not be supported by this "
                 "Geant4 installation.";
      G4Exception("atris::RunAction::BeginOfRunAction()", "AtRISOutput001", FatalException,
                  message);
    }
    fHisto->FillMetadata();
  }
}

void RunAction::EndOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing EndOfRunAction" << G4endl;
  auto* const analysis = G4AnalysisManager::Instance();
  if (analysis->IsActive())
  {
    analysis->SetVerboseLevel(1);
    analysis->Write();
    analysis->CloseFile();
    G4cout << "### AtRIS: histograms written, closed. " << G4endl;
  }
}

}  // namespace atris
