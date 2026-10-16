#include "UserActionInitialization.hh"
#include "RunAction.hh"
#include "EventAction.hh"
#include "PrimaryGeneratorAction.hh"
#include "G4ios.hh"

namespace atris {

UserActionInitialization::UserActionInitialization()
{
}

UserActionInitialization::~UserActionInitialization()
{
}



void UserActionInitialization::BuildForMaster() const
{
  auto* const runAction = new RunAction(true);
  SetUserAction(runAction);
}

void UserActionInitialization::Build() const
{
  G4cout << "Starting build of UserActionInitialization for workers" << G4endl;
  auto* const runAction = new RunAction(false);
  SetUserAction(runAction);

  SetUserAction(new EventAction());
  G4cout << "Proceeding with build of UserActionInitialization for workers" << G4endl;
  auto* const primary = new PrimaryGeneratorAction();
  SetUserAction(primary);
}

}  // namespace atris
