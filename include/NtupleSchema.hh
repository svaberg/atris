#ifndef NtupleSchema_hh
#define NtupleSchema_hh 1

#include "globals.hh"

namespace atris
{

/**
 * Column positions for ntuples booked by HistoManager and filled elsewhere.
 *
 * Geant4 identifies ntuples and their columns by integer position. These names
 * keep the booking order synchronized with writes from HistoManager and
 * SensitiveDetector. Changing the metadata layout or meaning requires a schema
 * version increment; changing any enum requires updating the corresponding
 * booking calls in HistoManager::Book().
 */

// Increment this when the metadata ntuple layout or meaning changes.
constexpr G4int kMetadataSchemaVersion = 2;

/// Fixed ID of the run-metadata ntuple.
constexpr G4int kMetadataNtupleId = 0;

/// Columns in the run-metadata ntuple.
enum MetadataNtupleColumn : G4int
{
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

/// Fixed ID of the interface-crossing ntuple when that ntuple is enabled.
constexpr G4int kInterfaceNtupleId = 1;

/// Columns in the interface-crossing ntuple.
enum InterfaceNtupleColumn : G4int
{
  kInterfacePDG = 0,
  kInterfaceId,
  kInterfaceAngleDegrees,
  kInterfaceKineticEnergyMeV,
  kInterfacePrimaryEnergyMeV,
};

/// Fixed ID of the transport-step ntuple when that ntuple is enabled.
constexpr G4int kStepNtupleId = 2;

/// Columns in the transport-step ntuple.
enum StepNtupleColumn : G4int
{
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

/**
 * Columns in the response-definition ntuple.
 *
 * Its ntuple ID follows the optional interface and step ntuples and is therefore
 * calculated when metadata is written rather than fixed here.
 */
enum ResponseNtupleColumn : G4int
{
  kResponsePhantomStem = 0,
  kResponseName,
  kResponseFile,
  kResponseScaleByCrossingEnergy,
  kResponseScaleByRadiationWeight,
  kResponseScaleByInversePhantomMass,
};

}  // namespace atris

#endif
