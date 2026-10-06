#ifndef PhantomResponseSchema_hh
#define PhantomResponseSchema_hh 1

#include "globals.hh"

namespace atris {

// Each particle row in a phantom response table contains 650 coefficients on
// a log10(eV) energy grid with a spacing of 0.02 decades.
constexpr G4int kPhantomResponseEnergyBins = 650;
constexpr G4double kPhantomResponseLogEnergyStep = 0.02;

// The historical response lookup is an array indexed directly by signed PDG
// code. Its exclusive bound 2214 includes proton and antiproton (PDG +/-2212)
// while leaving one unused slot at each end. Sparse ion PDG codes are stored
// separately rather than making this array enormous.
constexpr G4int kLightParticlePDGLimit = 2214;
constexpr G4int kLightParticlePDGOffset = kLightParticlePDGLimit - 1;
constexpr G4int kLightParticleLookupSize = 2 * kLightParticlePDGOffset + 1;

// The ion response table starts with deuterons. Protons use the ordinary PDG
// code 2212 and are handled by the dense light-particle lookup above.
constexpr G4int kFirstSupportedIonPDG = 1000010020;

constexpr G4int kPhotonPDG = 22;
constexpr G4int kNeutralPionPDG = 111;
constexpr G4int kNeutronPDG = 2112;
constexpr G4int kProtonPDG = 2212;

// H2 histogram IDs are assigned in HistoManager::Book() in this order.
constexpr G4int kIonizingEnergyHistogramId = 2;
constexpr G4int kTotalEnergyHistogramId = 3;
constexpr G4int kFirstResponseHistogramId = 4;

}  // namespace atris

#endif
