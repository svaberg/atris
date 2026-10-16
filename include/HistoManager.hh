#ifndef HistoManager_h
#define HistoManager_h 1

#include "globals.hh"
#include "G4Types.hh"
#include "G4String.hh"

namespace atris {

class HistoManager
{
  public:
    HistoManager();
    ~HistoManager();
    void FillMetadata() const;

  private:
    void Book() const;
    void BookPrimaryMoments() const;
};

}  // namespace atris

#endif
