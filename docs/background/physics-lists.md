# Geant4 physics lists

A Geant4 physics list selects the particle processes and interaction models
used during transport. It is part of the physical simulation definition,
independent of the number of threads, chunks, or scheduler nodes.

AtRIS obtains the named reference list from Geant4 and registers step-limiter
physics. The macro generator defaults to `FTFP_BERT_HP` and records the choice
in each species macro. Choosing the list and recording it with the model are
part of [simulation preparation](../running-atris/prepare-simulation.md#record-physics-and-output-choices).

The available lists and their detailed configuration depend on the installed
Geant4 version. See the official [Physics List Guide](https://geant4.web.cern.ch/documentation/dev/plg_html/PhysicsListGuide/physicslistguide.html).

## What the default name means

`FTFP_BERT` combines a high-energy hadronic model with the Bertini cascade and
includes electromagnetic processes. The `_HP` variant uses evaluated neutron
data and high-precision models at neutron energies of 20 MeV and below.
This can matter even for a high-energy primary source, because transport can
produce low-energy secondary neutrons. The [Geant4 description of FTFP_BERT](https://geant4.web.cern.ch/documentation/pipelines/master/plg_html/PhysicsListGuide/reference_PL/FTFP_BERT.html)
details the components and variants.

The default is a starting configuration, not proof of suitability for every
planet or observable. Check the species and energies of both primaries and
secondaries relevant to the calculation, the target materials, and the
processes that dominate the requested response.

## Production thresholds and tracking

A production threshold controls when certain secondary particles are created
explicitly. It is not a general instruction to stop every particle below that
energy. Geant4 converts range cuts into material-dependent energy thresholds;
tracking limits and particle termination are separate concepts. See
[production thresholds versus tracking cuts](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/thresholdVScut.html).

AtRIS's terminating inner and outer layers are geometry-specific boundaries.
Do not confuse them with the physics list's production thresholds.

## Compare physics consistently

For a model comparison, use separate run directories and change the physics
list while keeping geometry, source sampling, phantom selection, and analysis
consistent. Collect enough histories that Monte Carlo noise does not obscure
the difference. Do not gather chunks produced with different physics settings
into a single response table.

Record the AtRIS and Geant4 versions, physics-list name, installed data-library
versions, and any macro settings that modify cuts or processes. Changing only
the list's name in a note does not update existing results; the simulation must
be rerun with the intended configuration.

## Implementation

`atris_tools/atrismacrogen.py` writes the macro setting, and `src/main.cc`
constructs the selected physics list.
