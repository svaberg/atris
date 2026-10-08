#ifndef RunConfiguration_hh
#define RunConfiguration_hh

#include "G4GenericMessenger.hh"
#include "globals.hh"

#include "PhantomResponses.hh"

class G4RunManager;
class G4GDMLParser;
class G4UIcommand;

namespace atris
{

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
    RunConfiguration(G4RunManager* runManager, RunSettings& settings, ::G4GDMLParser& parser,
                     PhantomResponses& phantomResponses);

  private:
    /// Stores the two random seeds supplied by the run macro.
    void SetRandomSeeds(G4long firstSeed, G4long secondSeed);

    /// Converts a user-facing output-mode name to its internal value.
    void SetOutputMode(G4String outputModeName);

    /// Loads and appends the phantom response currently described by the macro.
    void AddPhantomResponse();

    /// Reads configured energy-bin edges; returns false after reporting failure.
    G4bool ReadEnergyBins();

    /// Reports which output products the selected mode will write.
    void DescribeOutputMode() const;

    /// Reads the GDML geometry and derives its sensitive-detector dimensions.
    void PrepareGeometry();

    /// Installs detector construction, physics, and user actions in Geant4.
    void InstallRunComponents();

    /// Applies configured random seeds to Geant4 when they were supplied.
    void ApplyRandomSeeds() const;

    /// Completes configuration and initializes the Geant4 run manager.
    void Initialize();

    G4RunManager* const fRunManager;
    RunSettings& fSettings;
    ::G4GDMLParser& fParser;
    PhantomResponses& fPhantomResponses;

    // Each messenger owns the commands registered in one Geant4 UI directory.
    // Keeping these members alive keeps the complete AtRIS command tree
    // available while Geant4 interprets the run macro.
    /// Owns the commands directly under `/atris/`.
    G4GenericMessenger fMessenger;

    /// Owns the `/atris/directionHistogram/` commands.
    G4GenericMessenger fDirectionHistogramMessenger;

    /// Owns the `/atris/positionHistogram/` commands.
    G4GenericMessenger fPositionHistogramMessenger;

    /// Owns the `/atris/phantom/` commands.
    G4GenericMessenger fPhantomMessenger;

    /// Owns the `/atris/phantom/response/` commands.
    G4GenericMessenger fPhantomResponseMessenger;

    /// Response assembled by macro properties before `response/add` loads it.
    PhantomResponse fPendingResponse;
    G4UIcommand* fAddPhantomResponseCommand = nullptr;
    G4UIcommand* fInitializeCommand = nullptr;
};

}  // namespace atris

#endif
