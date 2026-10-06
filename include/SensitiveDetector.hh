#ifndef SensitiveDetector_hh
#define SensitiveDetector_hh 1

#include "G4Allocator.hh"
#include "G4THitsCollection.hh"
#include "G4ThreeVector.hh"
#include "G4UImessenger.hh"
#include "G4VHit.hh"
#include "G4VSensitiveDetector.hh"
#include "tls.hh"

#include <cstddef>
#include <vector>

class G4Step;
class G4HCofThisEvent;

namespace atris {

class SDHit;
class PhantomResponses;
struct RunSettings;


class SDHit : public G4VHit
{
  public:
    SDHit();
    ~SDHit() override;

    inline void* operator new(std::size_t);
    inline void  operator delete(void*);

    void Print() override;

    G4double fIonizingEnergy, fNonionizingEnergy;
    G4String fDetector, fParticle;
    G4int fDetectorId, fStepId;

    static G4Allocator<SDHit>* fgAllocator;
};

using SDHitsCollection = G4THitsCollection<SDHit>;

inline void* SDHit::operator new(std::size_t)
{
	if (!fgAllocator) fgAllocator = new G4Allocator<SDHit>;
	return static_cast<void*>(fgAllocator->MallocSingle());
}

inline void SDHit::operator delete(void* hit)
{
	fgAllocator->FreeSingle(static_cast<SDHit*>(hit));
}


class SensitiveDetector : public G4VSensitiveDetector, public G4UImessenger
{
  public:
    SensitiveDetector(
      const G4String& name,
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~SensitiveDetector() override;

    void Initialize(G4HCofThisEvent* hitCollection) override;
    G4bool ProcessHits(G4Step* step, G4TouchableHistory* history) override;

  private:
    SDHitsCollection* fHitsCollection;
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;

};

}  // namespace atris

#endif
