#include "SensitiveDetector.hh"

#include "G4AnalysisManager.hh"
#include "G4Event.hh"
#include "G4GeneralParticleSourceData.hh"
#include "G4PhysicalConstants.hh"
#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4VProcess.hh"
#include "G4ios.hh"

#include "NtupleSchema.hh"
#include "OutputMode.hh"
#include "PhantomResponseSchema.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"

#include <algorithm>
#include <cmath>

namespace atris
{

namespace
{

constexpr G4double kDefaultRadiationWeight = 1.;
constexpr G4double kProtonPionRadiationWeight = 2.;
constexpr G4double kHeavyIonRadiationWeight = 20.;
constexpr G4double kLowNeutronEnergyLimit = 1. * MeV;
constexpr G4double kHighNeutronEnergyLimit = 50. * MeV;

G4double RadiationWeight(const G4int pdg, const G4double kineticEnergy)
{
  const G4int absolutePDG = std::abs(pdg);
  if (pdg >= kFirstSupportedIonPDG) return kHeavyIonRadiationWeight;
  if (absolutePDG == kProtonPDG || absolutePDG == kNeutralPionPDG)
  {
    return kProtonPionRadiationWeight;
  }
  if (absolutePDG != kNeutronPDG) return kDefaultRadiationWeight;
  // These coefficients are the original AtRIS piecewise neutron formula.
  if (kineticEnergy <= kLowNeutronEnergyLimit)
  {
    return 3.5 + 18.2 * std::exp(-std::log(std::pow(kineticEnergy / MeV, 2.0)) / 6.0);
  }
  if (kineticEnergy <= kHighNeutronEnergyLimit)
  {
    return 5.0 + 17.0 * std::exp(-std::log(std::pow(2 * kineticEnergy / MeV, 2.0)) / 6.0);
  }
  return 2.5 + 3.25 * std::exp(-std::log(std::pow(0.04 * kineticEnergy / MeV, 2.0)) / 6.0);
}

G4double AccumulatedResponse(const PhantomResponse& response, const G4int responseIndex,
                             const G4int particlePDG, const G4double kineticEnergy)
{
  G4double value = (*response.values)[responseIndex];
  if (response.scaleByCrossingEnergy) value *= kineticEnergy / eV;
  if (response.scaleByRadiationWeight)
  {
    value *= RadiationWeight(particlePDG, kineticEnergy);
  }
  return value;
}

}  // namespace

SensitiveDetector::SensitiveDetector(const G4String& name, const RunSettings& settings,
                                     const PhantomResponses& phantomResponses)
  : G4VSensitiveDetector(name), fSettings(settings), fPhantomResponses(phantomResponses)
{}

G4bool SensitiveDetector::ProcessHits(G4Step* step, G4TouchableHistory*)
{
  G4Track* const track = step->GetTrack();
  const G4double energyDeposit = step->GetTotalEnergyDeposit();
  auto* const sourceData = G4GeneralParticleSourceData::Instance();
  auto* const source = sourceData->GetCurrentSource();
  const G4double primaryEnergy = source->GetParticleEnergy();
  G4AnalysisManager* const analysis = G4AnalysisManager::Instance();

  const G4int detectorId = std::stoi(GetName());
  const G4double nonionizingEnergyDeposit = step->GetNonIonizingEnergyDeposit();
  if (WritesStepNtuple(fSettings.outputMode))
  {
    const G4Event* const event = G4RunManager::GetRunManager()->GetCurrentEvent();
    const G4StepPoint* const prePoint = step->GetPreStepPoint();
    const G4StepPoint* const postPoint = step->GetPostStepPoint();
    const G4ThreeVector& prePosition = prePoint->GetPosition();
    const G4ThreeVector& postPosition = postPoint->GetPosition();
    const G4VProcess* const creatorProcess = track->GetCreatorProcess();
    const G4VProcess* const definingProcess = postPoint->GetProcessDefinedStep();
    const G4String creatorName = creatorProcess ? creatorProcess->GetProcessName() : "primary";
    const G4String stepProcessName = definingProcess ? definingProcess->GetProcessName() : "none";

    analysis->FillNtupleIColumn(kStepNtupleId, kStepEventId, event ? event->GetEventID() : -1);
    analysis->FillNtupleIColumn(kStepNtupleId, kStepTrackId, track->GetTrackID());
    analysis->FillNtupleIColumn(kStepNtupleId, kStepParentId, track->GetParentID());
    analysis->FillNtupleIColumn(kStepNtupleId, kStepId, track->GetCurrentStepNumber());
    analysis->FillNtupleIColumn(kStepNtupleId, kStepPDG,
                                track->GetParticleDefinition()->GetPDGEncoding());
    analysis->FillNtupleIColumn(kStepNtupleId, kStepDetectorId, detectorId);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPreXKm, prePosition.x() / km);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPreYKm, prePosition.y() / km);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPreZKm, prePosition.z() / km);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPostXKm, postPosition.x() / km);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPostYKm, postPosition.y() / km);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPostZKm, postPosition.z() / km);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPreKineticEnergyMeV,
                                prePoint->GetKineticEnergy() / MeV);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPostKineticEnergyMeV,
                                postPoint->GetKineticEnergy() / MeV);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepEnergyDepositMeV, energyDeposit / MeV);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepNonionizingEnergyDepositMeV,
                                nonionizingEnergyDeposit / MeV);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepLengthM, step->GetStepLength() / m);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepGlobalTimeNs, postPoint->GetGlobalTime() / ns);
    analysis->FillNtupleDColumn(kStepNtupleId, kStepPrimaryEnergyMeV, primaryEnergy / MeV);
    analysis->FillNtupleSColumn(kStepNtupleId, kStepCreatorProcess, creatorName);
    analysis->FillNtupleSColumn(kStepNtupleId, kStepProcess, stepProcessName);
    analysis->AddNtupleRow(kStepNtupleId);
  }
  // The first and last sensitive volumes are termination shells. Particles
  // reaching either edge have left the simulated region and are discarded.
  if (detectorId == 0)
  {
    track->SetTrackStatus(fStopAndKill);
    return false;
  }
  if (detectorId == (fSettings.detectorCount - 1))
  {
    track->SetTrackStatus(fStopAndKill);
    return false;
  }
  const G4double ionizingEnergyDeposit = energyDeposit - nonionizingEnergyDeposit;
  analysis->FillH2(kIonizingEnergyHistogramId, primaryEnergy, detectorId,
                   ionizingEnergyDeposit / MeV);
  analysis->FillH2(kTotalEnergyHistogramId, primaryEnergy, detectorId, energyDeposit / MeV);
  const G4StepPoint* const preStepPoint = step->GetPreStepPoint();
  if (preStepPoint->GetStepStatus() == fGeomBoundary)
  {
    // Score particles entering this sensitive volume through a geometry boundary.
    const G4double kineticEnergy = preStepPoint->GetKineticEnergy();
    const G4ThreeVector position = preStepPoint->GetPosition().unit();
    const G4ThreeVector direction = preStepPoint->GetMomentumDirection();
    const G4double inclination = std::acos(position * direction);
    const bool upward = inclination < halfpi;
    // A crossing belongs to the shared interface below the current detector
    // when the particle is moving upward, and above it when moving downward.
    const G4int interfaceId = detectorId - upward;
    const G4int particlePDG = track->GetParticleDefinition()->GetPDGEncoding();
    const G4int responseEnergyBin = std::max(
      0, static_cast<G4int>(std::log10(kineticEnergy / eV) / kPhantomResponseLogEnergyStep));
    const G4int particleIndex = fPhantomResponses.FindParticleIndex(particlePDG);
    if (particleIndex >= 0)
    {
      const G4int tableIndex = particleIndex * kPhantomResponseEnergyBins + responseEnergyBin;
      const auto& responses = fPhantomResponses.GetAll();
      for (std::size_t responseIndex = 0; responseIndex < responses.size(); ++responseIndex)
      {
        const PhantomResponse& response = responses[responseIndex];
        analysis->FillH2(kFirstResponseHistogramId + static_cast<G4int>(responseIndex),
                         primaryEnergy, interfaceId,
                         AccumulatedResponse(response, tableIndex, particlePDG, kineticEnergy));
      }
    }

    if (WritesInterfaceNtuple(fSettings.outputMode))
    {
      analysis->FillNtupleIColumn(kInterfaceNtupleId, kInterfacePDG, particlePDG);
      analysis->FillNtupleIColumn(kInterfaceNtupleId, kInterfaceId, interfaceId);
      analysis->FillNtupleIColumn(kInterfaceNtupleId, kInterfaceAngleDegrees,
                                  static_cast<G4int>(std::round(inclination / deg)));
      analysis->FillNtupleDColumn(kInterfaceNtupleId, kInterfaceKineticEnergyMeV,
                                  preStepPoint->GetKineticEnergy() / MeV);
      analysis->FillNtupleDColumn(kInterfaceNtupleId, kInterfacePrimaryEnergyMeV,
                                  primaryEnergy / MeV);
      analysis->AddNtupleRow(kInterfaceNtupleId);
    }
  }

  return true;
}

}  // namespace atris
