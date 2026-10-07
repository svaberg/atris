"""Read AtRIS response histograms from Geant4 CSV or ROOT output."""

from dataclasses import dataclass
import re
from pathlib import Path

import numpy as np
import uproot


PRIMARY_HISTOGRAM = "h1.1"
IONIZATION_HISTOGRAM = "h2.ion"
TOTAL_DEPOSITION_HISTOGRAM = "h2.edep"
_RESPONSE_PROPERTIES = {
    "/atris/phantom/response/name": "name",
    "/atris/phantom/response/tableFile": "file",
    "/atris/phantom/response/scaleByCrossingEnergy": "scale_by_crossing_energy",
    "/atris/phantom/response/scaleByRadiationWeight": "scale_by_radiation_weight",
    "/atris/phantom/response/scaleByInversePhantomMass": (
        "scale_by_inverse_phantom_mass"
    ),
}
_RESPONSE_ANNOTATIONS = {
    "atris.phantom_stem": "phantom_stem",
    "atris.response_name": "name",
    "atris.response_file": "file",
    "atris.response_scale_by_crossing_energy": "scale_by_crossing_energy",
    "atris.response_scale_by_radiation_weight": "scale_by_radiation_weight",
    "atris.response_scale_by_inverse_phantom_mass": (
        "scale_by_inverse_phantom_mass"
    ),
}


@dataclass(frozen=True)
class ResponseDefinition:
    """Configuration and identity of one phantom response histogram."""

    phantom_stem: str
    name: str
    file: Path
    scale_by_crossing_energy: bool
    scale_by_radiation_weight: bool
    scale_by_inverse_phantom_mass: bool

    @property
    def histogram_name(self):
        return "h2.%s.%s" % (self.phantom_stem, self.name)


def _boolean(value, source):
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("Expected true or false for %s, got %s" % (source, value))


def _response_definition(values, source):
    required = {"phantom_stem", *_RESPONSE_PROPERTIES.values()}
    missing = required - values.keys()
    if missing:
        raise ValueError(
            "Incomplete phantom response in %s; missing: %s"
            % (source, ", ".join(sorted(missing)))
        )
    return ResponseDefinition(
        phantom_stem=values["phantom_stem"],
        name=values["name"],
        file=Path(values["file"]),
        scale_by_crossing_energy=_boolean(
            values["scale_by_crossing_energy"], source
        ),
        scale_by_radiation_weight=_boolean(
            values["scale_by_radiation_weight"], source
        ),
        scale_by_inverse_phantom_mass=_boolean(
            values["scale_by_inverse_phantom_mass"], source
        ),
    )


def read_macro_responses(filename):
    """Read explicit phantom response definitions from an AtRIS macro."""
    responses = []
    phantom_name = None
    response = {}
    configured_names = set()
    filename = Path(filename)
    with filename.open() as macro:
        for line_number, line in enumerate(macro, start=1):
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            command = fields[0]
            if command == "/atris/phantom/name":
                if len(fields) != 2:
                    raise ValueError(
                        "Invalid phantom name command at %s:%i"
                        % (filename, line_number)
                    )
                phantom_name = fields[1]
                continue
            if command in _RESPONSE_PROPERTIES:
                if len(fields) != 2:
                    raise ValueError(
                        "Invalid phantom response property at %s:%i"
                        % (filename, line_number)
                    )
                response[_RESPONSE_PROPERTIES[command]] = fields[1]
                continue
            if command != "/atris/phantom/response/add":
                continue
            if len(fields) != 1 or phantom_name is None:
                raise ValueError(
                    "Incomplete phantom response at %s:%i"
                    % (filename, line_number)
                )
            response["phantom_stem"] = phantom_name
            definition = _response_definition(
                response,
                "%s:%i" % (filename, line_number),
            )
            if definition.histogram_name in configured_names:
                raise ValueError(
                    "Duplicate %s response for phantom %s at %s:%i"
                    % (definition.name, phantom_name, filename, line_number)
                )
            responses.append(definition)
            configured_names.add(definition.histogram_name)
            response.clear()
    if response:
        raise ValueError("Incomplete phantom response at end of %s" % filename)
    return responses


def csv_histogram_path(prefix, name):
    """Return Geant4's CSV path for a named H1 or H2 histogram."""
    histogram_type = name.split(".", 1)[0]
    return Path(str(prefix) + "_" + histogram_type + "_" + name + ".csv")


def response_output_format(prefix):
    """Return the unambiguous response-histogram format for a prefix."""
    prefix = Path(prefix)
    csv_exists = csv_histogram_path(prefix, PRIMARY_HISTOGRAM).is_file()
    root_exists = Path(str(prefix) + ".root").is_file()
    if csv_exists and root_exists:
        raise ValueError(
            "Both CSV and ROOT response output exist for " + prefix.name
        )
    if csv_exists:
        return "csv"
    if root_exists:
        return "root"
    return None


def _csv_lines(path):
    lines = path.read_text().splitlines()
    column_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#")
    )
    return lines, column_index


def read_csv_histogram(path):
    """Read a Geant4 CSV histogram header, columns, and bin table."""
    path = Path(path)
    lines, column_index = _csv_lines(path)
    data = np.loadtxt(path, delimiter=",", skiprows=column_index + 1)
    return lines[:column_index], lines[column_index], np.atleast_2d(data)


