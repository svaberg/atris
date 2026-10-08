# Known bugs

This page records unresolved defects and possible bugs awaiting confirmation.

## Possible radiation-weighting bug

The radiation weights in `src/SensitiveDetector.cc` resemble the prescription
in [ICRP Publication 103](https://www.maff.go.jp/e/policies/market/reference/attach/pdf/reference-25.pdf),
Table 2 and Equation 4.3, but differ in three places:

- The low-energy neutron branch starts with `3.5`, whereas the ICRP formula
  starts with `2.5`.
- Each neutron branch squares the energy expression inside the logarithm,
  producing $\ln(x^2)$ rather than $(\ln x)^2$. Here $x$ is the branch's
  dimensionless energy expression: $e$, $2e$, or $0.04e$, with
  $e=E_{\mathrm{kin}}/(1\,\mathrm{MeV})$. These are different functions, not
  equivalent ways of writing the same formula.
- The pion condition applies weight `2` to neutral pions (PDG `111`), not
  charged pions (PDG `211` and `-211`), which are the pions specified by ICRP.

These differences are present in the first source import, commit `112e4dc`
(`From zip file`). If ICRP 103 is the intended prescription, they are possible
formula-transcription and particle-selection bugs. The intended prescription
has not yet been confirmed, and the calculation remains unchanged.

The affected outputs are response channels with
`/atris/phantom/response/scaleByRadiationWeight true`, including the generated
`equi` response. These factors do not change Geant4 particle transport,
unweighted energy-deposition tallies, or response channels with radiation
weighting disabled. See [radiation weighting as implemented](reference/outputs.md#radiation-weighting-as-implemented)
for the exact current formula.
