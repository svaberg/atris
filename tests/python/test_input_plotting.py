from unittest.mock import Mock

import numpy as np

from atris_tools import input_plotting


MACRO = """\
/atris/geometryFile protons.gdml
/atris/energyBinsFile protons.bins
/atris/outputFile protons
/atris/phantom/response test-phantom dos energy test-phantom_response.txt
/atris/phantom/response test-phantom equi radiation-weighted-energy test-phantom_response.txt
/atris/phantom/response test-phantom rates coefficient test-phantom_counting.txt
/gps/particle proton
/gps/ene/type User
/gps/hist/type energy
/gps/hist/point 1 0
/gps/hist/point 10 1
/gps/hist/point 100 1
/gps/pos/type Surface
/gps/pos/shape Sphere
/gps/pos/radius 7000 km
/gps/ang/type cos
/gps/ang/mintheta 0 deg
/gps/ang/maxtheta 90 deg
/gps/number 1
/run/setCut 100 m
/atris/randomSeeds 123 456
/run/beamOn 10
"""


def prepare_inputs(run_directory, gdml_text):
    (run_directory / "protons.gdml").write_text(gdml_text)
    (run_directory / "protons.mac").write_text(MACRO)
    np.savetxt(run_directory / "protons.bins", [1, 10, 100])
    (run_directory / "phantoms.txt").write_text(
        "test-phantom  1.0  2.0\n"
    )

    response = np.vstack(
        (
            np.linspace(0.0, 1.0, 650),
            np.linspace(1.0, 2.0, 650),
        )
    )
    for suffix in ("response", "counting"):
        filename = run_directory / ("test-phantom_" + suffix + ".txt")
        filename.write_text("22 2212\n")
        with filename.open("a") as phantom_file:
            np.savetxt(phantom_file, response)


def test_read_macro_and_atmosphere(tmp_path, gdml_text):
    (tmp_path / "protons.mac").write_text(MACRO)
    (tmp_path / "protons.gdml").write_text(gdml_text)

    settings, energy_points = input_plotting.read_macro(tmp_path / "protons.mac")
    all_layers = input_plotting.read_layers(tmp_path / "protons.gdml")

    assert settings["/gps/particle"] == "proton"
    np.testing.assert_allclose(energy_points, [[1, 0], [10, 1], [100, 1]])
    assert all_layers[1]["fractions"] == {"G4_N": 0.75, "G4_O": 0.25}
    assert [layer["detector_id"] for layer in all_layers] == [1, 2, 3]
    assert [layer["state"] for layer in all_layers] == ["solid", "gas", "gas"]
    assert input_plotting.surface_radius(all_layers) == 6371.0
    detector_ids, positions, edges = input_plotting.shell_coordinates(
        all_layers, [2, 3]
    )
    np.testing.assert_array_equal(detector_ids, [2, 3])
    np.testing.assert_allclose(positions, [0.5, 2.0])
    np.testing.assert_allclose(edges, [0.0, 1.0, 3.0])


def test_non_termination_layers_accept_every_intermediate_material_type():
    layers = [
        {"detector_id": 0, "state": "solid"},
        {"detector_id": 1, "state": "solid"},
        {"detector_id": 2, "state": "liquid"},
        {"detector_id": 3, "state": "gas"},
        {"detector_id": 4, "state": "solid"},
    ]

    selected = input_plotting.non_termination_layers(layers)

    assert [layer["detector_id"] for layer in selected] == [1, 2, 3]


def test_particle_name_translates_standard_particles_and_nuclei():
    assert input_plotting.particle_name(22) == "photon"
    assert input_plotting.particle_name(-11) == "positron"
    assert input_plotting.particle_name(1000020040) == "He-4"
    assert input_plotting.particle_name(1000260560) == "Fe-56"


def test_particle_symbol_uses_compact_pdg_notation():
    assert input_plotting.particle_symbol(22) == r"$\gamma$"
    assert input_plotting.particle_symbol(12) == r"$\nu_e$"
    assert input_plotting.particle_symbol(-11) == r"$e^{+}$"
    assert input_plotting.particle_symbol(1000020040) == r"$^{4}\mathrm{He}$"


def test_elements_are_labelled_and_sorted_by_atomic_number():
    references = ["G4_Si", "custom", "G4_O", "G4_H", "G4_He"]

    ordered = sorted(references, key=input_plotting.element_sort_key)

    assert ordered == ["G4_H", "G4_He", "G4_O", "G4_Si", "custom"]
    assert [input_plotting.element_label(reference) for reference in ordered] == [
        "H",
        "He",
        "O",
        "Si",
        "custom",
    ]


