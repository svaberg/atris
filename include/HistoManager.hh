#ifndef HistoManager_h
#define HistoManager_h 1

#include "G4String.hh"
#include "G4Types.hh"
#include "globals.hh"

namespace atris {

class PhantomResponses;
struct RunSettings;

/**
 * Defines the analysis objects written by one AtRIS run.
 *
 * Construction books the primary-source, energy-deposition, and configured
 * phantom-response histograms in the current Geant4 analysis manager. Depending
 * on the output mode, it also books metadata, interface-crossing, and transport-
 * step ntuples. Geant4 owns the booked analysis objects.
 *
 * RunSettings and PhantomResponses are borrowed and must outlive this object.
 */
class HistoManager
{
  public:
    /// Books all histograms and ntuples required by the resolved run settings.
    HistoManager(
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~HistoManager();

    /// Writes run and response definitions to the metadata ntuples.
    void FillMetadata() const;

  private:
    void Book() const;

    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
