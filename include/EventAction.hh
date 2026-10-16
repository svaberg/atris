#ifndef EventAction_hh
#define EventAction_hh 1

#include "G4UserEventAction.hh"
#include "globals.hh"
#include <map>
#include <tuple>

namespace atris {

class EventAction : public G4UserEventAction {
public:
	void BeginOfEventAction(const G4Event*) override;
	void EndOfEventAction(const G4Event*) override;
	void Score(G4int histogramId, G4double energy, G4double layer, G4double weight);

private:
	struct BinTotal {
		G4double energy;
		G4double layer;
		G4double weight = 0.;
	};
	// One total per output bin across every track and sensitive volume in an event.
	std::map<std::tuple<G4int, G4int, G4int>, BinTotal> fTotals;
};

}  // namespace atris

#endif
