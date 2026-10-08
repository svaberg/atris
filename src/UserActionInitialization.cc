#include "UserActionInitialization.hh"

#include "G4ios.hh"

#include "PhantomResponses.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"
#include "RunSettings.hh"

namespace atris
{

UserActionInitialization::UserActionInitialization(const RunSettings& settings,
                                                   const PhantomResponses& phantomResponses)
  : fSettings(settings), fPhantomResponses(phantomResponses)
{}

void UserActionInitialization::BuildForMaster() const
{
  auto* const runAction = new RunAction(true, fSettings, fPhantomResponses);
  SetUserAction(runAction);
}

void UserActionInitialization::Build() const
{
  G4debug << "Starting build of UserActionInitialization for workers" << G4endl;
  auto* const runAction = new RunAction(false, fSettings, fPhantomResponses);
  SetUserAction(runAction);

  G4debug << "Proceeding with build of UserActionInitialization for workers" << G4endl;
  auto* const primary = new PrimaryGeneratorAction();
  SetUserAction(primary);
}

}  // namespace atris
