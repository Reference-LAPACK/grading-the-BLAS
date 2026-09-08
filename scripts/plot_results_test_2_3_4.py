import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from collections import defaultdict
from pathlib import Path

from plot_utils import parse_path_metadata, unique_output_path, reference_curves

# Per-cell pass/fail predicates keyed by input_type.
# None means no threshold is defined yet; the check is skipped.
_CELL_THRESHOLD = {
    "test2c":                  lambda d, val: val < d,   # max f_A(n) < n
    "test3":                   lambda d, val: val < d**2,   # max f_A(n) < n
    "test2b_w_inner_permute":  None,                      # TBD
    "test2b_w_outer_permute":  None,                      # TBD
}
_THRESHOLD_DESC = {
    "test2c":                  "max componentwise f_A(n) < n",
    "test3":                   "max componentwise f_B(n) < n**2",
    "test2b_w_inner_permute":  None,
    "test2b_w_outer_permute":  None,
}


def collect_max_vals(paths):
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

def plot_lines(grouped, ax, scale_style, y_label, show_yx=True, input_type=None):
    """Draw one line per scale into ax."""
    impl = next(iter(grouped))
    for s in sorted(grouped[impl]):
        points = sorted(grouped[impl][s])
        ds = [pt[0] for pt in points]
        ys = [pt[1] for pt in points]
        style = scale_style[s]
        ax.plot(
            ds, ys,
            label=rf"$2^{{\pm{s}}}$",
            marker=style["marker"],
            markersize=16,
            linewidth=1.5,
        )
    all_ds_flat = sorted({pt[0] for points in grouped[impl].values() for pt in points})
    all_ys_flat = [y for pts in grouped[impl].values() for _, y in pts]
    if show_yx and all_ds_flat:
        for ref_ys, ref_label in reference_curves(input_type, all_ds_flat):
            ax.plot(all_ds_flat, ref_ys, color='black', linestyle=':', linewidth=1.5)
            ax.text(all_ds_flat[-1], ref_ys[-1], ref_label,
                    ha='right', va='bottom', fontsize=FONTSIZE, color='black')
            all_ys_flat = all_ys_flat + list(ref_ys)
    # Cap ylim before setting log scale so the tick locator never needs
    # to compute 10^309+, which overflows float64 in old matplotlib/numpy.
    _safe_top = np.finfo(np.float64).max / 1e3   # ~1.8e305; log10 ceil = 306, safe
    pos_ys = [y for y in all_ys_flat if np.isfinite(y) and y > 0]
    if pos_ys:
        ax.set_ylim(bottom=min(pos_ys) * 0.5,
                    top=min(max(pos_ys) * 2, _safe_top))

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
    ax.legend(fontsize=FONTSIZE, loc='upper left', bbox_to_anchor=(1.01, 1),
              borderaxespad=0., title="scale factor", title_fontsize=FONTSIZE)

def build_heatmap_grid(grouped):
    """
    Reshape the grouped data into a dict[impl] -> (ds, scales, Z) where
    Z[i, j] = max value at scale scales[i], dimension ds[j].
    Missing combinations become NaN.
    """
    all_ds = sorted({d for impl_data in grouped.values()
                       for points in impl_data.values()
                       for d, _ in points})
    all_scales = sorted({s for impl_data in grouped.values() for s in impl_data})

    grids = {}
    for impl, impl_data in grouped.items():
        Z = np.full((len(all_scales), len(all_ds)), np.nan)
        for s, points in impl_data.items():
            i = all_scales.index(s)
            for d, val in points:
                j = all_ds.index(d)
                Z[i, j] = val
        grids[impl] = Z
    return all_ds, all_scales, grids


def plot_heatmap(grids, all_ds, all_scales, ax, cmap, y_label):
    """Draw the heatmap for the single impl into ax."""
    impl = next(iter(grids))
    Z = grids[impl]
    finite = Z[np.isfinite(Z)]
    vmin, vmax = (finite.min(), finite.max()) if finite.size > 0 else (0.0, 1.0)
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    im = ax.imshow(
        np.where(np.isfinite(Z), Z, np.nan),
        cmap=cmap,
        norm=norm,
        aspect='auto',
        origin='lower',
        interpolation='nearest',
    )
    labels = {}
    for r in range(Z.shape[0]):
        for c in range(Z.shape[1]):
            val = Z[r, c]
            if np.isposinf(val):
                labels[(r, c)] = "+INF"
            elif np.isneginf(val):
                labels[(r, c)] = "-INF"
            elif np.isfinite(val):
                labels[(r, c)] = f"{val:.2g}"
    # max_len = max((len(s) for s in labels.values()), default=5)
    # cell_fontsize = FONTSIZE * min(1.0, 8 / max_len)

    cell_fontsize = FONTSIZE

    for (row, col), label in labels.items():
        val = Z[row, col]
        if not np.isfinite(val):
            ax.add_patch(mpl.patches.Rectangle(
                (col - 0.5, row - 0.5), 1, 1, color='red', zorder=2))
            text_color = "white"
        else:
            rgba = cmap(norm(val))
            luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
            text_color = "white" if luminance < 0.5 else "black"
        ax.text(col, row, label, ha="center", va="center",
                fontsize=cell_fontsize, color=text_color, zorder=3)
    ax.set_xlabel("dimension (m = n = k)", fontsize=FONTSIZE)
    ax.set_ylabel("scale factor", fontsize=FONTSIZE)
    ax.set_xticks(range(len(all_ds)))
    ax.set_xticklabels(all_ds, fontsize=FONTSIZE, rotation=45, ha='right')
    ax.set_yticks(range(len(all_scales)))
    ax.set_yticklabels([rf"$2^{{\pm{s}}}$" for s in all_scales], fontsize=FONTSIZE)
    cb = ax.figure.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label(y_label, fontsize=FONTSIZE)
    cb.ax.tick_params(labelsize=FONTSIZE)
    fmt = mpl.ticker.ScalarFormatter(useMathText=True)
    fmt.set_powerlimits((-3,3))
    cb.ax.yaxis.set_major_formatter(fmt)
    cb_ot = cb.ax.yaxis.get_offset_text()
    cb_ot.set_fontsize(FONTSIZE)
    cb_ot.set_ha('left')
    cb_ot.set_x(0) 

    # def _safe_cb_fmt(x, pos):
    #     if not np.isfinite(x):
    #         return ''
    #     import math
    #     if x == 0.0:
    #         return '0'
    #     exp = int(math.floor(math.log10(abs(x))))
    #     coeff = x / 10.0 ** exp
    #     if abs(coeff - round(coeff)) < 0.01:
    #         coeff = round(coeff)
    #     if exp == 0:
    #         return f'{coeff:.3g}'
    #     return rf'${coeff:.3g} \times 10^{{{exp}}}$'

    # cb.ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(_safe_cb_fmt))

