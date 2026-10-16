"""Compare fixed-size phantom statistics with detailed shower records."""

import numpy as np
import pytest
import uproot

from test_atris_command import atris_command, invoke_atris
from atris_tools.phantom_statistics import (
    PhantomEvents,
    PhantomStatistics,
    read_phantom_statistics,
)
from atris_tools.phantom_builder import prepare_phantom_batch
from atris_tools.histogram import ResponseHistogramReader

from phantom_fixture import water_psf
from atris_tools.psf import PSF

EVENTS = 64


def prepare_phantom(directory, particle, *, miss=False, events=EVENTS, psf=None):
    directory.mkdir()
    radius = 4e-4
    prepare_phantom_batch(directory, [0.001, 10], psf_path=water_psf(radius) if psf is None else psf, particle=particle,
                          events_per_chunk=events, production_cut_mm=0.00001,
                          tracking_floor_eV=1)
    macro = directory / "phantom.chunk.mac"
    macro.write_text(macro.read_text().replace("/run/beamOn",
        "/gps/pos/type Point\n"
        f"/gps/pos/centre {1.5 * radius if miss else 0} 0 {-1.1 * radius} cm\n"
        "/run/beamOn"))
    (directory / "phantom.mac").symlink_to(macro.name)


@pytest.mark.regression
@pytest.mark.parametrize("particle", ("proton", "e-", "gamma", "neutron", "alpha"))
@pytest.mark.parametrize("threads", ("1", "2"))
def test_phantom_matches_shower_and_retains_per_bin_statistics(
    tmp_path, atris_command, particle, threads
):
    outputs = {}
    sizes = {}
    for mode in ("1", "phantom"):
        directory = tmp_path / mode
        prepare_phantom(directory, particle)
        result = invoke_atris(
            atris_command,
            directory,
            "FTFP_BERT_HP",
            "phantom_123456_654321.root",
            mode,
            "0",
            threads=threads,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        if mode == "phantom":
            assert "Processing event:" not in result.stdout
        path = directory / "phantom_123456_654321.root"
        sizes[mode] = path.stat().st_size
        with uproot.open(path) as root:
            if mode == "1":
                steps = root["steps"].arrays(library="np")
                ids = steps["event_id"]
                water = steps["detector_id"] == 1
                incident = np.zeros(EVENTS)
                np.maximum.at(incident, ids, steps["primary_energy_MeV"])
                deposited = np.bincount(
                    ids[water],
                    weights=steps["energy_deposit_MeV"][water],
                    minlength=EVENTS,
                )
                ionizing = np.bincount(
                    ids[water],
                    weights=(
                        steps["energy_deposit_MeV"]
                        - steps["nonionizing_energy_deposit_MeV"]
                    )[water],
                    minlength=EVENTS,
                )
                outputs[mode] = PhantomStatistics.from_events(
                    PhantomEvents(incident, deposited, ionizing)
                )
                for name, totals in (("h2.ion", ionizing), ("h2.edep", deposited)):
                    companion = root[name + ".primary"]
                    axes = [axis.edges(flow=True) for axis in companion.axes]
                    expected = np.histogram2d(incident, np.ones(EVENTS), bins=axes,
                                              weights=totals**2)[0]
                    np.testing.assert_allclose(companion.variances(flow=True), expected,
                        rtol=1e-12, atol=1e-20)
                    np.testing.assert_allclose(companion.values(flow=True),
                                               root[name].values(flow=True), rtol=1e-12)
                    if particle in ("proton", "e-", "alpha"):
                        assert np.sum(expected) > np.sum(root[name].variances(flow=True))
                    with ResponseHistogramReader(path.with_suffix("")) as reader:
                        variance = reader.mean_variance(name)
                    # Compare the reported mean variance with the sample variance
                    # of the primary totals reconstructed from diagnostic records.
                    bins = np.searchsorted(companion.axes[0].edges(), incident, side="right")
                    sensor_bin = np.searchsorted(companion.axes[1].edges(), 1, side="right")
                    for energy_bin in np.flatnonzero(root["h1.1"].values(flow=True) > 1):
                        samples = totals[bins == energy_bin]
                        assert len(samples) == root["h1.1"].values(flow=True)[energy_bin]
                        # The raw-moment formula loses precision when subtracting
                        # nearly equal numbers; scale its roundoff bound by Q.
                        roundoff = (32 * np.finfo(float).eps * expected[energy_bin, sensor_bin]
                                    / (len(samples) * (len(samples) - 1)))
                        assert variance[energy_bin, sensor_bin] == pytest.approx(
                            np.var(samples, ddof=1) / len(samples), rel=1e-10, abs=roundoff)
            else:
                assert not {"steps", "interfaces", "phantom_events"} & set(
                    root.keys(cycle=False)
                )
                assert root["metadata"]["output_mode"].array(library="np").tolist() == [
                    3
                ]
                assert len(root["h2.fraction"].member("fSumw2")) > 0
                outputs[mode] = read_phantom_statistics(path)
                stats = outputs[mode]
                assert stats.sample_counts.sum() == EVENTS
                assert np.all(stats.detected_counts <= stats.sample_counts)
                assert np.all(stats.squared_deviations >= 0)
    # Repeated shower-only MT runs also differ in their event streams. Compare
    # exact transport histories serially; above checks cover merged MT scoring.
    if threads == "1":
        for field in PhantomStatistics.__dataclass_fields__:
            np.testing.assert_allclose(
                getattr(outputs["phantom"], field),
                getattr(outputs["1"], field),
                rtol=1e-12,
                atol=1e-14,
            )
    assert sizes["phantom"] < sizes["1"]


@pytest.mark.regression
def test_layered_phantom_scores_only_sensor_deposit_per_primary(tmp_path, atris_command):
    psf = PSF(inner_radius_km=[0, 2e-9], outer_radius_km=[2e-9, 4e-9],
              temperature_k=293, density_g_cm3=[2.7, 1.8], pressure_pa=0,
              mass_fractions={"Al": [1, 0], "C": [0, 1]}, state="solid")
    outputs = {}
    for mode in ("1", "phantom"):
        directory = tmp_path / mode
        prepare_phantom(directory, "proton", psf=psf)
        macro = directory / "phantom.chunk.mac"
        macro.write_text(macro.read_text().replace(
            "/gps/ene/type Pow", "/gps/ene/type Mono\n/gps/ene/mono 1 MeV"))
        result = invoke_atris(atris_command, directory, "FTFP_BERT_HP",
                              "phantom_123456_654321.root", mode, "0", threads="1")
        assert result.returncode == 0, result.stdout + result.stderr
        path = directory / "phantom_123456_654321.root"
        with uproot.open(path) as root:
            assert root["h1.1"].member("fEntries") == EVENTS
            if mode == "phantom":
                assert root["h2.fraction"].member("fEntries") == EVENTS
                outputs[mode] = read_phantom_statistics(path)
            else:
                steps = root["steps"].arrays(library="np")
                assert set(steps["detector_id"]) <= {0, 1, 2}
                sensor = steps["detector_id"] == 1
                deposited = np.bincount(steps["event_id"][sensor],
                    weights=steps["energy_deposit_MeV"][sensor], minlength=EVENTS)
                ionizing = np.bincount(steps["event_id"][sensor],
                    weights=(steps["energy_deposit_MeV"] - steps["nonionizing_energy_deposit_MeV"])[sensor],
                    minlength=EVENTS)
                # Monoenergetic source gives the exact energy even for primaries
                # absorbed in passive shielding, which leave no detector steps.
                outputs[mode] = PhantomStatistics.from_events(
                    PhantomEvents(np.ones(EVENTS), deposited, ionizing))
    for field in PhantomStatistics.__dataclass_fields__:
        np.testing.assert_allclose(getattr(outputs["1"], field),
                                   getattr(outputs["phantom"], field), rtol=1e-12, atol=1e-14)
    unshielded = PSF.from_layers(psf.layers.copy(), psf.materials)
    from atris_tools.psf import DENSITY
    unshielded.layers[1, DENSITY] = 1e-25
    directory = tmp_path / "vacuum"
    prepare_phantom(directory, "proton", psf=unshielded)
    macro = directory / "phantom.chunk.mac"
    macro.write_text(macro.read_text().replace(
        "/gps/ene/type Pow", "/gps/ene/type Mono\n/gps/ene/mono 1 MeV"))
    result = invoke_atris(atris_command, directory, "FTFP_BERT_HP",
                          "phantom_123456_654321.root", "phantom", "0", threads="1")
    assert result.returncode == 0, result.stdout + result.stderr
    without_shield = read_phantom_statistics(directory / "phantom_123456_654321.root")
    assert not np.allclose(without_shield.mean_fraction, outputs["phantom"].mean_fraction, equal_nan=True)


@pytest.mark.regression
def test_phantom_counts_primaries_that_never_enter_water(tmp_path, atris_command):
    directory = tmp_path / "miss"
    prepare_phantom(directory, "proton", miss=True)
    result = invoke_atris(
        atris_command,
        directory,
        "FTFP_BERT_HP",
        "phantom",
        "phantom",
        "0",
        threads="2",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    stats = read_phantom_statistics(directory / "phantom.root")
    assert stats.sample_counts.sum() == EVENTS
    assert not np.any(stats.mean_fraction)
    assert not np.any(stats.squared_deviations)
    assert not np.any(stats.detected_counts)
    with pytest.raises(ValueError, match="zero counting threshold"):
        read_phantom_statistics(directory / "phantom.root", threshold_MeV=0.001)
    with uproot.open(directory / "phantom.root") as root:
        assert root["h1.1"].member("fEntries") == EVENTS
    with ResponseHistogramReader(directory / "phantom") as reader:
        sampled = reader["h1.1"].values > 1
        assert sampled.any()
        np.testing.assert_array_equal(reader.mean_variance("h2.ion")[sampled], 0)


@pytest.mark.regression
def test_phantom_output_does_not_store_records_per_primary(tmp_path, atris_command):
    sizes = []
    for events in (64, 65000):
        directory = tmp_path / str(events)
        prepare_phantom(directory, "proton", events=events)
        result = invoke_atris(
            atris_command,
            directory,
            "FTFP_BERT_HP",
            "phantom",
            "phantom",
            "0",
            threads="2",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        path = directory / "phantom.root"
        stats = read_phantom_statistics(path)
        assert stats.sample_counts.sum() == events
        assert stats.sample_counts.shape == (650,)
        with uproot.open(path) as root:
            trees = {
                name
                for name, cls in root.classnames(cycle=False).items()
                if cls == "TTree"
            }
            assert trees == {"metadata"}
        sizes.append(path.stat().st_size)
    # Compression changes with occupied bins, but not one record per primary.
    assert sizes[1] < 3 * sizes[0]
