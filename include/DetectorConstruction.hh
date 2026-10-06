#ifndef DetectorConstruction_hh
#define DetectorConstruction_hh

#include "G4VUserDetectorConstruction.hh"

class G4Material;
class G4GDMLParser;

namespace atris {

class PhantomResponses;
struct RunSettings;

class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    DetectorConstruction(
      const ::G4GDMLParser& parser,
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~DetectorConstruction() override;

    void ConstructSDandField() override;
    G4VPhysicalVolume* Construct() override;

  private:
    const ::G4GDMLParser& fParser;
    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
