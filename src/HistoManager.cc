#include "HistoManager.hh"

#include "DetectorConstruction.hh"
#include "NtupleSchema.hh"
#include "OutputMode.hh"
#include "PhantomResponseSchema.hh"
#include "PhantomResponses.hh"
#include "RunSettings.hh"

#include "G4AnalysisManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4SDManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include "G4UnitsTable.hh"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <math.h>
#include <string>
#include <vector>

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
	const G4String& accumulatedWeight,
	const atris::RunSettings& settings,
	const G4int phantomCount
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
	histogram->add_annotation("atris.input_prefix", settings.simulationInputPrefix);
	histogram->add_annotation("atris.physics_list", settings.physicsListName);
	histogram->add_annotation("atris.output_mode", std::to_string(settings.outputMode));
	histogram->add_annotation("atris.phantom_count", std::to_string(phantomCount));
	if (settings.hasExplicitSeeds) {
		histogram->add_annotation(
			"atris.random_seed_pairs",
			std::to_string(settings.explicitSeeds[0]) + ":"
				+ std::to_string(settings.explicitSeeds[1])
		);
	} else {
		histogram->add_annotation("atris.random_seed_pairs", "runtime-default");
	}
}

G4String AccumulationName(const atris::ResponseAccumulation accumulation)
{
	switch (accumulation) {
		case atris::ResponseAccumulation::kCoefficient:
			return "coefficient";
		case atris::ResponseAccumulation::kEnergy:
			return "energy";
		case atris::ResponseAccumulation::kRadiationWeightedEnergy:
			return "radiation-weighted-energy";
	}
	return "unknown";
}

G4String AccumulatedWeight(const atris::ResponseAccumulation accumulation)
{
	switch (accumulation) {
		case atris::ResponseAccumulation::kCoefficient:
			return "response coefficient";
		case atris::ResponseAccumulation::kEnergy:
			return "response coefficient times crossing kinetic energy [eV]";
		case atris::ResponseAccumulation::kRadiationWeightedEnergy:
			return "response coefficient times crossing kinetic energy and radiation weight [eV]";
	}
	return "unknown response weight";
}

}  // namespace

