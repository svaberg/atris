"""Histogram arrays and their ROOT/CSV representations, including recorded moments."""

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import tempfile
import warnings

from uproot.writing.identify import to_TAxis, to_TH1x, to_TH2x
import numpy as np
import uproot


PRIMARY_HISTOGRAM = "h1.1"
IONIZATION_HISTOGRAM = "h2.ion"
TOTAL_DEPOSITION_HISTOGRAM = "h2.edep"
BIN_ENTRIES = 0
BIN_SUM_WEIGHTS = 1
PLANE_SUM_PREFIX = "#planes_Sxyw "
ATRIS_ANNOTATION_PREFIX = "#annotation atris."
ROOT_STATISTICS = (
    "fEntries", "fTsumw", "fTsumw2", "fTsumwx", "fTsumwx2",
    "fTsumwy", "fTsumwy2", "fTsumwxy",
)


@dataclass
class Histogram:
    """Bin values, edges and available squared-weight sums, including flow bins.

    ``sumw2`` contains raw squared-weight sums, not a sample variance or a
    standard error. ROOT statistics and CSV annotations retain format-specific information;
    missing uncertainty information is represented by None, not inferred.
    """

    values: np.ndarray
    axes: list[np.ndarray]
    sumw2: np.ndarray | None = None
    title: str = ""
    axis_titles: tuple[str, ...] = ()
    statistics: dict[str, float] = field(default_factory=dict)
    root_class: str | None = None
    annotations: tuple[str, ...] = ()
    bin_statistics: np.ndarray | None = None
    columns: tuple[str, ...] = ()
    value_column: int = BIN_SUM_WEIGHTS
    plane_sum: float | None = None

    def __str__(self):
        lines = ["Histogram" + (": " + self.title if self.title else ""),
                 f"Value shape: {self.values.shape}"]
        if self.axes:
            for index, axis in enumerate(self.axes):
                label = (self.axis_titles[index] if index < len(self.axis_titles) else "") or f"Axis {index}"
                extent = (f"{len(axis) - 1:,} {'bin' if len(axis) == 2 else 'bins'} "
                          f"from {axis[0]:g} to {axis[-1]:g}"
                          if len(axis) >= 2 else "bin edges unavailable")
                lines.append(f"{label}: {extent}")
            lines.append("Values include underflow and overflow bins")
        else:
            lines.append("Bin edges unavailable")
        lines.append("Squared-weight sums: " + ("available" if self.sumw2 is not None else "unavailable"))
        return "\n".join(lines)

    def __post_init__(self):
        if self.bin_statistics is not None:
            if self.bin_statistics.shape[-1] != len(self.columns):
                raise ValueError("Histogram bin statistics do not match its columns")
            self.values = self.bin_statistics[..., self.value_column]
            self.sumw2 = (self.bin_statistics[..., self.columns.index("Sw2")]
                              if self.value_column == BIN_SUM_WEIGHTS and "Sw2" in self.columns else None)
        if self.axes and self.values.shape != tuple(len(axis) + 1 for axis in self.axes):
            raise ValueError("Histogram values do not match its axes and flow bins")
        if self.sumw2 is not None and self.sumw2.shape != self.values.shape:
            raise ValueError("Histogram squared-weight sums do not match its values")

    @property
    def entries(self):
        """Per-bin fill counts when recorded; ROOT does not supply these."""
        return None if self.bin_statistics is None else self.bin_statistics[..., BIN_ENTRIES]

    def add(self, other, description):
        """Add compatible bin statistics in place without changing geometry."""
        if (self.root_class != other.root_class or self.title != other.title
                or self.values.shape != other.values.shape
                or len(self.axes) != len(other.axes)
                or self.statistics.keys() != other.statistics.keys()
                or self.columns != other.columns or self.value_column != other.value_column
                or (self.bin_statistics is None) != (other.bin_statistics is None)
                or (self.plane_sum is None) != (other.plane_sum is None)
                or comparable_header(self.annotations) != comparable_header(other.annotations)
                or (self.sumw2 is None) != (other.sumw2 is None)):
            raise ValueError("Histogram differs: " + description)
        if self.axis_titles != other.axis_titles or any(
                not np.array_equal(first, second) for first, second in zip(self.axes, other.axes)):
            raise ValueError("Histogram axes differ: " + description)
        if self.bin_statistics is not None:
            self.bin_statistics += other.bin_statistics
        else:
            self.values += other.values
            if self.sumw2 is not None:
                self.sumw2 += other.sumw2
        for name, value in other.statistics.items():
            self.statistics[name] += value
        if self.plane_sum is not None:
            self.plane_sum += other.plane_sum

    def write_csv(self, output):
        """Write all recorded bin statistics to an open text stream."""
        if self.bin_statistics is None:
            raise ValueError("CSV requires per-bin entries and moments absent from ROOT")
        for line in self.annotations:
            if line.startswith(PLANE_SUM_PREFIX) and self.plane_sum is not None:
                line = PLANE_SUM_PREFIX + "%.17g" % self.plane_sum
            output.write(line + "\n")
        output.write(",".join(self.columns) + "\n")
        data = self.bin_statistics.swapaxes(0, 1) if len(self.axes) == 2 else self.bin_statistics
        np.savetxt(output, data.reshape(-1, len(self.columns)), delimiter=",",
                   fmt=["%.0f"] + ["%.17e"] * (len(self.columns) - 1))