def test_shell_profiles_share_density_pressure_axis_and_twin_temperature_axis():
    axis = Mock()
    temperature_axis = Mock()
    temperature_axis.get_ylim.return_value = (-0.15, 3.15)
    density = np.array([1.0, 2.0])
    pressure = np.array([10.0, 20.0])
    temperature = np.array([250.0, 300.0])
    edges = np.array([0.0, 1.0, 3.0])

    input_plotting._plot_shell_profiles(
        axis,
        temperature_axis,
        density,
        pressure,
        temperature,
        edges,
        edges,
    )

    assert axis.stairs.call_count == 2
    np.testing.assert_array_equal(axis.stairs.call_args_list[0].args[0], density)
    np.testing.assert_array_equal(axis.stairs.call_args_list[1].args[0], pressure)
    np.testing.assert_array_equal(
        temperature_axis.stairs.call_args.args[0], temperature
    )
    for call in axis.stairs.call_args_list + [temperature_axis.stairs.call_args]:
        np.testing.assert_array_equal(call.args[1], edges)
        assert call.kwargs["orientation"] == "horizontal"
    axis.set_yscale.assert_called_once_with("linear")
    axis.set_xscale.assert_called_once_with("log")
    axis.minorticks_on.assert_called_once_with()
    temperature_axis.minorticks_on.assert_called_once_with()
    axis.legend.assert_not_called()
    temperature_axis.legend.assert_called_once()
    temperature_axis.set_ylim.assert_called_once_with((-0.15, 3.15))
    assert [
        call.args[0] for call in temperature_axis.axhline.call_args_list
    ] == [0.0, 3.0]
    assert [call.args[2] for call in temperature_axis.text.call_args_list] == [
        "Ground",
        "Space",
    ]
    assert [call.args[1] for call in temperature_axis.text.call_args_list] == [
        -0.075,
        3.075,
    ]
    assert all(
        call.kwargs == {"color": "black", "zorder": 10}
        for call in temperature_axis.axhline.call_args_list
    )
    method_names = [call[0] for call in temperature_axis.method_calls]
    assert max(
        index for index, name in enumerate(method_names) if name == "axhline"
    ) < method_names.index("set_ylim")
    assert method_names.index("set_ylim") < method_names.index("stairs")


def test_source_summary_explains_radius_and_atmosphere_clearance():
    settings = {
        "/gps/particle": "proton",
        "/gps/pos/type": "Surface",
        "/gps/pos/shape": "Sphere",
        "/gps/pos/radius": "7421.001 km",
        "/gps/ang/type": "cos",
        "/gps/ang/mintheta": "0 deg",
        "/gps/ang/maxtheta": "90 deg",
        "/run/setCut": "100 m",
    }
    layers = [
        {
            "detector_id": 0,
            "state": "solid",
            "rmin": 0.0,
            "rmax": 6370.98,
        },
        {
            "detector_id": 1,
            "state": "solid",
            "rmin": 6370.98,
            "rmax": 6371.0,
        },
        {
            "detector_id": 2,
            "state": "gas",
            "rmin": 6371.0,
            "rmax": 7421.0,
        },
        {
            "detector_id": 3,
            "state": "solid",
            "rmin": 7421.001,
            "rmax": 7421.021,
        },
    ]

    summary = input_plotting._source_summary(settings, layers, 121)

    assert "Planet surface radius: 6371.000 km" in summary
    assert "Modeled shell outer radius: 7421.000 km" in summary
    assert "Modeled layers: 2" in summary
    assert "Source sphere radius: 7421.001 km" in summary
    assert "Altitude above surface: 1050.001 km" in summary
    assert "Model clearance: 1.000 m" in summary
    assert "Configured energies: 121" in summary
    assert "Direction: inward cosine law" in summary
    assert "Secondary production range cut: 100 m" in summary


def test_particle_groups_include_every_particle_once():
    particle_codes = np.array(
        [22, 2212, 2112, -2112, 11, -11, 1000010020, 1000030070]
    )

    groups = input_plotting._particle_groups(particle_codes)

    assert groups == ([0, 1, 2, 3, 4, 5], [6, 7])


def test_plot_inputs_writes_species_and_phantom_pngs(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == [
        "protons.inputs.png",
        "phantom.test-phantom.inputs.png",
    ]
    assert errors == []
    for filename in filenames:
        assert (tmp_path / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


PSF = """\
H1000 H
0 1 0 6.283185 0 3.141593 0 293 2.7 101325 1 0
1 2 0 6.283185 0 3.141593 1 293 2.7 101325 1 0
2 3 0 6.283185 0 3.141593 2 250 0.001 50000 0 1
3.001 3.021 0 6.283185 0 3.141593 3 293 2.7 101325 1 0
"""


def test_plot_inputs_writes_planet_specification_without_species_inputs(
    tmp_path, monkeypatch
):
    (tmp_path / "simulation.psf").write_text(PSF)
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == ["simulation.psf.png"]
    assert errors == []
    assert (tmp_path / "simulation.psf.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )


def test_plot_inputs_writes_planet_specification_alongside_species_inputs(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    (tmp_path / "simulation.psf").write_text(PSF)
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == [
        "protons.inputs.png",
        "simulation.psf.png",
        "phantom.test-phantom.inputs.png",
    ]
    assert errors == []


def test_plot_inputs_reports_missing_phantom_response_but_keeps_species_plot(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    (tmp_path / "test-phantom_counting.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == ["protons.inputs.png"]
    assert errors == [
        "phantom test-phantom inputs: missing test-phantom_counting.txt"
    ]


def test_plot_inputs_uses_macro_stem_without_phantom_metadata(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    (tmp_path / "phantoms.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == [
        "protons.inputs.png",
        "phantom.test-phantom.inputs.png",
    ]
    assert errors == []
