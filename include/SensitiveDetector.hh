#ifndef SensitiveDetector_hh
#define SensitiveDetector_hh 1

#include "G4VSensitiveDetector.hh"

class G4Step;

namespace atris
{

class PhantomResponses;
struct RunSettings;

/**
 * Converts particle transport through one sensitive volume into AtRIS output.
 *
 * Geant4 calls ProcessHits() for each step in a GDML volume marked with a
 * `SensDet` auxiliary entry. The detector accumulates ionizing and total energy
 * deposition, evaluates configured phantom-response tables when particles cross
 * layer interfaces, and writes optional interface or step ntuples according to
 * the output mode. The first and last sensitive volumes are termination shells;
 * tracks entering them are stopped after any requested step data is recorded.
 *
 * RunSettings and PhantomResponses are borrowed and must outlive this detector.
 */
class SensitiveDetector : public G4VSensitiveDetector
{
  public:
    /// Creates a detector whose name is the integer sensitive-volume ID.
    SensitiveDetector(const G4String& name, const RunSettings& settings,
                      const PhantomResponses& phantomResponses);
    ~SensitiveDetector() override = default;

    /// Records one transport step; returns false for a termination shell.
    G4bool ProcessHits(G4Step* step, G4TouchableHistory* history) override;

  private:
    /// Appends one transport step to the detailed step ntuple.
    void RecordStep(const G4Step& step, G4int detectorId, G4double primaryEnergy) const;

    /// Scores one particle entering a sensitive volume through an interface.
    void ScoreBoundaryCrossing(const G4Step& step, G4int detectorId, G4double primaryEnergy) const;

    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
