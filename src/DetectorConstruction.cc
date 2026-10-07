#include "DetectorConstruction.hh"

#include "G4GDMLParser.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4PhysicalConstants.hh"
#include "G4SDManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4VSolid.hh"

#include "PhantomResponses.hh"
#include "RunSettings.hh"
#include "SensitiveDetector.hh"

#include <string>

namespace
{

constexpr G4bool kAtrisVerbose = false;
constexpr G4int kDiagnosticPrecision = 15;

}  // namespace

namespace atris
{

DetectorConstruction::DetectorConstruction(const ::G4GDMLParser& parser,
                                           const RunSettings& settings,
                                           const PhantomResponses& phantomResponses)
  : G4VUserDetectorConstruction(),
    fParser(parser),
    fSettings(settings),
    fPhantomResponses(phantomResponses)
{
  G4cout << "### AtRIS: Initialized the DetectorConstruction object." << G4endl;
}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
  return fParser.GetWorldVolume();
}
void DetectorConstruction::ConstructSDandField()
{
  G4cout.precision(kDiagnosticPrecision);
  G4cout << "### AtRIS: increased precision to " << kDiagnosticPrecision << ", printing pi=" << pi
         << G4endl;
  G4cout << "### AtRIS: proceeding with detector construction." << G4endl;
  G4SDManager* const sdManager = G4SDManager::GetSDMpointer();
  const G4GDMLAuxMapType* const auxiliaryMap = fParser.GetAuxMap();
  // We now generate the sensitive detectors and assign them to the proper volumes
  // We also count the number of generated sensitive detectors
  for (auto volume = auxiliaryMap->begin(); volume != auxiliaryMap->end(); ++volume)
  {
    for (auto auxiliary = volume->second.begin(); auxiliary != volume->second.end(); ++auxiliary)
    {
      if (auxiliary->type == "SensDet")
      {
        if (kAtrisVerbose)
        {
          G4cout << "SD " << auxiliary->value << " to " << volume->first->GetName() << ", ";
        }
        const G4String detectorName = auxiliary->value;
        const G4int detectorId = std::stoi(detectorName);
        SensitiveDetector* const sensitiveDetector =
          new SensitiveDetector(detectorName, fSettings, fPhantomResponses);
        sdManager->AddNewDetector(sensitiveDetector);
        G4VSensitiveDetector* const detector = sdManager->FindSensitiveDetector(auxiliary->value);
        if (detector)
        {
          G4LogicalVolume* const logicalVolume = volume->first;
          logicalVolume->SetSensitiveDetector(detector);
          // At this point we implement the calculation of volume, mass, surface
          const G4double mass = logicalVolume->GetMass();
          G4VSolid* const solid = logicalVolume->GetSolid();
          const G4double surface = solid->GetSurfaceArea();
          const G4double solidVolume = solid->GetCubicVolume();
          const G4double density = mass / solidVolume;
          // Print detector ID, mass, surface area, volume, and density.
          G4cout << "SDIDr: " << detectorId << ", " << mass / kg << ", " << surface / cm2 << ", "
                 << solidVolume / cm3 << ", " << density / (g / cm3) << G4endl;
          // populating the dictionaries
        }
        else
        {
          G4cout << auxiliary->value << " detector not found" << G4endl;
        }
      }
    }
  }

  // Debugging: printout the new vector data:
  G4cout << "### AtRIS: printing detailed information about all materials" << G4endl;
  if (kAtrisVerbose) G4cout << *(G4Material::GetMaterialTable()) << G4endl;
  G4cout << "### AtRIS: gdml construction complete. In total we have " << fSettings.detectorCount
         << " sensitive detectors" << G4endl;
}

DetectorConstruction::~DetectorConstruction()
{
  ;
}

}  // namespace atris