def csv_histogram_annotations(path):
    """Return native Geant4 annotations from a CSV histogram header."""
    annotations = {}
    for line in Path(path).read_text().splitlines():
        if not line.startswith("#"):
            break
        if line.startswith("#annotation "):
            fields = line.split(maxsplit=2)
            if len(fields) == 3:
                annotations[fields[1]] = fields[2]
    return annotations


def csv_histogram_axes(path):
    """Read histogram axis edges from a Geant4 CSV header."""
    axes = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#axis edges "):
            axes.append(np.fromstring(line[len("#axis edges ") :], sep=" "))
        elif line.startswith("#axis fixed "):
            fields = line.split()
            axes.append(
                np.linspace(
                    float(fields[3]),
                    float(fields[4]),
                    int(fields[2]) + 1,
                )
            )
        elif not line.startswith("#"):
            break
    if not axes:
        raise ValueError("No histogram axes found in " + str(path))
    return axes


def table_histogram_values(table, axes, column=1):
    """Return a Geant4 CSV bin column in histogram-axis order."""
    if len(axes) not in (1, 2):
        raise ValueError("Only one- and two-dimensional histograms are supported")
    shape = tuple(len(axis) + 1 for axis in axes)
    values = np.asarray(table[:, column], dtype=float)
    if values.size != np.prod(shape):
        raise ValueError("Histogram table size does not match its axes")
    return values.reshape(shape[::-1]).T


class ResponseHistogramReader:
    """Expose equivalent response data from CSV files or one ROOT file."""

    def __init__(self, prefix):
        self.prefix = Path(prefix)
        self.format = response_output_format(self.prefix)
        if self.format is None:
            raise FileNotFoundError(
                "No response histogram output found for " + str(self.prefix)
            )
        self._root_file = None

    def __enter__(self):
        if self.format == "root":
            self._root_file = uproot.open(str(self.prefix) + ".root")
            if PRIMARY_HISTOGRAM not in self._root_file:
                self._root_file.close()
                self._root_file = None
                raise ValueError(
                    "%s.root does not contain %s"
                    % (self.prefix.name, PRIMARY_HISTOGRAM)
                )
        return self

    def __exit__(self, exception_type, exception, traceback):
        if self._root_file is not None:
            self._root_file.close()
            self._root_file = None

    def _root(self):
        if self._root_file is None:
            raise RuntimeError("ResponseHistogramReader is not open")
        return self._root_file

    def names(self):
        if self.format == "root":
            root_file = self._root()
            return {
                name
                for name, class_name in root_file.classnames(cycle=False).items()
                if class_name.startswith(("TH1", "TH2"))
            }

        pattern = re.compile(
            "^"
            + re.escape(self.prefix.name)
            + r"_(h[12])_(h[12]\..+)\.csv$"
        )
        return {
            match.group(2)
            for path in self.prefix.parent.glob(self.prefix.name + "_h*.csv")
            if (match := pattern.match(path.name)) is not None
        }

    def axes(self, name):
        if self.format == "root":
            histogram = self._root()[name]
            return [np.asarray(axis.edges()) for axis in histogram.axes]
        return csv_histogram_axes(csv_histogram_path(self.prefix, name))

    def values(self, name):
        """Return bin values in histogram-axis order, including flow bins."""
        if self.format == "csv":
            path = csv_histogram_path(self.prefix, name)
            table = read_csv_histogram(path)[2]
            column = 0 if name == PRIMARY_HISTOGRAM else 1
            return table_histogram_values(
                table, csv_histogram_axes(path), column
            )

        histogram = self._root()[name]
        values = np.asarray(histogram.values(flow=True), dtype=float)
        if len(histogram.axes) == 1:
            if name == PRIMARY_HISTOGRAM:
                entries = float(histogram.member("fEntries"))
                if not np.isclose(values.sum(), entries):
                    raise ValueError(
                        "%s.root contains a weighted %s histogram; per-bin "
                        "primary counts are unavailable"
                        % (self.prefix.name, PRIMARY_HISTOGRAM)
                    )
        if len(histogram.axes) not in (1, 2):
            raise ValueError(
                "Unsupported response histogram dimension for " + name
            )
        return values

    def responses(self):
        """Return response names grouped by their phantom stem."""
        responses = {}
        for name in self.names():
            match = re.fullmatch(r"h2\.(.+)\.([^.]+)", name)
            if match is not None:
                responses.setdefault(match.group(1), set()).add(match.group(2))
        return responses

    def response_definitions(self):
        """Return response metadata independently of histogram storage format."""
        output_names = {
            "h2.%s.%s" % (stem, name)
            for stem, names in self.responses().items()
            for name in names
        }
        if not output_names:
            return []

        if self.format == "root":
            configured = read_macro_responses(
                self.prefix.with_name(self.prefix.name + ".mac")
            )
        else:
            configured = []
            for histogram_name in output_names:
                annotations = csv_histogram_annotations(
                    csv_histogram_path(self.prefix, histogram_name)
                )
                values = {
                    field: annotations[key]
                    for key, field in _RESPONSE_ANNOTATIONS.items()
                    if key in annotations
                }
                configured.append(
                    _response_definition(values, histogram_name)
                )

        by_histogram = {
            response.histogram_name: response for response in configured
        }
        missing = output_names - by_histogram.keys()
        if missing:
            raise ValueError(
                "No response configuration found for "
                + ", ".join(sorted(missing))
            )
        return [by_histogram[name] for name in sorted(output_names)]

    def phantom_stems(self):
        return set(self.responses())
