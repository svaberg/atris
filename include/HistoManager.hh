#ifndef HistoManager_h
#define HistoManager_h 1

#include "globals.hh"
#include "G4Types.hh"
#include "G4String.hh"

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
