#ifndef PhantomResponses_hh
#define PhantomResponses_hh

#include "globals.hh"

#include <map>
#include <set>
#include <vector>

namespace atris
{

/**
 * Describes one named response channel for one phantom.
 *
 * A channel combines a response-table file with the factors applied when a
 * particle crosses a layer interface. After the response is added, `values`
 * points into storage owned by the containing PhantomResponses object.
 */
struct PhantomResponse
{
    /// User-facing phantom identity shared by all of its response channels.
    G4String phantomStem;

    /// Response channel name used in histogram and metadata names.
    G4String name;

    /// Source table filename recorded in output metadata.
    G4String fileName;

    /// Multiply the table coefficient by the crossing particle's kinetic energy.
    G4bool scaleByCrossingEnergy = false;

    /// Multiply by AtRIS's particle-dependent radiation weighting factor.
    G4bool scaleByRadiationWeight = false;

    /// Request inverse-mass scaling during Python post-processing.
    G4bool scaleByInversePhantomMass = false;

    /// Flattened particle-by-energy response table owned by PhantomResponses.
    const std::vector<G4double>* values = nullptr;
};

/**
 * Owns the response tables and particle lookup shared by all phantoms in a run.
 *
 * Add() loads each distinct table file once. The first table establishes the
 * ordered PDG header; every later table must use the same header so a particle
 * index has one meaning across every response. Common signed PDG codes use a
 * dense lookup, while sparse ion codes use a map.
 *
 * The collection owns all numeric table storage. PhantomResponse entries refer
 * to that stable storage and are consumed by HistoManager and SensitiveDetector
 * after macro configuration is complete.
 */
class PhantomResponses
{
  public:
    /**
     * Loads the configured table and adds or replaces a named phantom response.
     *
     * Returns false when the table cannot be read, has the wrong number of
     * values, or has a PDG header inconsistent with tables already loaded.
     */
    G4bool Add(PhantomResponse response);

    /// Returns configured responses in histogram-booking order.
    const std::vector<PhantomResponse>& GetAll() const { return fResponses; }

    /// Returns the number of distinct phantom stems represented by responses.
    G4int GetPhantomCount() const { return static_cast<G4int>(fPhantomStems.size()); }

    /// Returns a particle's row index in every response table, or -1 if absent.
    G4int FindParticleIndex(G4int pdg) const;

  private:
    void ConfigureParticleLookup(const std::vector<G4int>& particleCodes, const G4String& fileName);

    std::vector<G4int> fParticleCodes;
    G4String fParticleHeaderFile;
    std::vector<G4int> fLightParticleIndices;
    std::map<G4int, G4int> fIonIndices;
    std::set<G4String> fPhantomStems;
    std::map<G4String, std::vector<G4double>> fTables;
    std::vector<PhantomResponse> fResponses;
};

}  // namespace atris

#endif
