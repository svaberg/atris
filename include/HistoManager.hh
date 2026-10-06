#ifndef HistoManager_h
#define HistoManager_h 1

#include "G4String.hh"
#include "G4Types.hh"
#include "globals.hh"

namespace atris {

class PhantomResponses;
struct RunSettings;

class HistoManager
{
  public:
    HistoManager(
      const RunSettings& settings,
      const PhantomResponses& phantomResponses
    );
    ~HistoManager();
    void FillMetadata() const;

  private:
    void Book() const;

    const RunSettings& fSettings;
    const PhantomResponses& fPhantomResponses;
};

}  // namespace atris

#endif
