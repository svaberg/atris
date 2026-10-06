#ifndef DetectorConstruction_hh
#define DetectorConstruction_hh

#include "G4VUserDetectorConstruction.hh"

class G4Material;
class G4GDMLParser;

namespace atris {

struct RunSettings;

class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    DetectorConstruction(
      const ::G4GDMLParser& parser,
      const RunSettings& settings
    );
    ~DetectorConstruction() override;

    void ConstructSDandField() override;
    G4VPhysicalVolume* Construct() override;

  private:
    const ::G4GDMLParser& fParser;
    const RunSettings& fSettings;
};

}  // namespace atris

#endif
