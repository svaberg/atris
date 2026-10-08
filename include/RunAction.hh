#ifndef RunAction_hh
#define RunAction_hh 1

#include "G4UserRunAction.hh"

class G4Run;

namespace atris
{

class AnalysisOutput;
class PhantomResponses;
struct RunSettings;

/**
 * Opens, populates, and closes Geant4 analysis output for a run.
 *
 * Geant4 creates this action for the master and for each worker. At the start of
 * a run it selects the configured output backend, enables ntuple merging when
 * required, creates an AnalysisOutput, and opens the output. At the end of the run
 * it asks Geant4 to write and close that output.
 *
 * The action owns its AnalysisOutput. RunSettings and PhantomResponses are
 * borrowed and must outlive the action.
 */
class RunAction : public ::G4UserRunAction
{
  public:
    /// Creates a master action when `isMaster` is true, otherwise a worker action.
    RunAction(G4bool isMaster, const RunSettings& runSettings,
              const PhantomResponses& phantomResponses);
    ~RunAction() override;

    /// Creates the Geant4 run object used for event accumulation.
    G4Run* GenerateRun() override;

    /// Books analysis objects and opens the configured output file.
    void BeginOfRunAction(const G4Run* aRun) override;

    /// Writes and closes the configured output file.
    void EndOfRunAction(const G4Run* aRun) override;

  private:
    AnalysisOutput* fAnalysisOutput;
    const RunSettings& fRunSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
