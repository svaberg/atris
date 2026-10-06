# Minimal test fixture

The fixture lives in `tests/fixtures/minimal/` in the repository.

This fixture is intentionally structural rather than scientific. The PSF and
GDML describe matching concentric hydrogen layers from 0–1 km and 1–2 km with
sensitive-detector identifiers `0` and `1`, inside a vacuum world. The macros
launch one or two 10 MeV protons from the centre, and the two energy-bin edges
bracket that source energy.

Regression tests copy the repository's reviewed RAMONA response and counting
tables from `phantoms` into a temporary run directory under descriptive
stem-based filenames. They are not duplicated in the fixture directory because
the C++ application requires the full 650-bin response tables even though
detector `0` terminates the test particles before using their response values.
`phantoms.txt` contains the corresponding phantom metadata needed by future
post-processing tests.

The fixture is suitable for checking initialization, macro selection, random
seed selection, exit status, and output file naming. It is not a scientific
baseline and must not be used to validate radiation-response values.
