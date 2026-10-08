import numpy as np
import pytest

from atris_tools.psf import (
    DETECTOR_ID,
    STATE,
    FIRST_ELEMENT,
    GEOMETRY_COLUMNS,
    build_psf,
    load_psf,
    read_psf_header,
    read_psf_layers,
    write_psf,
)


def test_build_and_write_named_layers(tmp_path):
    psf = build_psf(
        inner_radius_km=[0, 1, 2, 3.001],
        outer_radius_km=[1, 2, 3, 3.021],
        temperature_k=300,
        density_g_cm3=[2.7, 0.001, 1, 2.7],
        pressure_pa=1e5,
        state=["solid", "gas", "liquid", "solid"],
        mass_fractions={"O": [0, 0.2, 1, 0], "N": [0, 0.8, 0, 0]},
        solid_composition="O533Si467",
    )
    path = tmp_path / "simulation.psf"
    write_psf(path, psf, fmt=psf.formats("%.6e"))

    assert read_psf_header(path) == ["O533Si467", "O", "N"]
    expected = np.array(
        [
            [0, 1, 0, 2 * np.pi, 0, np.pi, 0, 300, 2.7, 1e5, 1, 0, 0],
            [1, 2, 0, 2 * np.pi, 0, np.pi, 1, 300, 0.001, 1e5, 0, 0.2, 0.8],
            [2, 3, 0, 2 * np.pi, 0, np.pi, 2, 300, 1, 1e5, 2, 1, 0],
            [3.001, 3.021, 0, 2 * np.pi, 0, np.pi, 3, 300, 2.7, 1e5, 1, 0, 0],
        ]
    )
    np.testing.assert_allclose(load_psf(path), expected, rtol=5e-7)
    assert read_psf_layers(path)[1]["fractions"] == {"O": 0.2, "N": 0.8}


def test_low_precision_preserves_thin_shells(tmp_path):
    psf = build_psf(
        inner_radius_km=[9556.48, 9556.5, 9656.501],
        outer_radius_km=[9556.5, 9656.5, 9656.521],
        temperature_k=300,
        density_g_cm3=0.001234567,
        pressure_pa=80375.4,
        mass_fractions={"N": 1},
        solid_composition="O533Si467",
    )
    path = tmp_path / "simulation.psf"
    write_psf(path, psf, fmt=psf.formats("%.3e"))
    data = load_psf(path)
    np.testing.assert_allclose(
        data[:, GEOMETRY_COLUMNS], psf.layers[:, GEOMETRY_COLUMNS], rtol=1e-11
    )
    np.testing.assert_allclose(data[:, 1] - data[:, 0], [0.02, 100, 0.02])
    assert data[2, 0] - data[1, 1] == pytest.approx(0.001)
    assert "1.235e-03" in path.read_text()
    assert "8.038e+04" in path.read_text()


def test_scalar_composition_broadcasts_across_layers():
    psf = build_psf(
        inner_radius_km=[1, 2],
        outer_radius_km=[2, 3],
        temperature_k=[300, 200],
        density_g_cm3=0.001,
        pressure_pa=[10, 1],
        mass_fractions={"N": 0.8, "O": 0.2},
        solid_composition="O533Si467",
    )
    np.testing.assert_allclose(psf.layers[:, FIRST_ELEMENT:], [[0.8, 0.2], [0.8, 0.2]])
    np.testing.assert_array_equal(psf.layers[:, STATE], [0, 0])
    with pytest.raises(ValueError, match="column order"):
        write_psf("unused.psf", psf, materials="O533Si467 O N", fmt="%.3e")


@pytest.mark.parametrize(
    "override,match",
    [
        ({"outer_radius_km": [2]}, "equal length"),
        ({"inner_radius_km": [1, 1.5]}, "overlap"),
        ({"temperature_k": [100, 200, 300]}, "one value per layer"),
        ({"density_g_cm3": -1}, "positive"),
        ({"pressure_pa": np.nan}, "finite"),
        ({"state": "plasma"}, "State"),
        ({"mass_fractions": {"N": 0.5}}, "sum to one"),
        ({"mass_fractions": {"N": -0.1, "O": 1.1}}, "nonnegative"),
        ({"mass_fractions": {"N": 0}}, "sum to one"),
    ],
)
def test_named_layers_reject_inconsistent_inputs(override, match):
    arguments = dict(
        inner_radius_km=[1, 2],
        outer_radius_km=[2, 3],
        temperature_k=300,
        density_g_cm3=0.001,
        pressure_pa=1e5,
        mass_fractions={"N": 1},
        solid_composition="O533Si467",
    )
    arguments.update(override)
    with pytest.raises(ValueError, match=match):
        build_psf(**arguments)


