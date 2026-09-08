import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path

from plot_utils import load_matrix, parse_path_metadata, unique_output_path

FONTSIZE = 20


def compute_recovery_pct(c_vals, mask_vals, d):
    """
    mask NaN:  not a target entry
    mask 0.0:  true result is exactly 0; recovered iff C_ij == 0.0
    mask else: true result is a tiny nonzero; recovered iff C_ij is nonzero,
               has the same sign, and |C_ij| <= |target| * d
    """
    target = ~np.isnan(mask_vals)
    n_target = int(target.sum())
    if n_target == 0:
        return np.nan
    recovered = np.zeros(mask_vals.shape, dtype=bool)

    zero_target = target & (mask_vals == 0.0)
    recovered[zero_target] = (c_vals[zero_target] == 0.0)

    nonzero_target = target & (mask_vals != 0.0)
    tgt = mask_vals[nonzero_target]
    cmp = c_vals[nonzero_target]
    recovered[nonzero_target] = (
        (cmp != 0.0) &
        (np.sign(cmp) == np.sign(tgt)) &
        (np.abs(cmp) <= np.abs(tgt) * d)
    )

    return 100.0 * int(recovered[target].sum()) / n_target


def build_recovery_grid(input_type_dir, impl):
    """
    For each (s, d) cell found under input_type_dir/<impl>, load C and the
    co-located target_value_mask and compute recovery %.
    Returns (all_ds, all_scales, Z).
    """
    c_paths = sorted(input_type_dir.glob(f"{impl}/**/values.fp64"))
    if not c_paths:
        raise FileNotFoundError(
            f"No values.fp64 files found for impl '{impl}' under {input_type_dir}"
        )

    cells = {}
    for c_path in c_paths:
        mask_path = input_type_dir / "target_value_mask" / c_path.parent.parent.name / c_path.parent.name / "values.fp64"
        if not mask_path.exists():
            print(f"  warning: no mask found alongside {c_path}, skipping")
            continue
        meta = parse_path_metadata(c_path)
        s, d = meta["s"], meta["d"]
        c_vals   = load_matrix(c_path)
        mask_vals = load_matrix(mask_path)
        cells[(s, d)] = compute_recovery_pct(c_vals, mask_vals, d)

    if not cells:
        raise ValueError("No valid (C, mask) pairs found.")

    all_scales = sorted({s for s, _ in cells})
    all_ds     = sorted({d for _, d in cells})
    Z = np.full((len(all_scales), len(all_ds)), np.nan)
    for (s, d), pct in cells.items():
        Z[all_scales.index(s), all_ds.index(d)] = pct
    return all_ds, all_scales, Z


def plot_recovery_heatmap(all_ds, all_scales, Z):
    mpl.rcParams['font.family'] = 'serif'

    heat_w = max(6.0, len(all_ds) * 1.875)
    plot_h = max(6.0, len(all_scales) * 0.8)
    fig, ax = plt.subplots(figsize=(heat_w, plot_h))

    cmap = mpl.colormaps['Reds_r']
    norm = mpl.colors.Normalize(vmin=0, vmax=100)

    im = ax.imshow(Z, cmap=cmap, norm=norm, aspect='auto', origin='lower',
                   interpolation='nearest')

    labels = {(r, c): ("100%" if Z[r, c] >= 100.0 - 1e-9 else f"{Z[r, c]:.1f}%")
              for r in range(Z.shape[0]) for c in range(Z.shape[1])
              if np.isfinite(Z[r, c])}
    max_len = max((len(s) for s in labels.values()), default=5)
    cell_fontsize = FONTSIZE * min(1.0, 5 / max_len)

    for (r, c), label in labels.items():
        rgba = cmap(norm(Z[r, c]))
        luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
        ax.text(c, r, label,
                ha="center", va="center",
                fontsize=cell_fontsize,
                color="black" if luminance > 0.5 else "white")

    ax.set_xlabel("dimension (m = n = k)", fontsize=FONTSIZE)
    ax.set_ylabel("scale factor", fontsize=FONTSIZE)
    ax.set_xticks(range(len(all_ds)))
    ax.set_xticklabels(all_ds, fontsize=FONTSIZE, rotation=45, ha='right')
    ax.set_yticks(range(len(all_scales)))
    ax.set_yticklabels([rf"$2^{{\pm{s}}}$" for s in all_scales], fontsize=FONTSIZE)
    ax.tick_params(labelsize=FONTSIZE)

    ax.set_xticks([x - 0.5 for x in range(len(all_ds) + 1)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(len(all_scales) + 1)], minor=True)
    ax.grid(which='minor', color='black', linewidth=1.0)
    ax.tick_params(which='minor', length=0)

    cb = fig.colorbar(im, ax=ax, shrink=0.75)
    cb.set_label("Correct target values", fontsize=FONTSIZE)
    cb.set_ticks([0, 25, 50, 75, 100])
    cb.ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    cb.ax.tick_params(labelsize=FONTSIZE)

    fig.tight_layout()

    failures = [
        (all_scales[i], all_ds[j], Z[i, j])
        for i in range(len(all_scales))
        for j in range(len(all_ds))
        if np.isfinite(Z[i, j]) and Z[i, j] < 100.0 - 1e-9
    ]
    passed = len(failures) == 0
    if passed:
        print("    PASS: 100% of target values computed correctly")
    else:
        print(f"    FAIL: {len(failures)} cell(s) below 100%:")
        for s, d, val in failures:
            print(f"    scale=2^±{s}, dim={d}: {val:.2f}%")

    return fig, passed


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <impl_dir>")
        print(f"  e.g. {sys.argv[0]} results/raw_data/test1c/openblas")
        sys.exit(1)

    impl_dir = Path(sys.argv[1])
    impl = impl_dir.name
    input_type_dir = impl_dir.parent
    input_type = input_type_dir.name

    all_ds, all_scales, Z = build_recovery_grid(input_type_dir, impl)

    fig, passed = plot_recovery_heatmap(all_ds, all_scales, Z)

    output_dir = Path("results/figures")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = unique_output_path(output_dir / f"{input_type}_{impl}.png")
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"    Figure written to: {output_path}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
