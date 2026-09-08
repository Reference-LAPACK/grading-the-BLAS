import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from collections import defaultdict
from pathlib import Path

from plot_utils import parse_path_metadata, unique_output_path, reference_curves


def collect_max_vals_per_impl(paths):
    """Group max values by impl and scale. Returns (grouped, value_descriptor) where
    grouped is dict[impl][s] -> list of (d, max)."""
    grouped = defaultdict(lambda: defaultdict(list))
    descriptors = set()
    for p in paths:
        meta = parse_path_metadata(p)
        max_val = np.fromfile(p, dtype=np.float64)[0]
        grouped[meta["impl"]][meta["s"]].append((meta["d"], max_val))
        descriptors.add(meta["value_descriptor"])
    if len(descriptors) > 1:
        raise ValueError(f"Expected a single value descriptor across all paths, got: {sorted(descriptors)}")
    value_descriptor = descriptors.pop() if descriptors else "value"
    return grouped, value_descriptor


def select_largest_scale(grouped):
    """dict[impl][s] -> list of (d, val) becomes dict[impl] -> (s_max, sorted points)."""
    selected = {}
    for impl, scale_data in grouped.items():
        s_max = max(scale_data.keys())
        points = sorted(scale_data[s_max])
        selected[impl] = (s_max, points)
    return selected


def plot_lines_across_impls(selected, ax, y_label, show_yx=True, input_type=None):
    """Draw one line per impl (at that impl's largest scale) into ax."""
    markers = ['o', 's', '^', 'D', 'v', 'P', 'X', '*', '<', '>', 'h', 'p']
    impls = sorted(selected.keys())

    all_ds_flat = set()
    all_ys_flat = []
    for i, impl in enumerate(impls):
        s_max, points = selected[impl]
        ds = [pt[0] for pt in points]
        ys = [pt[1] for pt in points]
        all_ds_flat.update(ds)
        all_ys_flat.extend(ys)
        ax.plot(
            ds, ys,
            label=rf"{impl} ($2^{{\pm{s_max}}}$)",
            marker=markers[i % len(markers)],
            markersize=16,
            linewidth=1.5,
        )

    all_ds_flat = sorted(all_ds_flat)
    if show_yx and all_ds_flat:
        for ref_ys, ref_label in reference_curves(input_type, all_ds_flat):
            ax.plot(all_ds_flat, ref_ys, color='black', linestyle=':', linewidth=1.5)
            ax.text(all_ds_flat[-1], ref_ys[-1], ref_label,
                    ha='right', va='bottom', fontsize=FONTSIZE, color='black')
            all_ys_flat = all_ys_flat + ref_ys

    # Cap ylim before setting log scale so the tick locator never needs
    # to compute 10^309+, which overflows float64 in old matplotlib/numpy.
    _safe_top = np.finfo(np.float64).max / 1e3   # ~1.8e305; log10 ceil = 306, safe
    pos_ys = [y for y in all_ys_flat if np.isfinite(y) and y > 0]
    if pos_ys:
        # Extra headroom (2 decades) above the highest trace so the in-plot
        # upper-left legend doesn't sit on top of the data.
        ax.set_ylim(bottom=min(pos_ys) * 0.5,
                    top=min(max(pos_ys) * 1e2, _safe_top))

    ax.set_xscale('log', base=2)
    ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter())
    ax.set_yscale('log')

    def _safe_y_fmt(x, pos):
        if not np.isfinite(x) or x <= 0:
            return ''
        import math
        exp = int(math.floor(math.log10(x)))
        coeff = x / 10.0 ** exp
        if abs(coeff - 1.0) < 0.01:
            return rf'$10^{{{exp}}}$'
        return f'{x:.2g}'

    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(_safe_y_fmt))
    ax.tick_params(labelsize=FONTSIZE)
    ax.set_xlabel("dimension (m = n = k)", fontsize=FONTSIZE)
    ax.set_ylabel(y_label, fontsize=FONTSIZE)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)
    ncol = 2 if len(impls) > 4 else 1
    legend_fontsize = FONTSIZE * 0.7
    ax.legend(fontsize=legend_fontsize, loc='upper left', ncol=ncol,
              columnspacing=1.0, handletextpad=0.5, labelspacing=0.4,
              framealpha=0.9)


def plot_max_vals_across_impls(paths, y_label="f(n)", figsize: tuple = (9, 7), show_yx=True, input_type=None):
    if isinstance(paths, str):
        paths = [paths]

    grouped, value_descriptor = collect_max_vals_per_impl(paths)
    selected = select_largest_scale(grouped)

    for impl in sorted(selected.keys()):
        s_max, _ = selected[impl]
        print(f"    {impl}: using scale 2^±{s_max}")

    mpl.rcParams['font.family'] = 'serif'
    mpl.rcParams['mathtext.fontset'] = 'dejavuserif'
    global FONTSIZE
    FONTSIZE = 20

    fig, ax = plt.subplots(figsize=figsize)
    plot_lines_across_impls(selected, ax, y_label, show_yx=show_yx, input_type=input_type)
    fig.tight_layout()
    return fig


def main():
    parser = argparse.ArgumentParser(
        description="Plot max f(n) results for test 2 or test 3, one trace per "
                     "implementation (each shown at its own largest scaling factor)."
    )
    parser.add_argument("input_type_dir", type=Path,
                        help="e.g. results/raw_data/test2c or results/raw_data/test3")
    parser.add_argument("--exclude", nargs="+", default=[], metavar="IMPL",
                        help="impl names to omit from the plot (case-insensitive), "
                             "e.g. --exclude STRASSEN OZAKI2")
    args = parser.parse_args()

    input_type_dir = args.input_type_dir
    input_type = input_type_dir.name

    y_label_map = {
        "test2c": r"max componentwise $f_A(n)$",
        "test3":  r"max componentwise $f_B(n)$",
    }
    y_label = y_label_map.get(input_type, r"$f(n)$")

    filename = "max_f_of_n.fp64"

    paths = sorted(input_type_dir.glob(f"*/scl*/m*_n*_k*/{filename}"))
    paths = [p for p in paths if "C_ref" not in p.parts]
    if not paths:
        print(f"No {filename} files found under {input_type_dir}")
        sys.exit(1)

    excluded = {impl.lower() for impl in args.exclude}
    if excluded:
        before = {p.relative_to(input_type_dir).parts[0] for p in paths}
        paths = [p for p in paths if p.relative_to(input_type_dir).parts[0].lower() not in excluded]
        after = {p.relative_to(input_type_dir).parts[0] for p in paths}
        print(f"    Excluded: {sorted(before - after)}")
        if not paths:
            print("All impls were excluded; nothing to plot.")
            sys.exit(1)

    fig = plot_max_vals_across_impls(paths, y_label=y_label, show_yx=True, input_type=input_type)

    output_dir = Path("results/figures")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = unique_output_path(output_dir / f"{input_type}_across_impls.png")
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"    Figure written to: {output_path}")


if __name__ == "__main__":
    main()