def test_written_psf_preserves_values_materials_and_states(tmp_path):
    path = tmp_path / "simulation.psf"
    layers = np.array(
        [
            [0, 1, 0, 2 * np.pi, 0, np.pi, 0, 293, 2.7, 1e5, 1, 0, 0],
            [1, 2, 0, 2 * np.pi, 0, np.pi, 1, 250, 0.1, 2, 2, 0.25, 0.75],
            [2, 3, 0, 2 * np.pi, 0, np.pi, 2, 240, 0.01, 1, 0, 1, 0],
        ]
    )

    write_psf(path, layers, materials="O750Si250 N O", fmt="%.6e")

    assert read_psf_header(path) == ["O750Si250", "N", "O"]
    np.testing.assert_allclose(load_psf(path), layers, rtol=5e-7)
    assert [layer["state"] for layer in read_psf_layers(path)] == [
        "solid",
        "liquid",
        "gas",
    ]
    assert "density g/cm3" in path.read_text()
    assert "pressure state N O" in path.read_text()


@pytest.mark.parametrize("column,value", [(6, 0.5), (10, 3), (8, np.nan)])
def test_invalid_psf_does_not_overwrite_existing_file(tmp_path, column, value):
    path = tmp_path / "simulation.psf"
    path.write_text("original contents")
    layers = np.array([[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]], dtype=float)
    layers[0, column] = value

    with pytest.raises(ValueError):
        write_psf(path, layers, materials="H1000 H", fmt="%.3e")
    assert path.read_text() == "original contents"


def test_psf_writer_rejects_material_column_mismatch(tmp_path):
    with pytest.raises(ValueError, match="columns"):
        write_psf(
            tmp_path / "simulation.psf",
            np.zeros((2, 12)),
            materials="H1000 H O",
            fmt="%.3e",
        )


def test_reads_descriptive_header_followed_by_material_definition(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "# Planet Specification Format\n"
        "# Column descriptions\n"
        "H1000 H\n"
        "0 1 0 1 0 1 0 293 1 1 1 0\n"
    )

    assert read_psf_header(path) == ["H1000", "H"]
    np.testing.assert_allclose(
        load_psf(path),
        [[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]],
    )


def test_reads_legacy_commented_material_definition(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text("#H1000 H\n" "0 1 0 1 0 1 0 293 1 1 1 0\n")

    assert read_psf_header(path) == ["H1000", "H"]
    np.testing.assert_allclose(
        load_psf(path),
        [[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]],
    )


def test_reads_psf_rows_as_material_layers(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "O750Si250 N O\n"
        "0 1 0 1 0 1 0 293 2.7 1 1 0 0\n"
        "1 2 0 1 0 1 1 250 0.1 2 2 0.25 0.75\n"
    )

    layers = read_psf_layers(path)

    assert [layer["state"] for layer in layers] == ["solid", "liquid"]
    assert layers[0]["fractions"] == {"O": 0.75, "Si": 0.25}
    assert layers[1]["fractions"] == {"N": 0.25, "O": 0.75}
    assert [layer["detector_id"] for layer in layers] == [0, 1]


def test_writer_without_format_uses_numpy_formatting(tmp_path):
    path = tmp_path / "simulation.psf"
    layers = np.array(
        [
            [
                9556.48,
                9556.5,
                0,
                2 * np.pi,
                0,
                np.pi,
                0,
                293.123456789,
                0.001234567891234,
                80375.41234567,
                0,
                1,
            ],
        ]
    )
    write_psf(path, layers, materials="H1000 H")
    np.testing.assert_array_equal(load_psf(path), layers)
    expected = tmp_path / "numpy.txt"
    np.savetxt(expected, layers)
    assert path.read_text().splitlines()[6:] == expected.read_text().splitlines()
