#include "SensitiveDetector.hh"
#include "G4UnitsTable.hh"
#include "G4VVisManager.hh"
#include "G4Circle.hh"
#include "G4Colour.hh"
#include "G4VisAttributes.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4HCofThisEvent.hh"
#include "G4Event.hh"
#include "G4Step.hh"
#include "G4ThreeVector.hh"
#include "G4SDManager.hh"
#include "G4ios.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "DetectorConstruction.hh"
#include "G4UIcmdWithAString.hh"
#include "G4Run.hh"
#include "G4AnalysisManager.hh"
#include "G4PhysicalConstants.hh"
#include "NtupleSchema.hh"
#include "OutputMode.hh"
#include "PhantomResponseSchema.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunSettings.hh"
#include "G4GeneralParticleSourceData.hh"
#include "G4VProcess.hh"
#include <algorithm>
#include <cmath>
#include <map>
#include <vector>
extern std::vector<G4int> lightParticleResponseIndices;
extern std::vector<std::vector<G4double>> radiationResponses;
extern std::vector<std::vector<G4double>> countingResponses;
extern std::map<G4int, G4int> ionResponseIndices;

namespace atris {

namespace {

constexpr G4double kDefaultRadiationWeight = 1.;
constexpr G4double kProtonPionRadiationWeight = 2.;
constexpr G4double kHeavyIonRadiationWeight = 20.;
constexpr G4double kLowNeutronEnergyLimit = 1.*MeV;
constexpr G4double kHighNeutronEnergyLimit = 50.*MeV;

}  // namespace

G4Allocator<SDHit>* SDHit::fgAllocator = nullptr;


SDHit::SDHit()
	: G4VHit()
{}

SDHit::~SDHit() {}

void SDHit::Print() {}


SensitiveDetector::SensitiveDetector(
	const G4String& name,
	const RunSettings& settings
)
	: G4VSensitiveDetector(name),
	fHitsCollection(nullptr),
	fSettings(settings)
{
	collectionName.insert(name);
}

SensitiveDetector::~SensitiveDetector()
{}

void SensitiveDetector::Initialize(G4HCofThisEvent* hce){
	// Create hits collection
	fHitsCollection	= new SDHitsCollection(SensitiveDetectorName, collectionName[0]);
	// Add this collection in hce
	const G4int hitsCollectionId =
		G4SDManager::GetSDMpointer()->GetCollectionID(collectionName[0]);
	hce->AddHitsCollection(hitsCollectionId, fHitsCollection);
}

G4bool SensitiveDetector::ProcessHits(G4Step* step, G4TouchableHistory*){
	G4Track* const track = step->GetTrack();
	const G4double energyDeposit = step->GetTotalEnergyDeposit();
	auto* const sourceData = G4GeneralParticleSourceData::Instance();
	auto* const source = sourceData->GetCurrentSource();
	const G4double primaryEnergy = source->GetParticleEnergy();
	G4AnalysisManager* const analysis = G4AnalysisManager::Instance();

	const G4int detectorId = std::stoi(this->GetName());
	const G4double nonionizingEnergyDeposit = step->GetNonIonizingEnergyDeposit();
	if (WritesStepNtuple(fSettings.outputMode)) {
		const G4Event* const event = G4RunManager::GetRunManager()->GetCurrentEvent();
		const G4StepPoint* const prePoint = step->GetPreStepPoint();
		const G4StepPoint* const postPoint = step->GetPostStepPoint();
		const G4ThreeVector& prePosition = prePoint->GetPosition();
		const G4ThreeVector& postPosition = postPoint->GetPosition();
		const G4VProcess* const creatorProcess = track->GetCreatorProcess();
		const G4VProcess* const definingProcess = postPoint->GetProcessDefinedStep();
		const G4String creatorName = creatorProcess
			? creatorProcess->GetProcessName()
			: "primary";
		const G4String stepProcessName = definingProcess
			? definingProcess->GetProcessName()
			: "none";

		analysis->FillNtupleIColumn(
			kStepNtupleId,
			kStepEventId,
			event ? event->GetEventID() : -1
		);
		analysis->FillNtupleIColumn(kStepNtupleId, kStepTrackId, track->GetTrackID());
		analysis->FillNtupleIColumn(kStepNtupleId, kStepParentId, track->GetParentID());
		analysis->FillNtupleIColumn(
			kStepNtupleId,
			kStepId,
			track->GetCurrentStepNumber()
		);
		analysis->FillNtupleIColumn(
			kStepNtupleId,
			kStepPDG,
			track->GetParticleDefinition()->GetPDGEncoding()
		);
		analysis->FillNtupleIColumn(kStepNtupleId, kStepDetectorId, detectorId);
		analysis->FillNtupleDColumn(kStepNtupleId, kStepPreXKm, prePosition.x()/km);
		analysis->FillNtupleDColumn(kStepNtupleId, kStepPreYKm, prePosition.y()/km);
		analysis->FillNtupleDColumn(kStepNtupleId, kStepPreZKm, prePosition.z()/km);
		analysis->FillNtupleDColumn(kStepNtupleId, kStepPostXKm, postPosition.x()/km);
		analysis->FillNtupleDColumn(kStepNtupleId, kStepPostYKm, postPosition.y()/km);
		analysis->FillNtupleDColumn(kStepNtupleId, kStepPostZKm, postPosition.z()/km);
		analysis->FillNtupleDColumn(
			kStepNtupleId,
			kStepPreKineticEnergyMeV,
			prePoint->GetKineticEnergy()/MeV
		);
		analysis->FillNtupleDColumn(
			kStepNtupleId,
			kStepPostKineticEnergyMeV,
			postPoint->GetKineticEnergy()/MeV
		);
		analysis->FillNtupleDColumn(
			kStepNtupleId, kStepEnergyDepositMeV, energyDeposit/MeV
		);
		analysis->FillNtupleDColumn(
			kStepNtupleId,
			kStepNonionizingEnergyDepositMeV,
			nonionizingEnergyDeposit/MeV
		);
		analysis->FillNtupleDColumn(
			kStepNtupleId,
			kStepLengthM,
			step->GetStepLength()/m
		);
		analysis->FillNtupleDColumn(
			kStepNtupleId,
			kStepGlobalTimeNs,
			postPoint->GetGlobalTime()/ns
		);
		analysis->FillNtupleDColumn(
			kStepNtupleId, kStepPrimaryEnergyMeV, primaryEnergy/MeV
		);
		analysis->FillNtupleSColumn(kStepNtupleId, kStepCreatorProcess, creatorName);
		analysis->FillNtupleSColumn(kStepNtupleId, kStepProcess, stepProcessName);
		analysis->AddNtupleRow(kStepNtupleId);
	}
	// The first and last sensitive volumes are termination shells. Particles
	// reaching either edge have left the simulated region and are discarded.
	if (detectorId == 0){
		track->SetTrackStatus(fStopAndKill);
		return false;
	}
	if (detectorId == (fSettings.detectorCount-1)){
		track->SetTrackStatus(fStopAndKill);
		return false;
	}
	const G4double ionizingEnergyDeposit = energyDeposit - nonionizingEnergyDeposit;
	analysis->FillH2(
		kIonizingEnergyHistogramId,
		primaryEnergy,
		detectorId,
		ionizingEnergyDeposit/MeV
	);
	analysis->FillH2(
		kTotalEnergyHistogramId,
		primaryEnergy,
		detectorId,
		energyDeposit/MeV
	);
	//before the step, the particle should have been at the boundary. 
	const G4StepPoint* const preStepPoint = step->GetPreStepPoint();
	if (preStepPoint->GetStepStatus() == fGeomBoundary){
		//Let's check which sdid we have:
		const G4double kineticEnergy = preStepPoint->GetKineticEnergy();
		const G4ThreeVector position = preStepPoint->GetPosition().unit();
		const G4ThreeVector direction = preStepPoint->GetMomentumDirection();
		const G4double inclination = std::acos(position*direction);
		const bool upward = inclination < halfpi;
		// A crossing belongs to the shared interface below the current detector
		// when the particle is moving upward, and above it when moving downward.
		const G4int interfaceId = detectorId - upward;
		const G4int particlePDG = track->GetParticleDefinition()->GetPDGEncoding();
		const G4int absolutePDG = std::abs(particlePDG);
		const G4int responseEnergyBin = std::max(
			0,
			static_cast<G4int>(
				std::log10(kineticEnergy/eV) / kPhantomResponseLogEnergyStep
			)
		);
		if (absolutePDG < kLightParticlePDGLimit) {
			const G4int lookupIndex = particlePDG + kLightParticlePDGOffset;
			// Zero is both the first response-table row and the legacy "not found"
			// sentinel. Supplied tables place photons first, so include them explicitly.
			const bool hasResponse =
				lightParticleResponseIndices[lookupIndex] || particlePDG == kPhotonPDG;
			if (hasResponse) {
				const G4int responseIndex =
					lightParticleResponseIndices[lookupIndex]
					* kPhantomResponseEnergyBins + responseEnergyBin;
				// Radiation weighting is 1 by default, 2 for protons and neutral
				// pions, and 20 for heavy ions. The numerical coefficients below
				// are the original AtRIS piecewise neutron radiation-weighting formula.
				G4double radiationWeight = kDefaultRadiationWeight;
				if (absolutePDG == kProtonPDG || absolutePDG == kNeutralPionPDG) {
					radiationWeight = kProtonPionRadiationWeight;
				}
				if (absolutePDG == kNeutronPDG) {
					if (kineticEnergy <= kLowNeutronEnergyLimit) {
						radiationWeight = 3.5 + 18.2*std::exp(-std::log(std::pow(kineticEnergy/MeV,2.0))/6.0) ;
					} else if (kineticEnergy <= kHighNeutronEnergyLimit) {
						radiationWeight = 5.0 + 17.0*std::exp(-std::log(std::pow(2*kineticEnergy/MeV,2.0))/6.0) ;
					} else if (kineticEnergy > kHighNeutronEnergyLimit) {
						radiationWeight = 2.5 + 3.25*std::exp(-std::log(std::pow(0.04*kineticEnergy/MeV,2.0))/6.0) ;
					}
				}
				for (G4int phantomIndex = 0;
				     phantomIndex < fSettings.phantomCount;
				     ++phantomIndex) {
					const G4int offset = kFirstPhantomHistogramId
						+ kPhantomHistogramsPerPhantom*phantomIndex;
					analysis->FillH2(
						offset + kPhantomDoseHistogramOffset,
						primaryEnergy, interfaceId,
						radiationResponses[phantomIndex][responseIndex]
							* kineticEnergy/eV
					);
					analysis->FillH2(
						offset + kPhantomEquivalentDoseHistogramOffset,
						primaryEnergy, interfaceId,
						radiationResponses[phantomIndex][responseIndex]
							* kineticEnergy/eV * radiationWeight
					);
					analysis->FillH2(
						offset + kPhantomCountingHistogramOffset,
						primaryEnergy, interfaceId,
						countingResponses[phantomIndex][responseIndex]
					);
				}


			}
		} else if (particlePDG >= kFirstSupportedIonPDG) {
			// We first check if we are dealing with one of the smaller, relevant isotopes
			// We then check if we are dealing with one of: H2, H3, He3, He4
			// If so, we add the contribution to the dose-rate histogram
			if (ionResponseIndices.find(particlePDG) != ionResponseIndices.end()){
				const G4int responseIndex =
					ionResponseIndices[particlePDG] * kPhantomResponseEnergyBins
					+ responseEnergyBin;
				const G4double radiationWeight = kHeavyIonRadiationWeight;
				for (G4int phantomIndex = 0;
				     phantomIndex < fSettings.phantomCount;
				     ++phantomIndex) {
					const G4int offset = kFirstPhantomHistogramId
						+ kPhantomHistogramsPerPhantom*phantomIndex;
					analysis->FillH2(
						offset + kPhantomDoseHistogramOffset,
						primaryEnergy, interfaceId,
						radiationResponses[phantomIndex][responseIndex]
							* kineticEnergy/eV
					);
					analysis->FillH2(
						offset + kPhantomEquivalentDoseHistogramOffset,
						primaryEnergy, interfaceId,
						radiationResponses[phantomIndex][responseIndex]
							* kineticEnergy/eV * radiationWeight
					);
					analysis->FillH2(
						offset + kPhantomCountingHistogramOffset,
						primaryEnergy, interfaceId,
						countingResponses[phantomIndex][responseIndex]
					);
				}
			}
		}

		if (WritesInterfaceNtuple(fSettings.outputMode)) {
			analysis->FillNtupleIColumn(kInterfaceNtupleId, kInterfacePDG, particlePDG);
			analysis->FillNtupleIColumn(kInterfaceNtupleId, kInterfaceId, interfaceId);
			analysis->FillNtupleIColumn(
				kInterfaceNtupleId,
				kInterfaceAngleDegrees,
				static_cast<G4int>(std::round(inclination/deg))
			);
			analysis->FillNtupleDColumn(
				kInterfaceNtupleId,
				kInterfaceKineticEnergyMeV,
				preStepPoint->GetKineticEnergy()/MeV
			);
			analysis->FillNtupleDColumn(
				kInterfaceNtupleId,
				kInterfacePrimaryEnergyMeV,
				primaryEnergy/MeV
			);
			analysis->AddNtupleRow(kInterfaceNtupleId);
		}
	}

	return true;

}

}  // namespace atris
