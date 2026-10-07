#ifndef DetectorConstruction_hh
#define DetectorConstruction_hh

#include "G4VUserDetectorConstruction.hh"

class G4Material;
class G4GDMLParser;

namespace atris {

class PhantomResponses;
struct RunSettings;

/**
 * Supplies Geant4 with the world parsed from GDML and attaches AtRIS detectors.
 *
 * RunConfiguration reads the GDML document before registering this object with
 * the run manager. Construct() returns that document's world volume.
 * ConstructSDandField() then finds the GDML `SensDet` auxiliary entries and
 * attaches one SensitiveDetector to each marked logical volume.
 *
 * The parser, settings, and phantom-response collection are borrowed. They must
 * remain alive for the lifetime of this object.
 */
class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    /// Creates a detector construction backed by an already populated parser.
    DetectorConstruction(
      const ::G4GDMLParser& parser,
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~DetectorConstruction() override;

    /// Creates and attaches sensitive detectors using GDML auxiliary metadata.
    void ConstructSDandField() override;

    /// Returns the physical world volume owned by the GDML parser.
    G4VPhysicalVolume* Construct() override;

  private:
    const ::G4GDMLParser& fParser;
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