def comparable_header(header):
    return [line for line in header
            if not line.startswith((PLANE_SUM_PREFIX, ATRIS_ANNOTATION_PREFIX))]


def read_root_histogram(source):
    """Keep ROOT bin data, axis labels and accumulated statistics together."""
    sumw2 = source.variances(flow=True) if len(source.member("fSumw2")) else None
    return Histogram(
        values=np.asarray(source.values(flow=True), dtype=float),
        axes=[np.asarray(axis.edges(), dtype=float) for axis in source.axes],
        sumw2=None if sumw2 is None else np.asarray(sumw2, dtype=float),
        title=source.title,
        axis_titles=tuple(source.member(name).member("fTitle")
                          for name in ("fXaxis", "fYaxis")[:len(source.axes)]),
        statistics={name: float(source.member(name)) for name in
                    (ROOT_STATISTICS if len(source.axes) == 2 else ROOT_STATISTICS[:5])},
        root_class=source.classname,
    )


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


def read_csv_histogram(path):
    """Read every Geant4 CSV bin statistic into the shared histogram model.

    Missing axes remain an empty list; no bin edges are invented.
    """
    path = Path(path)
    lines = path.read_text().splitlines()
    column_index = next(index for index, line in enumerate(lines) if not line.startswith("#"))
    header = lines[:column_index]
    columns = tuple(column.strip() for column in lines[column_index].split(","))
    data = np.loadtxt(path, delimiter=",", skiprows=column_index + 1, ndmin=2)
    axes = _csv_axes(header)
    if axes:
        shape = tuple(len(axis) + 1 for axis in axes)
        if len(shape) not in (1, 2) or data.shape != (np.prod(shape), len(columns)):
            raise ValueError("Histogram table size does not match its axes: " + str(path))
        data = data.reshape(*shape[::-1], len(columns))
        if len(shape) == 2:
            data = data.swapaxes(0, 1)
    column = BIN_ENTRIES if path.name.endswith("_h1_h1.1.csv") else BIN_SUM_WEIGHTS
    return Histogram(data[..., column], axes, bin_statistics=data, columns=columns,
                     value_column=column, annotations=tuple(header),
                     title=next((line[len("#title "):] for line in header
                                 if line.startswith("#title ")), ""),
                     plane_sum=next((float(line[len(PLANE_SUM_PREFIX):]) for line in header
                                     if line.startswith(PLANE_SUM_PREFIX)), None))


def _csv_axes(header):
    axes = []
    for line in header:
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
    return axes


