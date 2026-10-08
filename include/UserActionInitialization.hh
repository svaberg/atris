#ifndef UserActionInitialization_hh
#define UserActionInitialization_hh

#include "G4VUserActionInitialization.hh"

namespace atris
{

class PhantomResponses;
struct RunSettings;

/**
 * Installs the AtRIS user actions required by Geant4 worker roles.
 *
 * BuildForMaster() installs the master RunAction responsible for merged analysis
 * output. Build() installs a worker RunAction and PrimaryGeneratorAction for
 * event generation and worker-local accumulation. Both actions borrow the
 * resolved settings and phantom-response collection held by the application.
 */
class UserActionInitialization : public G4VUserActionInitialization
{
  public:
    UserActionInitialization(const RunSettings& runSettings,
                             const PhantomResponses& phantomResponses);
    ~UserActionInitialization() override = default;

    /// Installs event-generation and run actions for a worker thread.
    void Build() const override;

    /// Installs the run action used by the master thread.
    void BuildForMaster() const override;

  private:
    const RunSettings& fRunSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
