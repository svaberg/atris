#ifndef HistoManager_h
#define HistoManager_h 1

#include "G4String.hh"
#include "G4Types.hh"
#include "globals.hh"

namespace atris {

struct RunSettings;

class HistoManager
{
  public:
    explicit HistoManager(const RunSettings& settings);
    ~HistoManager();
    void FillMetadata() const;

  private:
    void Book() const;

    const RunSettings& fSettings;
};

}  // namespace atris

#endif
