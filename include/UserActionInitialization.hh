#ifndef UserActionInitialization_hh
#define UserActionInitialization_hh

#include "G4VUserActionInitialization.hh"

namespace atris {

struct RunSettings;

class UserActionInitialization : public G4VUserActionInitialization
{
  public:
    explicit UserActionInitialization(const RunSettings& settings);
    ~UserActionInitialization() override;

    void Build() const override;
    void BuildForMaster() const override;

  private:
    const RunSettings& fSettings;
};

}  // namespace atris

#endif
