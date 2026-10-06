#ifndef UserActionInitialization_hh
#define UserActionInitialization_hh

#include "G4VUserActionInitialization.hh"

namespace atris {

class PhantomResponses;
struct RunSettings;

class UserActionInitialization : public G4VUserActionInitialization
{
  public:
    UserActionInitialization(
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~UserActionInitialization() override;

    void Build() const override;
    void BuildForMaster() const override;

  private:
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
