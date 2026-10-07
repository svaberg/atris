#ifndef RunConfiguration_hh
#define RunConfiguration_hh

#include "G4GenericMessenger.hh"
#include "globals.hh"

class G4RunManager;
class G4GDMLParser;
class G4UIcommand;

namespace atris {

class PhantomResponses;
struct RunSettings;

/**
 * Exposes AtRIS run configuration as Geant4 macro commands.
 *
 * The constructor registers the `/atris/` command tree with Geant4's UI
 * manager. Those commands populate RunSettings, select input files, and build
 * the PhantomResponses collection while the macro is being interpreted. The
 * final `/atris/initialize` command reads the energy bins and GDML geometry,
 * installs the detector, physics list, and user actions, applies explicit random
 * seeds, and initializes the Geant4 run manager.
 *
 * This object owns the command messengers and must therefore remain alive for
 * the complete macro execution. The run manager, settings, parser, and response
 * collection are borrowed and must outlive it.
 */
class RunConfiguration
{
  public:
    /// Registers the AtRIS macro commands against the supplied run state.
    RunConfiguration(
      G4RunManager* runManager,
      RunSettings& settings,
      ::G4GDMLParser& parser,
      PhantomResponses& phantomResponses
    );

  private:
    void SetRandomSeeds(G4long firstSeed, G4long secondSeed);
    void AddPhantomResponse();
    void Initialize();

    G4RunManager* const fRunManager;
    RunSettings& fSettings;
    ::G4GDMLParser& fParser;
    PhantomResponses& fPhantomResponses;
    G4String fGeometryFileName = "simulation.gdml";
    G4String fEnergyBinsFileName = "simulation.bins";
    G4String fOutputModeName = "response";
    G4GenericMessenger fMessenger;
    G4GenericMessenger fDirectionHistogramMessenger;
    G4GenericMessenger fPositionHistogramMessenger;
    G4GenericMessenger fPhantomMessenger;
    G4GenericMessenger fPhantomResponseMessenger;
    G4String fPhantomName;
    G4String fPhantomResponseName;
    G4String fPhantomResponseTableFile;
    G4bool fPhantomResponseScaleByCrossingEnergy = false;
    G4bool fPhantomResponseScaleByRadiationWeight = false;
    G4bool fPhantomResponseScaleByInversePhantomMass = false;
    G4UIcommand* fAddPhantomResponseCommand = nullptr;
    G4UIcommand* fInitializeCommand = nullptr;
};

}  // namespace atris

#endif
