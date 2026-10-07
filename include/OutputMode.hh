#ifndef OutputMode_hh
#define OutputMode_hh 1

#include "globals.hh"

namespace atris {

// Response mode records aggregate histograms. Interface mode also records
// crossings, and step mode additionally records every transport step.
enum class OutputMode
{
  kResponse,
  kProfile,
  kShower,
  kInvalid
};

constexpr const char* OutputModeName(const OutputMode outputMode)
{
	switch (outputMode) {
		case OutputMode::kResponse: return "response";
		case OutputMode::kProfile: return "profile";
		case OutputMode::kShower: return "shower";
		case OutputMode::kInvalid: return "invalid";
	}
	return "invalid";
}

constexpr G4bool WritesInterfaceNtuple(const OutputMode outputMode)
{
	return outputMode == OutputMode::kProfile || outputMode == OutputMode::kShower;
}

constexpr G4bool WritesStepNtuple(const OutputMode outputMode)
{
	return outputMode == OutputMode::kShower;
}

}  // namespace atris

#endif
