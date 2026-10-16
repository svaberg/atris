"""Toy uncertainty propagation for the histogram quantities written by AtRIS.

This is a numerical illustration, not an AtRIS output reader. Edit the small
configuration block below to change the dimensions or output location.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# Dimensions mirror the AtRIS histogram layout: primary species are separate
# runs, and each h2 histogram has detector/interface and primary-energy axes.
N_PRIMARY_BINS = 650
N_PHANTOMS = 4
N_INTERFACES = 3
N_PRIMARY_SPECIES = 44
N_TOY_SHOWER_SCORES_PER_BIN = 128
OUTPUT_PNG = Path(__file__).with_name("atris-output-covariance.png")

# Synthetic settings used only to make the example concrete.
COMMON_SHOWER_COMPONENT = 0.25
SHOWER_SCORE_RELATIVE_SPREAD = 0.12
SPECTRUM_NORMALIZATION_RELATIVE_ERROR = 0.04
SPECTRUM_SHAPE_RELATIVE_ERROR = 0.02
SPECTRUM_ENERGY_CORRELATION_LENGTH_BINS = 12.0


def make_output_labels():
    labels = []
    for interface in range(N_INTERFACES):
        labels.extend((f"h2.ion / interface {interface}",
                       f"h2.edep / interface {interface}"))
    for phantom in range(N_PHANTOMS):
        for histogram in ("dos", "equi", "rates"):
            for interface in range(N_INTERFACES):
                labels.append(f"h2.{histogram}{phantom} / interface {interface}")
    return labels


OUTPUT_LABELS = make_output_labels()
N_OUTPUTS = len(OUTPUT_LABELS)
ENERGY = np.geomspace(1e-3, 1e3, N_PRIMARY_BINS)
LOG_ENERGY = np.log10(ENERGY)


def synthetic_histogram_mean(species_index):
    """Return H[u,b], synthetic means for the existing h2 output channels."""
    interface_scale = np.linspace(1.0, 0.55, N_INTERFACES)
    generic_ion = np.exp(-0.5 * ((LOG_ENERGY - 1.0) / 1.15) ** 2)
    generic_edep = np.exp(-0.5 * ((LOG_ENERGY - 0.25) / 1.3) ** 2)
    species_scale = 1.0 + species_index / max(1, N_PRIMARY_SPECIES)
    means = []
    for interface in range(N_INTERFACES):
        means.extend((species_scale * interface_scale[interface] * generic_ion,
                      1.7 * species_scale * interface_scale[interface] * generic_edep))
    for phantom in range(N_PHANTOMS):
        for channel_scale, peak in ((1.0, 0.6 + 0.15 * phantom),
                                    (1.3, 0.9 + 0.1 * phantom),
                                    (0.75, 0.25 + 0.2 * phantom)):
            curve = np.exp(-0.5 * ((LOG_ENERGY - peak) / (1.0 + 0.05 * phantom)) ** 2)
            for interface in range(N_INTERFACES):
                means.append(species_scale * channel_scale * interface_scale[interface] * curve)
    return np.asarray(means)


def synthetic_histogram_covariance(mean_h):
    """Return per-energy-bin covariance blocks C_H[b] across h2 channels."""
    sum_score = np.zeros(N_OUTPUTS)
    sum_outer_product = np.zeros((N_OUTPUTS, N_OUTPUTS))
    for shower in range(N_TOY_SHOWER_SCORES_PER_BIN):
        phase = 2 * np.pi * shower / N_TOY_SHOWER_SCORES_PER_BIN
        common = np.sqrt(2.0) * np.sin(phase)
        channel_factors = np.sqrt(2.0) * np.sin(
            phase + 2 * np.pi * np.arange(N_OUTPUTS) / N_OUTPUTS
        )
        fluctuation = (np.sqrt(COMMON_SHOWER_COMPONENT) * common
                       + np.sqrt(1 - COMMON_SHOWER_COMPONENT) * channel_factors)
        score = 1 + SHOWER_SCORE_RELATIVE_SPREAD * fluctuation

        # This is the writer's update for the product vector x: accumulate
        # x and x x^T, then discard x. No shower records are retained.
        sum_score += score
        sum_outer_product += np.outer(score, score)

    n = N_TOY_SHOWER_SCORES_PER_BIN
    centered_outer_sum = sum_outer_product - np.outer(sum_score, sum_score) / n
    covariance_of_factor_mean = centered_outer_sum / (n * (n - 1))
    # The toy uses the same relative shower fluctuations at each energy bin;
    # scale their covariance by the channel means to make C_H[b].
    means_by_bin = mean_h.T
    return np.einsum("bu,uv,bv->buv", means_by_bin,
                     covariance_of_factor_mean, means_by_bin)


def synthetic_spectrum(species_index):
    """Return spectrum mean f[b] and its covariance C_F[b,b'] for one species."""
    mean_f = (1.0 + species_index / max(1, N_PRIMARY_SPECIES)) * ENERGY**-0.7
    distance = np.abs(np.arange(N_PRIMARY_BINS)[:, None]
                      - np.arange(N_PRIMARY_BINS)[None, :])
    correlation = np.exp(-distance / SPECTRUM_ENERGY_CORRELATION_LENGTH_BINS)
    relative_covariance = (SPECTRUM_NORMALIZATION_RELATIVE_ERROR**2
                           + SPECTRUM_SHAPE_RELATIVE_ERROR**2 * correlation)
    covariance_f = np.outer(mean_f, mean_f) * relative_covariance
    return mean_f, covariance_f


def propagate_one_species(mean_h, covariance_h, mean_f, covariance_f):
    """Exact covariance of Y[u] = sum_b H[u,b] F[b] under stated independence.

    H and F are independent. Histogram estimates from different primary-energy
    bins are independent in this toy; spectrum bins may be correlated. The
    first term includes Var(F[b]) Var(H[:,b]), the product's second-order term.
    """
    mean_y = mean_h @ mean_f
    covariance_y = mean_h @ covariance_f @ mean_h.T
    for b in range(N_PRIMARY_BINS):
        covariance_y += (mean_f[b] ** 2 + covariance_f[b, b]) * covariance_h[b]
    return mean_y, covariance_y


def size_report():
    values_bytes = N_OUTPUTS * N_PRIMARY_BINS * 8
    sumw2_bytes = values_bytes  # ROOT's per-bin squared-weight accumulator.
    full_covariance_bytes = N_PRIMARY_BINS * N_OUTPUTS**2 * 8
    packed_covariance_bytes = N_PRIMARY_BINS * N_OUTPUTS * (N_OUTPUTS + 1) // 2 * 8
    return values_bytes, sumw2_bytes, full_covariance_bytes, packed_covariance_bytes


def mib(byte_count):
    return byte_count / 1024**2


def main():
    # Species are independent runs here, so their response means add and their
    # covariance matrices add. No cross-species statistical covariance is made.
    total_mean = np.zeros(N_OUTPUTS)
    total_covariance = np.zeros((N_OUTPUTS, N_OUTPUTS))
    displayed_species = 0
    displayed = None
    for species in range(N_PRIMARY_SPECIES):
        mean_h = synthetic_histogram_mean(species)
        covariance_h = synthetic_histogram_covariance(mean_h)
        mean_f, covariance_f = synthetic_spectrum(species)
        mean_y, covariance_y = propagate_one_species(
            mean_h, covariance_h, mean_f, covariance_f
        )
        total_mean += mean_y
        total_covariance += covariance_y
        if species == displayed_species:
            displayed = (mean_h, covariance_h, mean_f, covariance_f, mean_y, covariance_y)

    mean_h, covariance_h, mean_f, covariance_f, mean_y_one, covariance_y_one = displayed
    errors_y = np.sqrt(np.maximum(np.diag(total_covariance), 0.0))
    errors_one = np.sqrt(np.maximum(np.diag(covariance_y_one), 0.0))
    correlation_h = covariance_h[N_PRIMARY_BINS // 2]
    diagonal = np.sqrt(np.maximum(np.diag(correlation_h), 1e-300))
    correlation_h = correlation_h / np.outer(diagonal, diagonal)

    fig = plt.figure(figsize=(15, 9), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=(0.8, 1.6))
    flow = fig.add_subplot(grid[0, :])
    flow.set_axis_off()
    flow.set_xlim(0, 1)
    flow.set_ylim(0, 1)

    def box(x, y, width, height, title, detail, color):
        flow.add_patch(plt.Rectangle((x, y), width, height, facecolor=color,
                                     edgecolor="#263238", linewidth=1.4,
                                     transform=flow.transAxes))
        flow.text(x + width / 2, y + height * 0.68, title, ha="center", va="center",
                  fontsize=12, fontweight="bold", transform=flow.transAxes)
        flow.text(x + width / 2, y + height * 0.3, detail, ha="center", va="center",
                  fontsize=10, transform=flow.transAxes)

    box(0.015, 0.47, 0.29, 0.4, "Phantom ROOT product",
        f"H[a,u,b]  shape=({N_PRIMARY_SPECIES},{N_OUTPUTS},{N_PRIMARY_BINS})\n"
        "h2 values + C_H[a,b,u,v] covariance blocks", "#e3f2fd")
    box(0.36, 0.47, 0.28, 0.4, "Independent incoming spectrum",
        f"F[a,b]  shape=({N_PRIMARY_SPECIES},{N_PRIMARY_BINS})\n"
        "spectrum covariance C_F[a,b,b']", "#fff3e0")
    box(0.70, 0.47, 0.285, 0.4, "Phantom response",
        f"Y[a,u] = sum_b H[a,u,b] F[a,b]\n"
        f"total shape=({N_OUTPUTS},)", "#e8f5e9")
    flow.annotate("", xy=(0.75, 0.46), xytext=(0.27, 0.45), xycoords="axes fraction",
                  arrowprops={"arrowstyle": "->", "lw": 1.7,
                              "connectionstyle": "arc3,rad=0.18"})
    flow.annotate("", xy=(0.75, 0.46), xytext=(0.51, 0.45), xycoords="axes fraction",
                  arrowprops={"arrowstyle": "->", "lw": 1.7,
                              "connectionstyle": "arc3,rad=-0.12"})
    flow.text(0.16, 0.31, r"writer accumulates $\sum x$ and $\sum x x^T$ per energy bin",
              ha="center", fontsize=10, transform=flow.transAxes)
    flow.text(0.5, 0.31, "No particle records retained", ha="center", fontsize=10,
              fontweight="bold", transform=flow.transAxes)
    flow.text(0.83, 0.31, r"$C_Y$ propagated from $C_H$ and $C_F$",
              ha="center", fontsize=10, transform=flow.transAxes)

    ax = fig.add_subplot(grid[1, 0])
    selected = next(i for i, label in enumerate(OUTPUT_LABELS) if label.startswith("h2.dos0 / interface 0"))
    ax.plot(ENERGY, mean_h[selected], color="#1769aa", lw=1.5)
    ax.fill_between(ENERGY,
                    np.maximum(0, mean_h[selected] - np.sqrt(covariance_h[:, selected, selected])),
                    mean_h[selected] + np.sqrt(covariance_h[:, selected, selected]),
                    color="#64b5f6", alpha=0.35, label="1 standard error")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("One existing h2 response and its error")
    ax.set_xlabel("Primary energy (MeV)")
    ax.set_ylabel("Synthetic histogram value")
    ax.legend(frameon=False)

    ax = fig.add_subplot(grid[1, 1])
    image = ax.imshow(correlation_h, vmin=-1, vmax=1, cmap="coolwarm", interpolation="nearest")
    ax.set_title(f"Same-energy covariance across {N_OUTPUTS} outputs")
    ax.set_xlabel("Existing histogram channel / interface")
    ax.set_ylabel("Existing histogram channel / interface")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Correlation")

    ax = fig.add_subplot(grid[1, 2])
    phantom_channels = [i for i, label in enumerate(OUTPUT_LABELS)
                        if label.startswith("h2.dos0 / interface 0")
                        or label.startswith("h2.equi0 / interface 0")
                        or label.startswith("h2.rates0 / interface 0")]
    names = [OUTPUT_LABELS[i].split(" / ")[0] for i in phantom_channels]
    x = np.arange(len(phantom_channels))
    ax.errorbar(x, total_mean[phantom_channels], yerr=errors_y[phantom_channels],
                fmt="o", color="#2e7d32", capsize=4, label="sum over source species")
    ax.set_xticks(x, names, rotation=25, ha="right")
    ax.set_title("Propagated phantom response")
    ax.set_ylabel("Synthetic response ± standard error")
    ax.grid(axis="y", alpha=0.25)

    values_bytes, sumw2_bytes, full_bytes, packed_bytes = size_report()
    print(f"Existing h2 channels U: {N_OUTPUTS}; primary-energy bins B: {N_PRIMARY_BINS}")
    print(f"Ordinary ROOT contents + Sumw2: {mib(values_bytes + sumw2_bytes):.3f} MiB per source species")
    print(f"Added full same-energy covariance blocks: {mib(full_bytes):.3f} MiB per source species")
    print(f"Added packed symmetric covariance blocks: {mib(packed_bytes):.3f} MiB per source species")
    print(f"Across {N_PRIMARY_SPECIES} independent source species: "
          f"{mib(full_bytes * N_PRIMARY_SPECIES):.3f} MiB full, "
          f"{mib(packed_bytes * N_PRIMARY_SPECIES):.3f} MiB packed")
    print("These are raw array payload estimates: no ROOT compression or object overhead included.")
    print(f"Toy writer used {N_TOY_SHOWER_SCORES_PER_BIN} synthetic shower scores per energy bin.")
    print("Toy assumptions: H and F independent; primary-energy histogram strata independent; "
          "source-species runs independent. Per-shower product vectors were discarded after "
          "updating sum(x) and sum(x x^T).")
    print(f"Wrote {OUTPUT_PNG}")
    fig.savefig(OUTPUT_PNG, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
