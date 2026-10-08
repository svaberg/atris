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

constexpr G4bool kDebugLogging = ATRIS_DEBUG_LOGGING;
constexpr G4int kDiagnosticPrecision = 15;

}  // namespace

namespace atris
{

DetectorConstruction::DetectorConstruction(const ::G4GDMLParser& parser,
                                           const RunSettings& settings,
                                           const PhantomResponses& phantomResponses)
  : fParser(parser), fSettings(settings), fPhantomResponses(phantomResponses)
{
  if constexpr (kDebugLogging)
  {
    G4debug << "### AtRIS: Initialized the DetectorConstruction object." << G4endl;
  }
}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
  return fParser.GetWorldVolume();
}
void DetectorConstruction::ConstructSDandField()
{
  if constexpr (kDebugLogging)
  {
    G4debug.precision(kDiagnosticPrecision);
    G4debug << "### AtRIS: increased precision to " << kDiagnosticPrecision
            << ", printing pi=" << pi << G4endl;
    G4debug << "### AtRIS: proceeding with detector construction." << G4endl;
  }
  G4SDManager* const sdManager = G4SDManager::GetSDMpointer();
  const G4GDMLAuxMapType* const auxiliaryMap = fParser.GetAuxMap();
  // Attach one SensitiveDetector to each GDML volume marked SensDet.
  for (auto volume = auxiliaryMap->begin(); volume != auxiliaryMap->end(); ++volume)
  {
    for (auto auxiliary = volume->second.begin(); auxiliary != volume->second.end(); ++auxiliary)
    {
      if (auxiliary->type == "SensDet")
      {
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
          if constexpr (kDebugLogging)
          {
            const G4double mass = logicalVolume->GetMass();
            G4VSolid* const solid = logicalVolume->GetSolid();
            const G4double surface = solid->GetSurfaceArea();
            const G4double solidVolume = solid->GetCubicVolume();
            const G4double density = mass / solidVolume;
            G4debug << "SD " << detectorId << " attached to " << logicalVolume->GetName()
                    << ": mass=" << mass / kg << " kg, area=" << surface / cm2
                    << " cm2, volume=" << solidVolume / cm3
                    << " cm3, density=" << density / (g / cm3) << " g/cm3" << G4endl;
          }
        }
        else
        {
          G4cout << auxiliary->value << " detector not found" << G4endl;
        }
      }
    }
  }

  if constexpr (kDebugLogging)
  {
    G4debug << "### AtRIS: detailed information about all materials" << G4endl;
    G4debug << *(G4Material::GetMaterialTable()) << G4endl;
  }
  G4cout << "### AtRIS: gdml construction complete. In total we have " << fSettings.detectorCount
         << " sensitive detectors" << G4endl;
}

}  // namespace atris
