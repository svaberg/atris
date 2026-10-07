#ifndef RunAction_hh
#define RunAction_hh 1

#include "G4UserRunAction.hh"

class G4Run;

namespace atris
{

class HistoManager;
class PhantomResponses;
struct RunSettings;

/**
 * Opens, populates, and closes Geant4 analysis output for a run.
 *
 * Geant4 creates this action for the master and for each worker. At the start of
 * a run it selects the configured output backend, enables ntuple merging when
 * required, creates a HistoManager, and opens the output. At the end of the run
 * it asks Geant4 to write and close that output.
 *
 * The action owns its HistoManager. RunSettings and PhantomResponses are
 * borrowed and must outlive the action.
 */
class RunAction : public ::G4UserRunAction
{
  public:
    /// Creates a master action when `role` is true, otherwise a worker action.
    RunAction(G4bool role, const RunSettings& settings, const PhantomResponses& phantomResponses);
    ~RunAction() override;

    /// Creates the Geant4 run object used for event accumulation.
    G4Run* GenerateRun() override;

    /// Books analysis objects and opens the configured output file.
    void BeginOfRunAction(const G4Run* aRun) override;

    /// Writes and closes the configured output file.
    void EndOfRunAction(const G4Run* aRun) override;

  private:
    HistoManager* fHisto;
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
