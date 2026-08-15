#!/usr/bin/env python3
"""Print (and save) an ASCII impl x subtest summary table for a paper_artifact demo run.

Invoked at the end of each paper_artifact/demo_testN*.sh with the same
TEST_CONFIGS / DGEMM_CONFIGS arrays the script just looped over, e.g.:

    .venv/bin/python3 ./scripts/generate_summary_table.py \
        --name test1 \
        --test-configs "${TEST_CONFIGS[@]}" \
        --dgemm-configs "${DGEMM_CONFIGS[@]}"
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from plot_utils import load_matrix, parse_path_metadata

# Maps a demo_test_configs/<label>.mk stem to the results/raw_data subdirectory
# its output lands in. Most subtests share their own name; test4a/b are the
# exception because test4's INPUT_TYPE is pinned to test2b by the Makefile and
# the permute mode (not the TEST_CONFIG_MK name) picks the raw_data directory
# (see TEST4_OUTPUT_PATH in the root Makefile).
SUBTEST_RAW_DIR = {
    "test1a": "test1a",
    "test1b": "test1b",
    "test1c": "test1c",
    "test2a": "test2a",
    "test2b": "test2b",
    "test2c": "test2c",
    "test3": "test3",
    "test4a": "test2b_w_outer_permute",
    "test4b": "test2b_w_inner_permute",
}


def impl_name(dgemm_config_mk: str) -> str:
    text = Path(dgemm_config_mk).read_text()
    m = re.search(r"^\s*DGEMM_IMPL_NAME\s*:=\s*(\S+)", text, re.MULTILINE)
    if not m:
        raise ValueError(f"Could not find DGEMM_IMPL_NAME in {dgemm_config_mk}")
    return m.group(1)


def subtest_label(test_config_mk: str) -> str:
    return Path(test_config_mk).stem


def recovery_pct(c_path: Path, raw_dir: Path) -> float:
    mask_path = raw_dir / "target_value_mask" / c_path.parent.parent.name / c_path.parent.name / "values.fp64"
    if not mask_path.exists():
        return np.nan

    c_vals = load_matrix(c_path)
    mask_vals = load_matrix(mask_path)
    d = parse_path_metadata(c_path)["d"]

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


def metric_for_cell(subtest_dir_name: str, impl: str):
    """Returns (value, kind); kind is 'pct' or 'float'. (None, None) if no data found."""
    impl_dir = Path("results/raw_data") / subtest_dir_name / impl
    if not impl_dir.is_dir():
        return None, None

    # max_f_of_n.fp64 / max_rel_error.fp64 take priority: test2/test3 dump both
    # a values.fp64 (the raw C matrix) and max_f_of_n.fp64, but only the latter
    # is the metric of interest there. values.fp64 + a target_value_mask
    # sibling (test1-only) is what makes a subtest a recovery-pct subtest.
    for filename in ("max_f_of_n.fp64", "max_rel_error.fp64"):
        paths = sorted(impl_dir.glob(f"**/{filename}"))
        if paths:
            vals = [np.fromfile(p, dtype=np.float64)[0] for p in paths]
            return max(vals), "float"  # worst-case cell if more than one (s, d) point exists

    raw_dir = impl_dir.parent
    if (raw_dir / "target_value_mask").is_dir():
        c_paths = sorted(impl_dir.glob("**/values.fp64"))
        pcts = [p for p in (recovery_pct(c, raw_dir) for c in c_paths) if not np.isnan(p)]
        if pcts:
            return min(pcts), "pct"  # worst-case cell if more than one (s, d) point exists

    return None, None


def format_value(val, kind) -> str:
    if val is None:
        return "-"
    if kind == "pct":
        return f"{val:.1f}%"
    if not np.isfinite(val):
        return "NaN" if np.isnan(val) else ("+INF" if val > 0 else "-INF")
    return f"{val:.3e}"


def render_table(row_labels, col_labels, cells) -> str:
    col_widths = [
        max(len(col_labels[j]), max((len(cells[i][j]) for i in range(len(row_labels))), default=0))
        for j in range(len(col_labels))
    ]
    row_header_width = max([len("impl")] + [len(r) for r in row_labels])

    def hline(char):
        parts = [char * (row_header_width + 2)] + [char * (w + 2) for w in col_widths]
        return "+" + "+".join(parts) + "+"

    def fmt_row(header, values):
        parts = [f" {header:<{row_header_width}} "]
        parts += [f" {v:>{w}} " for v, w in zip(values, col_widths)]
        return "|" + "|".join(parts) + "|"

    lines = [hline("="), fmt_row("impl", col_labels), hline("=")]
    for row_label, row in zip(row_labels, cells):
        lines.append(fmt_row(row_label, row))
        lines.append(hline("-"))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Print and save an ASCII impl x subtest summary table for a paper_artifact demo run."
    )
    parser.add_argument("--name", required=True, help="table name, used for the output filename, e.g. test1")
    parser.add_argument("--test-configs", nargs="+", required=True,
                        help="TEST_CONFIG_MK paths that were run, in column order")
    parser.add_argument("--dgemm-configs", nargs="+", required=True,
                        help="DGEMM_CONFIG_MK paths that were run, in row order")
    args = parser.parse_args()

    for p in args.test_configs + args.dgemm_configs:
        if not Path(p).is_file():
            parser.error(
                f"no such file: {p!r} (pass each --test-configs/--dgemm-configs path as its "
                "own argument, not space-joined inside one quoted string)"
            )

    col_labels = [subtest_label(t) for t in args.test_configs]
    row_labels = [impl_name(d) for d in args.dgemm_configs]

    cells = []
    for impl in row_labels:
        row = []
        for label in col_labels:
            val, kind = metric_for_cell(SUBTEST_RAW_DIR.get(label, label), impl)
            row.append(format_value(val, kind))
        cells.append(row)

    table = render_table(row_labels, col_labels, cells)

    print()
    print(f"  Summary: {args.name}")
    print(table)

    output_dir = Path("results/figures")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.name}_summary_table.txt"
    output_path.write_text(table + "\n")
    print(f"    Table written to: {output_path}")


if __name__ == "__main__":
    main()
