#include "HistoManager.hh"
#include "NtupleSchema.hh"
#include "OutputMode.hh"
#include "PhantomResponseSchema.hh"
#include "G4AnalysisManager.hh"
#include "G4Threading.hh"
#include "G4UnitsTable.hh"
#include "DetectorConstruction.hh"
#include "G4SDManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include <array>
#include <vector>
#include <string>
#include <math.h>
#include <iostream>
#include <iterator>
#include <fstream>
#include <algorithm>

extern std::vector<G4double> energyBins;
extern std::vector<G4double> detectorBins;
extern std::array<G4int, 2> directionHistogramBins;
extern std::array<G4int, 2> positionHistogramBins;
extern G4int numberOfPhantoms;
extern G4int mode;
extern G4String simulationInputPrefix;
extern G4String physicsListName;
extern G4bool hasExplicitSeeds;
extern std::array<G4long, 2> explicitSeeds;

namespace {

constexpr G4double kSourceAzimuthMin = 0.;
constexpr G4double kSourceAzimuthMax = twopi;
constexpr G4double kSourceCosineMin = -1.;
constexpr G4double kSourceCosineMax = 1.;
// One primary-energy H1 and four non-phantom H2 histograms are always booked.
constexpr G4int kBaseHistogramCount = 5;
// Version of the annotations written into Geant4 CSV histogram headers.
constexpr G4int kCsvSchemaVersion = 1;

template <typename Histogram>
void AnnotateHistogram(
	Histogram* const histogram,
	const G4String& name,
	const G4String& quantity,
	const G4String& accumulatedWeight
)
{
	if (histogram == nullptr) return;
	histogram->add_annotation(
		"atris.csv_schema",
		std::to_string(kCsvSchemaVersion)
	);
	histogram->add_annotation("atris.version", ATRIS_VERSION);
	histogram->add_annotation("atris.histogram_name", name);
	histogram->add_annotation("atris.quantity", quantity);
	histogram->add_annotation("atris.accumulated_weight", accumulatedWeight);
	histogram->add_annotation("atris.input_prefix", simulationInputPrefix);
	histogram->add_annotation("atris.physics_list", physicsListName);
	histogram->add_annotation("atris.output_mode", std::to_string(mode));
	histogram->add_annotation("atris.phantom_count", std::to_string(numberOfPhantoms));
	if (hasExplicitSeeds) {
		histogram->add_annotation(
			"atris.random_seed_pairs",
			std::to_string(explicitSeeds[0]) + ":" + std::to_string(explicitSeeds[1])
		);
	} else {
		histogram->add_annotation("atris.random_seed_pairs", "runtime-default");
	}
}

}  // namespace

