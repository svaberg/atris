#ifndef NtupleSchema_hh
#define NtupleSchema_hh 1

#include "globals.hh"

namespace atris {

// Increment this when the metadata ntuple layout or meaning changes.
constexpr G4int kMetadataSchemaVersion = 2;

constexpr G4int kMetadataNtupleId = 0;
enum MetadataNtupleColumn : G4int {
	kMetadataSchema = 0,
	kMetadataAtrisVersion,
	kMetadataInputPrefix,
	kMetadataPhysicsList,
	kMetadataOutputMode,
	kMetadataPhantomCount,
	kMetadataSeedsExplicit,
	kMetadataRandomSeed1,
	kMetadataRandomSeed2,
};

constexpr G4int kInterfaceNtupleId = 1;
enum InterfaceNtupleColumn : G4int {
	kInterfacePDG = 0,
	kInterfaceId,
	kInterfaceAngleDegrees,
	kInterfaceKineticEnergyMeV,
	kInterfacePrimaryEnergyMeV,
};

constexpr G4int kStepNtupleId = 2;
enum StepNtupleColumn : G4int {
	kStepEventId = 0,
	kStepTrackId,
	kStepParentId,
	kStepId,
	kStepPDG,
	kStepDetectorId,
	kStepPreXKm,
	kStepPreYKm,
	kStepPreZKm,
	kStepPostXKm,
	kStepPostYKm,
	kStepPostZKm,
	kStepPreKineticEnergyMeV,
	kStepPostKineticEnergyMeV,
	kStepEnergyDepositMeV,
	kStepNonionizingEnergyDepositMeV,
	kStepLengthM,
	kStepGlobalTimeNs,
	kStepPrimaryEnergyMeV,
	kStepCreatorProcess,
	kStepProcess,
};

enum ResponseNtupleColumn : G4int {
	kResponsePhantomStem = 0,
	kResponseName,
	kResponseFile,
	kResponseScaleByCrossingEnergy,
	kResponseScaleByRadiationWeight,
	kResponseScaleByInversePhantomMass,
};

}  // namespace atris

#endif
