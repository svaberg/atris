#include "RunAction.hh"

#include "G4AnalysisManager.hh"
#include "G4Exception.hh"
#include "G4Run.hh"

#include "AnalysisOutput.hh"
#include "OutputMode.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"

namespace atris
{

RunAction::RunAction(G4bool isMaster, const RunSettings& runSettings,
                     const PhantomResponses& phantomResponses)
  : fAnalysisOutput(nullptr), fRunSettings(runSettings), fPhantomResponses(phantomResponses)
{
  SetMaster(isMaster);
}

RunAction::~RunAction()
{
  if (IsMaster())
  {
    G4debug << "### AtRIS: now writing out histograms... " << G4endl;
    G4debug << "=== MASTER: " << IsMaster() << G4endl;
  }
  delete fAnalysisOutput;
}

G4Run* RunAction::GenerateRun()
{
  G4debug << "### AtRIS: executing GenerateRun" << G4endl;
  G4debug << "=== MASTER: " << IsMaster() << G4endl;
  return new G4Run;
}

void RunAction::BeginOfRunAction(const G4Run*)
{
  G4debug << "### AtRIS: executing BeginOfRunAction" << G4endl;
  G4debug << "=== MASTER: " << IsMaster() << G4endl;
  G4AnalysisManager* const analysisManager = G4AnalysisManager::Instance();
  analysisManager->SetDefaultFileType(fRunSettings.outputFileFormat);
  if (fRunSettings.outputFileFormat == "root" || WritesInterfaceNtuple(fRunSettings.outputMode))
  {
    analysisManager->SetNtupleMerging(true);
  }
  fAnalysisOutput = new AnalysisOutput(fRunSettings, fPhantomResponses);
  if (analysisManager->IsActive())
  {
    analysisManager->SetFileName(fRunSettings.outputStem);
    if (!analysisManager->OpenFile())
    {
      G4ExceptionDescription message;
      message << "Cannot open analysis output '" << fRunSettings.outputStem
              << "'. Its filename extension may not be supported by this "
                 "Geant4 installation.";
      G4Exception("atris::RunAction::BeginOfRunAction()", "AtRISOutput001", FatalException,
                  message);
    }
    fAnalysisOutput->FillMetadata();
  }
}

void RunAction::EndOfRunAction(const G4Run*)
{
  G4debug << "### AtRIS: executing EndOfRunAction" << G4endl;
  auto* const analysisManager = G4AnalysisManager::Instance();
  if (analysisManager->IsActive())
  {
    analysisManager->SetVerboseLevel(1);
    analysisManager->Write();
    analysisManager->CloseFile();
    G4cout << "### AtRIS: histograms written, closed. " << G4endl;
  }
}

}  // namespace atris
