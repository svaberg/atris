#ifndef AnalysisOutput_hh
#define AnalysisOutput_hh 1

#include "G4String.hh"
#include "G4Types.hh"
#include "globals.hh"

namespace atris
{

class PhantomResponses;
struct RunSettings;

/**
 * Defines the analysis objects written by one AtRIS run.
 *
 * Construction books the primary-source, energy-deposition, and configured
 * phantom-response histograms in the current Geant4 analysis manager. It also
 * books run and response metadata ntuples and, depending on the output mode,
 * interface-crossing and transport-step ntuples. Geant4 owns the booked objects.
 *
 * RunSettings and PhantomResponses are borrowed and must outlive this object.
 */
class AnalysisOutput
{
  public:
    /// Books all histograms and ntuples required by the resolved run settings.
    AnalysisOutput(const RunSettings& settings, const PhantomResponses& phantomResponses);
    ~AnalysisOutput();

    /// Writes run and response definitions to the metadata ntuples.
    void FillMetadata() const;

  private:
    /// Books source, deposition, and phantom-response histograms in ID order.
    void BookHistograms() const;

    /// Books metadata and optional particle-record ntuples in ID order.
    void BookNtuples() const;

    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
