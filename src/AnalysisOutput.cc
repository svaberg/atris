#include "AnalysisOutput.hh"

#include "G4AnalysisManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4Threading.hh"

#include "NtupleSchema.hh"
#include "OutputMode.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"

namespace
{

constexpr G4double kSourceAzimuthMin = 0.;
constexpr G4double kSourceAzimuthMax = twopi;
constexpr G4double kSourceCosineMin = -1.;
constexpr G4double kSourceCosineMax = 1.;
// One primary-energy H1 and four non-phantom H2 histograms are always booked.
constexpr G4int kBaseHistogramCount = 5;

G4String AccumulatedWeight(const atris::PhantomResponse& response)
{
  G4String weight = "response coefficient";
  if (response.scaleByCrossingEnergy)
  {
    weight += " times crossing kinetic energy [eV]";
  }
  if (response.scaleByRadiationWeight)
  {
    weight += " times radiation weight";
  }
  return weight;
}

}  // namespace

namespace atris
{

AnalysisOutput::AnalysisOutput(const RunSettings& runSettings,
                               const PhantomResponses& phantomResponses)
  : fRunSettings(runSettings), fPhantomResponses(phantomResponses)
{
  BookHistograms();
  BookNtuples();
}

AnalysisOutput::~AnalysisOutput()
{
  G4debug << "AnalysisOutput deleted." << G4endl;
}

void AnalysisOutput::BookHistograms() const
{
  G4AnalysisManager* const analysisManager = G4AnalysisManager::Instance();
  const G4int phantomCount = fPhantomResponses.GetPhantomCount();
  const auto& responses = fPhantomResponses.GetAll();
  G4debug << "### AtRIS: configuring analysis histograms. " << G4endl;
  analysisManager->SetVerboseLevel(0);
  // Allow individual analysis objects to be activated or deactivated.
  analysisManager->SetActivation(true);
  G4int id =
    analysisManager->CreateH1("h1.1", "Primary kinetic energy", fRunSettings.energyBins, "MeV");
  analysisManager->SetH1XAxisTitle(id, "Primary kinetic energy [MeV]");
  analysisManager->SetH1YAxisTitle(id, "Accumulated primary kinetic energy [MeV]");
  analysisManager->SetH1Activation(id, true);
  id = analysisManager->CreateH2(
    "h2.dir", "Primary source direction", fRunSettings.directionHistogramBins[0], kSourceAzimuthMin,
    kSourceAzimuthMax, fRunSettings.directionHistogramBins[1], kSourceCosineMin, kSourceCosineMax);
  analysisManager->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
  analysisManager->SetH2YAxisTitle(id, "Cosine of global polar angle");
  analysisManager->SetH2ZAxisTitle(id, "Primary count");
  analysisManager->SetH2Activation(id, true);
  id = analysisManager->CreateH2(
    "h2.pos", "Primary source position", fRunSettings.positionHistogramBins[0], kSourceAzimuthMin,
    kSourceAzimuthMax, fRunSettings.positionHistogramBins[1], kSourceCosineMin, kSourceCosineMax);
  analysisManager->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
  analysisManager->SetH2YAxisTitle(id, "Cosine of global polar angle");
  analysisManager->SetH2ZAxisTitle(id, "Primary count");
  analysisManager->SetH2Activation(id, true);
  id = analysisManager->CreateH2("h2.ion", "Ionizing energy deposition", fRunSettings.energyBins,
                                 fRunSettings.detectorBins, "MeV", "none", "none", "none");
  analysisManager->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
  analysisManager->SetH2YAxisTitle(id, "Sensitive detector ID");
  analysisManager->SetH2ZAxisTitle(id, "Ionizing energy deposited [MeV]");
  analysisManager->SetH2Activation(id, true);
  // Total local energy deposition, retained separately so that atmospheric
  // heating estimates do not have to rely on the ionizing component alone.
  id = analysisManager->CreateH2("h2.edep", "Total energy deposition", fRunSettings.energyBins,
                                 fRunSettings.detectorBins, "MeV", "none", "none", "none");
  analysisManager->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
  analysisManager->SetH2YAxisTitle(id, "Sensitive detector ID");
  analysisManager->SetH2ZAxisTitle(id, "Total energy deposited [MeV]");
  analysisManager->SetH2Activation(id, true);
  G4cout << "### AtRIS: initializing " << responses.size() << " response histograms for "
         << phantomCount << " phantoms; " << responses.size() + kBaseHistogramCount
         << " histograms in total" << G4endl;
  for (const PhantomResponse& response : responses)
  {
    const G4String histogramName = "h2." + response.phantomStem + "." + response.name;
    const G4String accumulatedWeight = AccumulatedWeight(response);
    id = analysisManager->CreateH2(
      histogramName, response.name + " response for " + response.phantomStem,
      fRunSettings.energyBins, fRunSettings.detectorBins, "MeV", "none", "none", "none");
    analysisManager->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
    analysisManager->SetH2YAxisTitle(id, "Interface ID");
    analysisManager->SetH2ZAxisTitle(id, accumulatedWeight);
    analysisManager->SetH2Activation(id, true);
  }
}

void AnalysisOutput::BookNtuples() const
{
  auto* const analysisManager = G4AnalysisManager::Instance();
  G4int id = analysisManager->CreateNtuple("metadata", "AtRIS output metadata");
  analysisManager->CreateNtupleIColumn(id, "schema");
  analysisManager->CreateNtupleSColumn(id, "atris_version");
  analysisManager->CreateNtupleSColumn(id, "input_prefix");
  analysisManager->CreateNtupleSColumn(id, "physics_list");
  analysisManager->CreateNtupleSColumn(id, "output_mode");
  analysisManager->CreateNtupleIColumn(id, "phantom_count");
  analysisManager->CreateNtupleIColumn(id, "seeds_explicit");
  analysisManager->CreateNtupleIColumn(id, "random_seed_1");
  analysisManager->CreateNtupleIColumn(id, "random_seed_2");
  analysisManager->FinishNtuple(id);
  if (WritesInterfaceNtuple(fRunSettings.outputMode))
  {
    id = analysisManager->CreateNtuple("interfaces", "Particle crossings at layer interfaces");
    analysisManager->CreateNtupleIColumn(id, "pdg");
    analysisManager->CreateNtupleIColumn(id, "interface_id");
    analysisManager->CreateNtupleIColumn(id, "angle_degrees");
    analysisManager->CreateNtupleDColumn(id, "kinetic_energy_MeV");
    analysisManager->CreateNtupleDColumn(id, "primary_energy_MeV");
    analysisManager->FinishNtuple(id);
  }
  if (WritesStepNtuple(fRunSettings.outputMode))
  {
    id = analysisManager->CreateNtuple("steps", "Particle transport steps");
    analysisManager->CreateNtupleIColumn(id, "event_id");
    analysisManager->CreateNtupleIColumn(id, "track_id");
    analysisManager->CreateNtupleIColumn(id, "parent_id");
    analysisManager->CreateNtupleIColumn(id, "step_id");
    analysisManager->CreateNtupleIColumn(id, "pdg");
    analysisManager->CreateNtupleIColumn(id, "detector_id");
    analysisManager->CreateNtupleDColumn(id, "pre_x_km");
    analysisManager->CreateNtupleDColumn(id, "pre_y_km");
    analysisManager->CreateNtupleDColumn(id, "pre_z_km");
    analysisManager->CreateNtupleDColumn(id, "post_x_km");
    analysisManager->CreateNtupleDColumn(id, "post_y_km");
    analysisManager->CreateNtupleDColumn(id, "post_z_km");
    analysisManager->CreateNtupleDColumn(id, "pre_kinetic_energy_MeV");
    analysisManager->CreateNtupleDColumn(id, "post_kinetic_energy_MeV");
    analysisManager->CreateNtupleDColumn(id, "energy_deposit_MeV");
    analysisManager->CreateNtupleDColumn(id, "nonionizing_energy_deposit_MeV");
    analysisManager->CreateNtupleDColumn(id, "step_length_m");
    analysisManager->CreateNtupleDColumn(id, "global_time_ns");
    analysisManager->CreateNtupleDColumn(id, "primary_energy_MeV");
    analysisManager->CreateNtupleSColumn(id, "creator_process");
    analysisManager->CreateNtupleSColumn(id, "step_process");
    analysisManager->FinishNtuple(id);
  }
  id = analysisManager->CreateNtuple("responses", "AtRIS phantom response definitions");
  analysisManager->CreateNtupleSColumn(id, "phantom_stem");
  analysisManager->CreateNtupleSColumn(id, "name");
  analysisManager->CreateNtupleSColumn(id, "file");
  analysisManager->CreateNtupleIColumn(id, "scale_by_crossing_energy");
  analysisManager->CreateNtupleIColumn(id, "scale_by_radiation_weight");
  analysisManager->CreateNtupleIColumn(id, "scale_by_inverse_phantom_mass");
  analysisManager->FinishNtuple(id);
}

void AnalysisOutput::FillMetadata() const
{
  // One worker records the shared run metadata while Geant4 merges all ntuples.
  if (G4Threading::G4GetThreadId() != 0) return;
  auto* const analysisManager = G4AnalysisManager::Instance();
  analysisManager->FillNtupleIColumn(kMetadataNtupleId, kMetadataSchema, kMetadataSchemaVersion);
  analysisManager->FillNtupleSColumn(kMetadataNtupleId, kMetadataAtrisVersion, ATRIS_VERSION);
  analysisManager->FillNtupleSColumn(kMetadataNtupleId, kMetadataInputPrefix,
                                     fRunSettings.simulationInputPrefix);
  analysisManager->FillNtupleSColumn(kMetadataNtupleId, kMetadataPhysicsList,
                                     fRunSettings.physicsListName);
  analysisManager->FillNtupleSColumn(kMetadataNtupleId, kMetadataOutputMode,
                                     OutputModeName(fRunSettings.outputMode));
  analysisManager->FillNtupleIColumn(kMetadataNtupleId, kMetadataPhantomCount,
                                     fPhantomResponses.GetPhantomCount());
  analysisManager->FillNtupleIColumn(kMetadataNtupleId, kMetadataSeedsExplicit,
                                     fRunSettings.explicitSeeds[0] != 0);
  analysisManager->FillNtupleIColumn(kMetadataNtupleId, kMetadataRandomSeed1,
                                     fRunSettings.explicitSeeds[0]);
  analysisManager->FillNtupleIColumn(kMetadataNtupleId, kMetadataRandomSeed2,
                                     fRunSettings.explicitSeeds[1]);
  analysisManager->AddNtupleRow(kMetadataNtupleId);

  const G4int responseNtupleId = kInterfaceNtupleId + WritesInterfaceNtuple(fRunSettings.outputMode)
                                 + WritesStepNtuple(fRunSettings.outputMode);
  for (const PhantomResponse& response : fPhantomResponses.GetAll())
  {
    analysisManager->FillNtupleSColumn(responseNtupleId, kResponsePhantomStem,
                                       response.phantomStem);
    analysisManager->FillNtupleSColumn(responseNtupleId, kResponseName, response.name);
    analysisManager->FillNtupleSColumn(responseNtupleId, kResponseFile, response.fileName);
    analysisManager->FillNtupleIColumn(responseNtupleId, kResponseScaleByCrossingEnergy,
                                       response.scaleByCrossingEnergy);
    analysisManager->FillNtupleIColumn(responseNtupleId, kResponseScaleByRadiationWeight,
                                       response.scaleByRadiationWeight);
    analysisManager->FillNtupleIColumn(responseNtupleId, kResponseScaleByInversePhantomMass,
                                       response.scaleByInversePhantomMass);
    analysisManager->AddNtupleRow(responseNtupleId);
  }
}

}  // namespace atris
