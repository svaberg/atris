#include "UserActionInitialization.hh"
#include "RunAction.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunSettings.hh"
#include "G4ios.hh"

namespace atris {

UserActionInitialization::UserActionInitialization(const RunSettings& settings)
  : fSettings(settings)
{
}

UserActionInitialization::~UserActionInitialization()
{
}



void UserActionInitialization::BuildForMaster() const
{
  auto* const runAction = new RunAction(true, fSettings);
  SetUserAction(runAction);
}

void UserActionInitialization::Build() const
{
  G4cout << "Starting build of UserActionInitialization for workers" << G4endl;
  auto* const runAction = new RunAction(false, fSettings);
  SetUserAction(runAction);

 
  G4cout << "Proceeding with build of UserActionInitialization for workers" << G4endl;
  auto* const primary = new PrimaryGeneratorAction();
  SetUserAction(primary);
}

}  // namespace atris
