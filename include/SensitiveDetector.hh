#ifndef SensitiveDetector_hh
#define SensitiveDetector_hh 1

#include "G4UImessenger.hh"
#include "G4VSensitiveDetector.hh"

class G4Step;

namespace atris {

class PhantomResponses;
struct RunSettings;

class SensitiveDetector : public G4VSensitiveDetector, public G4UImessenger
{
  public:
    SensitiveDetector(
      const G4String& name,
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~SensitiveDetector() override;

    G4bool ProcessHits(G4Step* step, G4TouchableHistory* history) override;

  private:
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;

};

}  // namespace atris

#endif
