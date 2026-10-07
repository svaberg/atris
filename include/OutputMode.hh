#ifndef OutputMode_hh
#define OutputMode_hh 1

#include "globals.hh"

namespace atris
{

/**
 * Selects how much simulation detail AtRIS records.
 *
 * `kResponse` records aggregate histograms only. `kProfile` also records each
 * particle crossing of a layer interface. `kShower` additionally records every
 * transport step and can therefore produce very large output. `kInvalid` is the
 * uninitialized state used before RunConfiguration resolves the macro setting.
 */
enum class OutputMode
{
  kResponse,
  kProfile,
  kShower,
  kInvalid
};

/// Returns the stable name used by macros and output metadata.
constexpr const char* OutputModeName(const OutputMode outputMode)
{
  switch (outputMode)
  {
    case OutputMode::kResponse:
      return "response";
    case OutputMode::kProfile:
      return "profile";
    case OutputMode::kShower:
      return "shower";
    case OutputMode::kInvalid:
      return "invalid";
  }
  return "invalid";
}

/// Returns whether the mode records layer-interface crossings.
constexpr G4bool WritesInterfaceNtuple(const OutputMode outputMode)
{
  return outputMode == OutputMode::kProfile || outputMode == OutputMode::kShower;
}

/// Returns whether the mode records every particle transport step.
constexpr G4bool WritesStepNtuple(const OutputMode outputMode)
{
  return outputMode == OutputMode::kShower;
}

}  // namespace atris

#endif
