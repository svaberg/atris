#include "RunAction.hh"
#include "G4ParticleTable.hh"
#include "G4Run.hh"
#include "globals.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "HistoManager.hh"
#include "G4AnalysisManager.hh"
#include "G4UnitsTable.hh"
#include "OutputMode.hh"
#include "RunSettings.hh"
#include <vector>
#include <cmath>
#include <fstream>
#include <sstream>
#include <iostream>


namespace atris {

RunAction::RunAction(G4bool role, const RunSettings& settings)
  : fHisto(nullptr),
    fSettings(settings)
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
  return new G4Run;
}


void RunAction::BeginOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing BeginOfRunAction" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
  analysis->SetDefaultFileType(
    fSettings.outputFileFormat.empty() ? "csv" : fSettings.outputFileFormat
  );
  if (WritesInterfaceNtuple(fSettings.outputMode)) analysis->SetNtupleMerging(true);
  fHisto = new HistoManager(fSettings);
  if (analysis->IsActive()) {
    analysis->SetFileName(fSettings.outputFileName);
    if (!analysis->OpenFile()) {
      G4ExceptionDescription message;
      message << "Cannot open analysis output '" << fSettings.outputFileName
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
}

void RunAction::EndOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing EndOfRunAction" << G4endl;
  auto* const analysis = G4AnalysisManager::Instance();
  if (analysis->IsActive()) {
    analysis->SetVerboseLevel(1);
    analysis->Write();
    analysis->CloseFile();
    G4cout << "### AtRIS: histograms written, closed. " << G4endl;
  }
}

}  // namespace atris
