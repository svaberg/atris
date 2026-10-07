#ifndef PrimaryGeneratorAction_hh
#define PrimaryGeneratorAction_hh 1

#include "G4Types.hh"
#include "G4VUserPrimaryGeneratorAction.hh"

class G4GeneralParticleSource;
class G4Event;

namespace atris {

/**
 * Generates primary particles from Geant4's general particle source.
 *
 * The particle species, energy distribution, position, direction, and number of
 * events are configured by GPS commands in the run macro. For every generated
 * event, this action also records the sampled primary energy, source direction,
 * and source position in the analysis histograms booked by HistoManager.
 */
class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction
{
  public:
    PrimaryGeneratorAction();
    ~PrimaryGeneratorAction() override;

    /// Generates one primary vertex and records its sampled source properties.
    void GeneratePrimaries(G4Event*) override;

  private:
    G4GeneralParticleSource* const fParticleGenerator;
    const G4int fStartTime;
};

}  // namespace atris

#endif
