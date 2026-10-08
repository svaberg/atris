#include "PrimaryGeneratorAction.hh"

#include "G4AnalysisManager.hh"
#include "G4Event.hh"
#include "G4GeneralParticleSource.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"

#include <ctime>

namespace atris
{

namespace
{

constexpr G4int kProgressEventInterval = 100;

// These IDs match the H1 and H2 creation order in AnalysisOutput::BookHistograms().
constexpr G4int kPrimaryEnergyHistogramId = 0;
constexpr G4int kSourceDirectionHistogramId = 0;
constexpr G4int kSourcePositionHistogramId = 1;

}  // namespace

PrimaryGeneratorAction::PrimaryGeneratorAction()
  : fParticleGenerator(new G4GeneralParticleSource),
    fStartTime(static_cast<G4int>(std::time(nullptr)))
{
  G4debug << "### AtRIS: Created the particle gun." << G4endl;
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
  delete fParticleGenerator;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* anEvent)
{
  G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
  fParticleGenerator->GeneratePrimaryVertex(anEvent);

  const G4int current = anEvent->GetEventID();
  if (current % kProgressEventInterval == 0)
  {
    if (current != 0)
    {
      const G4int elapsed = static_cast<G4int>(std::time(nullptr)) - fStartTime;
      const G4double speed = static_cast<G4double>(current) / static_cast<G4double>(elapsed);
      G4cout << "Processing event: " << current << ", " << elapsed
             << " seconds have passed. We are processing " << speed << " primaries per second."
             << G4endl;
    }
    else
    {
      G4cout << "Starting primary particle generation" << G4endl;
    }
  }
  const G4ThreeVector direction = fParticleGenerator->GetParticleMomentumDirection();
  const G4double directionTheta = direction.theta();
  G4double directionPhi = direction.phi();
  if (directionPhi < 0.) directionPhi += twopi;
  const G4double directionCosine = std::cos(directionTheta);

  const G4double primaryVertexEnergy = fParticleGenerator->GetParticleEnergy();

  const G4ThreeVector position = fParticleGenerator->GetParticlePosition();
  const G4double positionTheta = position.theta();
  G4double positionPhi = position.phi();
  if (positionPhi < 0.) positionPhi += twopi;
  const G4double positionCosine = std::cos(positionTheta);

  // Unit weights preserve per-energy primary counts in CSV and ROOT output.
  analysis->FillH1(kPrimaryEnergyHistogramId, primaryVertexEnergy);
  analysis->FillH2(kSourceDirectionHistogramId, directionPhi, directionCosine);
  analysis->FillH2(kSourcePositionHistogramId, positionPhi, positionCosine);
}

}  // namespace atris