namespace atris {

HistoManager::HistoManager()
{
	Book();
}

HistoManager::~HistoManager()
{
	G4cout << "HistoManager deleted." << G4endl;
}

void HistoManager::Book() const
{
	G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
	// This code replaces the HistoManager.cc
	G4cout << "### AtRIS: configuring analysis histograms. " << G4endl;
	analysis->SetVerboseLevel(0);
	analysis->SetActivation(true);     //enable inactivation of histos, nTuples
	G4int id = analysis->CreateH1("h1.1", "Primary kinetic energy", energyBins, "MeV");
	auto* const primaryEnergy = analysis->GetH1(id);
	AnnotateHistogram(
		primaryEnergy,
		"h1.1",
		"primary kinetic energy distribution",
		"primary kinetic energy [MeV]"
	);
	analysis->SetH1XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH1YAxisTitle(id, "Accumulated primary kinetic energy [MeV]");
	analysis->SetH1Activation(id, true);
	// This is the direction histogram
	id = analysis->CreateH2("h2.dir", "Primary source direction",
				directionHistogramBins[0], kSourceAzimuthMin, kSourceAzimuthMax,
				directionHistogramBins[1], kSourceCosineMin, kSourceCosineMax);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.dir",
		"primary source direction",
		"primary count"
	);
	analysis->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
	analysis->SetH2YAxisTitle(id, "Cosine of global polar angle");
	analysis->SetH2ZAxisTitle(id, "Primary count");
	analysis->SetH2Activation(id,true);
	// This is the position histogram.
	id = analysis->CreateH2("h2.pos", "Primary source position",
				positionHistogramBins[0], kSourceAzimuthMin, kSourceAzimuthMax,
				positionHistogramBins[1], kSourceCosineMin, kSourceCosineMax);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.pos",
		"primary source position",
		"primary count"
	);
	analysis->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
	analysis->SetH2YAxisTitle(id, "Cosine of global polar angle");
	analysis->SetH2ZAxisTitle(id, "Primary count");
	analysis->SetH2Activation(id,true);
	// Now we activate the phantom histograms, 3 per phantom
	// This is the new ionization energy histogram, it gets the ID 2
	id = analysis->CreateH2(
		"h2.ion", "Ionizing energy deposition", energyBins, detectorBins,
		"MeV", "none", "none", "none"
	);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.ion",
		"ionizing energy deposition",
		"total energy deposit minus non-ionizing energy deposit [MeV]"
	);
	analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH2YAxisTitle(id, "Sensitive detector ID");
	analysis->SetH2ZAxisTitle(id, "Ionizing energy deposited [MeV]");
	analysis->SetH2Activation(id,true);
	// Total local energy deposition, retained separately so that atmospheric
	// heating estimates do not have to rely on the ionizing component alone.
	id = analysis->CreateH2(
		"h2.edep", "Total energy deposition", energyBins, detectorBins,
		"MeV", "none", "none", "none"
	);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.edep",
		"total energy deposition",
		"total energy deposit [MeV]"
	);
	analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH2YAxisTitle(id, "Sensitive detector ID");
	analysis->SetH2ZAxisTitle(id, "Total energy deposited [MeV]");
	analysis->SetH2Activation(id,true);
	for (G4int phantomIndex = 0; phantomIndex < numberOfPhantoms; ++phantomIndex){
		G4cout << "### AtRIS: Initializing higher order histograms for "
		       << numberOfPhantoms << " phantoms, with a total number of histograms "
		       << "equal to "
		       << numberOfPhantoms*kPhantomHistogramsPerPhantom
		          + kBaseHistogramCount << G4endl;
		// Post-processing removes the extra detector boundary from interface data.
		const G4String suffix = std::to_string(phantomIndex);
		id = analysis->CreateH2(
			"h2.dos" + suffix, "Phantom energy response", energyBins, detectorBins,
			"MeV", "none", "none", "none"
		);
		auto* const dose = analysis->GetH2(id);
		AnnotateHistogram(
			dose,
			"h2.dos" + suffix,
			"phantom energy response",
			"response coefficient times crossing kinetic energy [eV]"
		);
		if (dose != nullptr) dose->add_annotation("atris.phantom_id", suffix);
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, "Phantom energy-response weight [eV]");
		analysis->SetH2Activation(id,true);
		// same as above, but only for the equivalent dose rate
		id = analysis->CreateH2(
			"h2.equi" + suffix, "Radiation-weighted phantom energy response",
			energyBins, detectorBins, "MeV", "none", "none", "none"
		);
		auto* const equivalentDose = analysis->GetH2(id);
		AnnotateHistogram(
			equivalentDose,
			"h2.equi" + suffix,
			"radiation-weighted phantom energy response",
			"response coefficient times crossing kinetic energy and radiation weight [eV]"
		);
		if (equivalentDose != nullptr) {
			equivalentDose->add_annotation("atris.phantom_id", suffix);
		}
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, "Radiation-weighted phantom energy-response weight [eV]");
		analysis->SetH2Activation(id,true);
		// a histogram to hold the count rates if the first phantom
		id = analysis->CreateH2(
			"h2.rates" + suffix, "Phantom counting response", energyBins, detectorBins,
			"MeV", "none", "none", "none"
		);
		auto* const countRate = analysis->GetH2(id);
		AnnotateHistogram(
			countRate,
			"h2.rates" + suffix,
			"phantom counting response",
			"counting response coefficient"
		);
		if (countRate != nullptr) countRate->add_annotation("atris.phantom_id", suffix);
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, "Counting-response weight");
		analysis->SetH2Activation(id,true);

	}

	if (!WritesInterfaceNtuple(mode)) return;

	id = analysis->CreateNtuple("metadata", "AtRIS output metadata");
	analysis->CreateNtupleIColumn(id, "schema");
	analysis->CreateNtupleSColumn(id, "atris_version");
	analysis->CreateNtupleSColumn(id, "input_prefix");
	analysis->CreateNtupleSColumn(id, "physics_list");
	analysis->CreateNtupleIColumn(id, "output_mode");
	analysis->CreateNtupleIColumn(id, "phantom_count");
	analysis->CreateNtupleIColumn(id, "seeds_explicit");
	analysis->CreateNtupleIColumn(id, "random_seed_1");
	analysis->CreateNtupleIColumn(id, "random_seed_2");
	analysis->FinishNtuple(id);
	id = analysis->CreateNtuple(
		"interfaces",
		"Particle crossings at layer interfaces"
	);
	analysis->CreateNtupleIColumn(id, "pdg");
	analysis->CreateNtupleIColumn(id, "interface_id");
	analysis->CreateNtupleIColumn(id, "angle_degrees");
	analysis->CreateNtupleDColumn(id, "kinetic_energy_MeV");
	analysis->CreateNtupleDColumn(id, "primary_energy_MeV");
	analysis->FinishNtuple(id);
	if (!WritesStepNtuple(mode)) return;

	id = analysis->CreateNtuple("steps", "Particle transport steps");
	analysis->CreateNtupleIColumn(id, "event_id");
	analysis->CreateNtupleIColumn(id, "track_id");
	analysis->CreateNtupleIColumn(id, "parent_id");
	analysis->CreateNtupleIColumn(id, "step_id");
	analysis->CreateNtupleIColumn(id, "pdg");
	analysis->CreateNtupleIColumn(id, "detector_id");
	analysis->CreateNtupleDColumn(id, "pre_x_km");
	analysis->CreateNtupleDColumn(id, "pre_y_km");
	analysis->CreateNtupleDColumn(id, "pre_z_km");
	analysis->CreateNtupleDColumn(id, "post_x_km");
	analysis->CreateNtupleDColumn(id, "post_y_km");
	analysis->CreateNtupleDColumn(id, "post_z_km");
	analysis->CreateNtupleDColumn(id, "pre_kinetic_energy_MeV");
	analysis->CreateNtupleDColumn(id, "post_kinetic_energy_MeV");
	analysis->CreateNtupleDColumn(id, "energy_deposit_MeV");
	analysis->CreateNtupleDColumn(id, "nonionizing_energy_deposit_MeV");
	analysis->CreateNtupleDColumn(id, "step_length_m");
	analysis->CreateNtupleDColumn(id, "global_time_ns");
	analysis->CreateNtupleDColumn(id, "primary_energy_MeV");
	analysis->CreateNtupleSColumn(id, "creator_process");
	analysis->CreateNtupleSColumn(id, "step_process");
	analysis->FinishNtuple(id);

}

void HistoManager::FillMetadata() const
{
	if (!WritesInterfaceNtuple(mode)) return;
	// One worker records the shared run metadata while Geant4 merges all ntuples.
	if (G4Threading::G4GetThreadId() != 0) return;
	auto* const analysis = G4AnalysisManager::Instance();
	analysis->FillNtupleIColumn(
		kMetadataNtupleId,
		kMetadataSchema,
		kMetadataSchemaVersion
	);
	analysis->FillNtupleSColumn(
		kMetadataNtupleId, kMetadataAtrisVersion, ATRIS_VERSION
	);
	analysis->FillNtupleSColumn(
		kMetadataNtupleId, kMetadataInputPrefix, simulationInputPrefix
	);
	analysis->FillNtupleSColumn(
		kMetadataNtupleId, kMetadataPhysicsList, physicsListName
	);
	analysis->FillNtupleIColumn(kMetadataNtupleId, kMetadataOutputMode, mode);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataPhantomCount, numberOfPhantoms
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataSeedsExplicit, hasExplicitSeeds
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataRandomSeed1, explicitSeeds[0]
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataRandomSeed2, explicitSeeds[1]
	);
	analysis->AddNtupleRow(kMetadataNtupleId);
}

}  // namespace atris