def plot_max_vals(paths, y_label="f(n)", figsize_per_plot: tuple = (9, 6), show_yx=True, input_type=None):
    if isinstance(paths, str):
        paths = [paths]

    grouped, value_descriptor = collect_max_vals(paths)

    # pass/fail check
    threshold_fn = _CELL_THRESHOLD.get(input_type)
    if threshold_fn is None:
        print(f"    (no threshold defined for '{input_type}', skipping pass/fail check)")
        passed = True
    else:
        impl = next(iter(grouped))
        failures = [
            (s, d, val)
            for s, points in grouped[impl].items()
            for d, val in sorted(points)
            if not (np.isfinite(val) and threshold_fn(d, val))
        ]
        passed = len(failures) == 0
        desc = _THRESHOLD_DESC[input_type]
        if passed:
            print(f"    PASS: {desc}")
        else:
            print(f"    FAIL ({desc}): {len(failures)} cell(s):")
            for s, d, val in failures:
                print(f"    scale=2^±{s}, dim={d}: {val:.4g}")
    impls = sorted(grouped.keys())
    if len(impls) != 1:
        raise ValueError(f"Expected exactly one impl in paths, got: {impls}")

    all_ds, all_scales, grids = build_heatmap_grid(grouped)
    heatmap_cmap = mpl.colormaps['cividis']

    mpl.rcParams['font.family'] = 'serif'
    mpl.rcParams['mathtext.fontset'] = 'dejavuserif'
    global FONTSIZE
    FONTSIZE = 20
    line_w = figsize_per_plot[0]
    heat_w = max(6.0, len(all_ds) * 2.5)
    plot_h = max(6.0, len(all_scales) * 1.0)
    fig, axes = plt.subplots(
        1, 2,
        figsize=(line_w + heat_w, plot_h),
        gridspec_kw={'width_ratios': [line_w, heat_w]},
    )

    markers = ['o', 's', '^', 'D', 'v', 'P', 'X', '*', '<', '>', 'h', 'p']
    all_scales_for_lines = sorted({s for impl_data in grouped.values() for s in impl_data})
    scale_style = {
        s: {"marker": markers[i % len(markers)]}
        for i, s in enumerate(all_scales_for_lines)
    }

    plot_lines(grouped, axes[0], scale_style, y_label, show_yx=show_yx, input_type=input_type)
    plot_heatmap(grids, all_ds, all_scales, axes[1], cmap=heatmap_cmap, y_label=y_label)

    fig.tight_layout(w_pad=6)
    return fig, passed


def main():
    parser = argparse.ArgumentParser(
        description="Plot max f(n) or relative error results for tests 2, 3, and 4."
    )
    parser.add_argument("impl_dir", type=Path,
                        help="e.g. results/raw_data/test2c/openblas")
    args = parser.parse_args()

    impl_dir = args.impl_dir
    impl = impl_dir.name
    input_type_dir = impl_dir.parent
    input_type = input_type_dir.name

    y_label_map = {
        "test2c":                r"max componentwise $f_A(n)$",
        "test3":                 r"max componentwise $f_B(n)$",
        "test2b_w_inner_permute": "max componentwise rel err",
        "test2b_w_outer_permute": "max componentwise rel err",
    }
    y_label = y_label_map.get(input_type, r"$f(n)$")

    filename = "max_rel_error.fp64" if "permute" in input_type else "max_f_of_n.fp64"

    paths = sorted(input_type_dir.glob(f"{impl}/**/{filename}"))
    if not paths:
        print(f"No f_of_n.fp64 files found for impl '{impl}' under {input_type_dir}")
        sys.exit(1)

    show_yx = "permute" not in input_type

    fig, passed = plot_max_vals(paths, y_label=y_label, show_yx=show_yx, input_type=input_type)

    output_dir = Path("results/figures")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = unique_output_path(output_dir / f"{input_type}_{impl}.png")
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"    Figure written to: {output_path}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