def csv_histogram_axes(path):
    """Read only axis metadata, without loading histogram bin statistics."""
    axes = _csv_axes(Path(path).read_text().splitlines())
    if not axes:
        raise ValueError("No histogram axes found in " + str(path))
    return axes


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

    def __getitem__(self, name):
        """Read one histogram with the same representation for either format."""
        if self.format == "csv":
            path = csv_histogram_path(self.prefix, name)
            histogram = read_csv_histogram(path)
            if not histogram.axes:
                raise ValueError("No histogram axes found in " + str(path))
            return histogram

        histogram = read_root_histogram(self._root()[name])
        if name == PRIMARY_HISTOGRAM and not np.isclose(
                histogram.values.sum(), histogram.statistics["fEntries"]):
            raise ValueError(
                "%s.root contains a weighted %s histogram; per-bin primary counts are unavailable"
                % (self.prefix.name, PRIMARY_HISTOGRAM))
        if len(histogram.axes) not in (1, 2):
            raise ValueError(
                "Unsupported response histogram dimension for " + name
            )
        return histogram

    def phantom_count(self):
        indexes = {
            int(match.group(1))
            for name in self.names()
            if (match := re.fullmatch(r"h2\.dos(\d+)", name)) is not None
        }
        if indexes and indexes != set(range(max(indexes) + 1)):
            raise ValueError("Phantom response histogram indexes are not contiguous")
        return len(indexes)

    def mean_variance(self, name):
        """Variance of the per-primary mean, in squared raw response units.

        Uses ``name + '.primary'`` and the primary counts, including primaries
        with no score. Arrays include flow bins, in (energy, layer) order.
        Bins with fewer than two primaries return NaN. Older outputs without
        the companion statistic cannot supply this variance. Warns when native
        CSV rounding prevents reliable subtraction of nearly equal moments.
        """
        companion = name + ".primary"
        if companion not in self.names():
            raise ValueError("Per-primary squared sums are unavailable for " + name)
        response = self[companion]
        primary = self[PRIMARY_HISTOGRAM]
        if (len(response.axes) != 2
                or not np.array_equal(response.axes[0], primary.axes[0])):
            raise ValueError("Response and primary energy axes differ")
        if response.sumw2 is None:
            raise ValueError("Per-primary squared sums are unavailable for " + name)
        counts = primary.values[:, None]
        valid = counts > 1
        squared_mean_sum = np.divide(response.values**2, counts,
                                     out=np.zeros_like(response.values), where=valid)
        centered = response.sumw2 - squared_mean_sum
        # Native Geant4 CSV rounds moments to six significant digits. ROOT
        # retains doubles; neither representation avoids raw-moment cancellation.
        rtol = 2e-5 if self.format == "csv" else 1e-10
        tolerance = rtol * np.maximum(response.sumw2, squared_mean_sum)
        if np.any(valid & (centered < -tolerance)):
            raise ValueError("Inconsistent per-primary moments for " + name)
        if self.format == "csv" and np.any(
                valid & (response.sumw2 > 0) & (np.abs(centered) <= tolerance)):
            warnings.warn("CSV rounding limits the variance estimate for " + name
                          + "; use ROOT output to resolve small variances.",
                          RuntimeWarning, stacklevel=2)
        return np.divide(np.maximum(centered, 0), counts * (counts - 1),
                         out=np.full_like(centered, np.nan), where=valid)


def _read_metadata(root_file):
    if "metadata" not in root_file:
        return None
    tree = root_file["metadata"]
    arrays = tree.arrays(library="np")
    metadata = {}
    for name in tree.keys():
        values = np.asarray(arrays[name])
        if values.dtype.kind == "O":
            values = np.asarray(values.tolist(), dtype=str)
        metadata[name] = values
    return metadata


def read_root_histograms(path):
    """Read response histograms and optional metadata from one ROOT file."""
    histograms = {}
    with uproot.open(path) as root_file:
        for name, class_name in root_file.classnames(cycle=False).items():
            if not class_name.startswith(("TH1", "TH2")):
                continue
            histograms[name] = read_root_histogram(root_file[name])
        metadata = _read_metadata(root_file)
    if PRIMARY_HISTOGRAM not in histograms:
        raise ValueError(
            "%s does not contain %s" % (Path(path).name, PRIMARY_HISTOGRAM)
        )
    return histograms, metadata


def _root_axis(edges, title, name):
    return to_TAxis(
        name,
        title,
        len(edges) - 1,
        edges[0],
        edges[-1],
        edges,
    )


def _writable_histogram(histogram):
    sumw2 = histogram.sumw2
    common = {
        "fName": None,
        "fTitle": histogram.title,
        "data": histogram.values.ravel(order="F"),
        "fSumw2": None if sumw2 is None else sumw2.ravel(order="F"),
        "fXaxis": _root_axis(histogram.axes[0], histogram.axis_titles[0], "xaxis"),
        **histogram.statistics,
    }
    if len(histogram.axes) == 1:
        return to_TH1x(**common)
    return to_TH2x(
        **common,
        fYaxis=_root_axis(histogram.axes[1], histogram.axis_titles[1], "yaxis"),
    )


def write_root_histograms(path, histograms, metadata=None):
    """Write response histograms to one ROOT file atomically."""
    path = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
    )
    os.close(descriptor)
    try:
        with uproot.recreate(temporary_name) as root_file:
            for name, histogram in histograms.items():
                root_file[name] = _writable_histogram(histogram)
            if metadata:
                root_file["metadata"] = metadata
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return path
