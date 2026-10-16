#include "EventAction.hh"
#include "G4AnalysisManager.hh"
#include "G4SystemOfUnits.hh"

namespace atris {

void EventAction::BeginOfEventAction(const G4Event*)
{
	fTotals.clear();
}

void EventAction::Score(
	G4int histogramId, G4double energy, G4double layer, G4double weight)
{
	auto* const analysis = G4AnalysisManager::Instance();
	if (!analysis->FillH2(histogramId, energy, layer, weight) || weight == 0.) return;
	const auto* const histogram = analysis->GetH2(histogramId);
	const auto key = std::make_tuple(histogramId,
		histogram->axis_x().coord_to_index(energy/MeV),
		histogram->axis_y().coord_to_index(layer));
	auto position = fTotals.try_emplace(key, BinTotal{energy, layer}).first;
	position->second.weight += weight;
}

void EventAction::EndOfEventAction(const G4Event*)
{
	auto* const analysis = G4AnalysisManager::Instance();
	for (const auto& [key, total] : fTotals) {
		const G4int id = analysis->GetH2Id(
			analysis->GetH2Name(std::get<0>(key)) + ".primary");
		// Sumw2 now squares the whole primary's contribution, not individual steps.
		// Zero totals need no fill; h1.1 supplies N, including zero-score primaries.
		analysis->FillH2(id, total.energy, total.layer, total.weight);
	}
}

}  // namespace atris
