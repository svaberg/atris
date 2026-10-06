#ifndef RunAction_hh
#define RunAction_hh 1

#include "G4UserRunAction.hh"

class G4Run;

namespace atris {

class HistoManager;
class PhantomResponses;
struct RunSettings;

class RunAction : public ::G4UserRunAction
{
  public:
    RunAction(
      G4bool role,
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~RunAction() override;

    G4Run* GenerateRun() override;
    void BeginOfRunAction(const G4Run* aRun) override;
    void EndOfRunAction(const G4Run* aRun) override;

  private:
    HistoManager* fHisto;
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
