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
    /// Values accumulated while the macro describes one response.
    struct PendingResponse
    {
      G4String name;
      G4String tableFile;
      G4bool scaleByCrossingEnergy = false;
      G4bool scaleByRadiationWeight = false;
      G4bool scaleByInversePhantomMass = false;
    };

    /// The selected phantom and the response currently being assembled for it.
    struct SelectedPhantom
    {
      G4String name;
      PendingResponse response;
    };

    void SetRandomSeeds(G4long firstSeed, G4long secondSeed);
    void SetOutputMode(G4String outputModeName);
    void AddPhantomResponse();
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

    SelectedPhantom fSelectedPhantom;
    G4UIcommand* fAddPhantomResponseCommand = nullptr;
    G4UIcommand* fInitializeCommand = nullptr;
};

}  // namespace atris

#endif
