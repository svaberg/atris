#ifndef OutputMode_hh
#define OutputMode_hh 1

#include "globals.hh"

namespace atris {

// Response mode records aggregate histograms. Interface mode also records
// crossings, and step mode additionally records every transport step.
enum class OutputMode : G4int
{
  kResponse = -1,
  kInterface = 0,
  kStep = 1,
  kInvalid = 2
};

constexpr G4bool WritesInterfaceNtuple(const OutputMode outputMode)
{
	return outputMode == OutputMode::kInterface || outputMode == OutputMode::kStep;
}

constexpr G4bool WritesStepNtuple(const OutputMode outputMode)
{
	return outputMode == OutputMode::kStep;
}

}  // namespace atris

#endif