namespace atris {

HistoManager::HistoManager(
	const RunSettings& settings,
	const PhantomResponses& phantomResponses
)
	: fSettings(settings),
	fPhantomResponses(phantomResponses)
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
	const G4int phantomCount = fPhantomResponses.GetPhantomCount();
	const auto& responses = fPhantomResponses.GetAll();
	// This code replaces the HistoManager.cc
	G4cout << "### AtRIS: configuring analysis histograms. " << G4endl;
	analysis->SetVerboseLevel(0);
	analysis->SetActivation(true);     //enable inactivation of histos, nTuples
	G4int id = analysis->CreateH1(
		"h1.1", "Primary kinetic energy", fSettings.energyBins, "MeV"
	);
	auto* const primaryEnergy = analysis->GetH1(id);
	AnnotateHistogram(
		primaryEnergy,
		"h1.1",
		"primary kinetic energy distribution",
		"primary kinetic energy [MeV]",
		fSettings,
		phantomCount
	);
	analysis->SetH1XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH1YAxisTitle(id, "Accumulated primary kinetic energy [MeV]");
	analysis->SetH1Activation(id, true);
	// This is the direction histogram
	id = analysis->CreateH2("h2.dir", "Primary source direction",
				fSettings.directionHistogramBins[0], kSourceAzimuthMin, kSourceAzimuthMax,
				fSettings.directionHistogramBins[1], kSourceCosineMin, kSourceCosineMax);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.dir",
		"primary source direction",
		"primary count",
		fSettings,
		phantomCount
	);
	analysis->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
	analysis->SetH2YAxisTitle(id, "Cosine of global polar angle");
	analysis->SetH2ZAxisTitle(id, "Primary count");
	analysis->SetH2Activation(id,true);
	// This is the position histogram.
	id = analysis->CreateH2("h2.pos", "Primary source position",
				fSettings.positionHistogramBins[0], kSourceAzimuthMin, kSourceAzimuthMax,
				fSettings.positionHistogramBins[1], kSourceCosineMin, kSourceCosineMax);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.pos",
		"primary source position",
		"primary count",
		fSettings,
		phantomCount
	);
	analysis->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
	analysis->SetH2YAxisTitle(id, "Cosine of global polar angle");
	analysis->SetH2ZAxisTitle(id, "Primary count");
	analysis->SetH2Activation(id,true);
	// This is the new ionization energy histogram, it gets the ID 2
	id = analysis->CreateH2(
		"h2.ion", "Ionizing energy deposition", fSettings.energyBins,
		fSettings.detectorBins,
		"MeV", "none", "none", "none"
	);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.ion",
		"ionizing energy deposition",
		"total energy deposit minus non-ionizing energy deposit [MeV]",
		fSettings,
		phantomCount
	);
	analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH2YAxisTitle(id, "Sensitive detector ID");
	analysis->SetH2ZAxisTitle(id, "Ionizing energy deposited [MeV]");
	analysis->SetH2Activation(id,true);
	// Total local energy deposition, retained separately so that atmospheric
	// heating estimates do not have to rely on the ionizing component alone.
	id = analysis->CreateH2(
		"h2.edep", "Total energy deposition", fSettings.energyBins,
		fSettings.detectorBins,
		"MeV", "none", "none", "none"
	);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.edep",
		"total energy deposition",
		"total energy deposit [MeV]",
		fSettings,
		phantomCount
	);
	analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH2YAxisTitle(id, "Sensitive detector ID");
	analysis->SetH2ZAxisTitle(id, "Total energy deposited [MeV]");
	analysis->SetH2Activation(id,true);
	G4cout << "### AtRIS: initializing " << responses.size()
	       << " response histograms for " << phantomCount
	       << " phantoms; " << responses.size() + kBaseHistogramCount
	       << " histograms in total" << G4endl;
	for (const PhantomResponse& response : responses) {
		const G4String histogramName =
			"h2." + response.phantomStem + "." + response.name;
		const G4String accumulatedWeight = AccumulatedWeight(
			response.accumulation
		);
		id = analysis->CreateH2(
			histogramName,
			response.name + " response for " + response.phantomStem,
			fSettings.energyBins,
			fSettings.detectorBins,
			"MeV", "none", "none", "none"
		);
		auto* const histogram = analysis->GetH2(id);
		AnnotateHistogram(
			histogram,
			histogramName,
			"phantom response " + response.name,
			accumulatedWeight,
			fSettings,
			phantomCount
		);
		if (histogram != nullptr) {
			histogram->add_annotation("atris.phantom_stem", response.phantomStem);
			histogram->add_annotation("atris.response_name", response.name);
			histogram->add_annotation("atris.response_file", response.fileName);
			histogram->add_annotation(
				"atris.response_accumulation",
				AccumulationName(response.accumulation)
			);
		}
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, accumulatedWeight);
		analysis->SetH2Activation(id,true);
	}

	if (!WritesInterfaceNtuple(fSettings.outputMode)) return;

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
	if (!WritesStepNtuple(fSettings.outputMode)) return;

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
	if (!WritesInterfaceNtuple(fSettings.outputMode)) return;
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
		kMetadataNtupleId, kMetadataInputPrefix, fSettings.simulationInputPrefix
	);
	analysis->FillNtupleSColumn(
		kMetadataNtupleId, kMetadataPhysicsList, fSettings.physicsListName
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataOutputMode, fSettings.outputMode
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId,
		kMetadataPhantomCount,
		fPhantomResponses.GetPhantomCount()
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataSeedsExplicit, fSettings.hasExplicitSeeds
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataRandomSeed1, fSettings.explicitSeeds[0]
	);
	analysis->FillNtupleIColumn(
		kMetadataNtupleId, kMetadataRandomSeed2, fSettings.explicitSeeds[1]
	);
	analysis->AddNtupleRow(kMetadataNtupleId);
}

}  // namespace atris
