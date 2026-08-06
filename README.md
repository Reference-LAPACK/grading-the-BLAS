# Grading the BLAS

A floating-point accuracy benchmarking harness for DGEMM implementations. The harness sweeps over matrix dimensions and input scaling factors, computes error metrics against a high-precision reference, and produces figures summarizing the results.

## Table of Contents

- [Requirements](#requirements)
- [One-time setup](#one-time-setup)
- [Specifying a Test Configuration](#specifying-a-test-configuration)
  - [DGEMM config](#dgemm-config-config_filesdgemm_configsmk)
  - [Sweep config](#sweep-config-config_filescommonmk)
- [Running the Tests](#running-the-tests)
- [Description of Tests](#description-of-tests)
- [Output structure](#output-structure)

---

## Requirements

1. A shared or static library exposing `dgemm_` via the standard BLAS Fortran API
2. A C++17 compiler
3. Python 3 (for data visualization)

## One-time setup

Install the Python plotting dependencies into the local virtual environment:

```bash
./scripts/install_plot_dependencies.sh
```

---

## Specifying a Test Configuration

### DGEMM config (`config_files/dgemm_configs/*.mk`)

Describes the implementation under test.

| Variable | Purpose |
|---|---|
| `DGEMM_IMPL_NAME` | Label used in output paths |
| `LIB_PATH` | Path to the library exposing the `dgemm_` symbol under test |
| `CXX` | Compiler (`g++`, or `nvcc` when `USE_CUDA=1`) |
| `CXX_FLAGS` / `LDFLAGS` | Compiler flags / linker flags |
| `USE_CUDA` | Set to `1` to wrap `cublasDgemm` instead of `dgemm_` |
| `RUN_PREFIX` | optional; string to be prepended to CL invocation of test binary, i.e., `${RUN_PREFIX} ./test1` |

See `config_files/dgemm_configs/` for ready-made examples (OpenBLAS, BLIS, cuBLAS, Strassen variants, Ozaki variants).

To add a new implementation: copy any existing file, set `DGEMM_IMPL_NAME`, and point `LIB_PATH`/`LDFLAGS` at your `.so`.

### Sweep config (`config_files/common.mk`)

Controls the parameter sweep shared across all four tests.

| Variable | Purpose |
|---|---|
| `LOG2_MIN_DIM` / `LOG2_MAX_DIM` | Parameterizes the sweep of dimensions according to pseudocode below |
| `LOG2_MIN_SCALING_FACTOR` / `LOG2_MAX_SCALING_FACTOR` / `LOG2_INC_SCALING_FACTOR` | Parameterizes the sweep of scaling factors according to pseudocode below |
| `REFERENCE_GEMM` | `1` = double-precision reference, `2` = long-double reference |
| `DUMP_A_B` | `1` = also write `A` and `B` to disk |
| `VERBOSE` | `1` = print `A`, `B`, and `C` to stdout |

```
for ( int d = LOG2_MIN_DIM; d <= LOG2_MAX_DIM; ++d ){
    // A and B have shape (2^d) x (2^d)
    ...
    for ( int s = LOG2_MIN_SCALING_FACTOR; s <= LOG2_MAX_SCALING_FACTOR; s += LOG2_INC_SCALING_FACTOR ){
        // entries in A and B span the orders of 2^-s to 2^s (note that LOG2_INC_SCALING_FACTOR must be >0)
        ...
        // execute DGEMM under test
        ...
}
```

---

## Running the Tests

```bash
# Run all tests
make grade DGEMM_CONFIG_MK=...

# Run individual tests
make run_test1 DGEMM_CONFIG_MK=...
make run_test2 DGEMM_CONFIG_MK=...
make run_test3 DGEMM_CONFIG_MK=...
make run_test4 DGEMM_CONFIG_MK=...
```

Figures are automatically written to `results/figures/<input_type>_<impl>.png`.

- **test1**: single heatmap — percentage of target values recovered (0–100%, `Reds_r` colormap)
- **test2 / test3 / test4**: line plot (one line per scale factor, log-log axes) + heatmap of the scalar max metric

Rerunning any target overwrites its output directory; no timestamped directories are created.

---

## Description of Tests

The harness has four test binaries, each targeting a different class of difficult input.

- **Test 1** : Inputs are largely sparse rows and columns whose nonzero entries span an extreme dynamic range, arranged so that each targeted output entry has a single, exactly-known tiny value hidden among contributions that cancel to exact zero. Stresses whether an implementation can recover small target values rather than losing them to absorption by far larger magnitudes. Referred to in the output structure on disk as `test1c`.

- **Test 2** : Rank-structured inputs with entries spanning a wide dynamic range and randomized sign patterns, so that each output entry is formed by heavy cancellation among positive and negative terms of very different sizes. Stresses accuracy under catastrophic cancellation combined with wide dynamic range. Referred to in the output structure on disk as `test2c`.

- **Test 3** : Entrywise-positive inputs whose rows and columns are scaled to span a wide range of magnitudes, so each dot product accumulates terms of widely varying size with no cancellation. Stresses accumulation accuracy across large magnitude spreads — whether small contributions survive when summed alongside dominant ones. Referred to in the output structure on disk as `test3`.

- **Test 4** : Inputs whose entries span an extreme dynamic range while the true products remain benign; the contraction dimension is randomly reordered across ten permutations and the worst relative error is reported. Stresses consistency of accuracy under reordering of the summation — sensitivity to accumulation order and internal blocking. Referred to in the output structure on disk as `test2b_w_inner_permute`.

---

## Output structure

```
results/
├── raw_data/
│   ├── test1c/
│   │   ├── <DGEMM_IMPL_NAME>/scl<s>/m<m>_n<n>_k<k>/
│   │   │   └── values.fp64                      # full C matrix (column-major float64)
│   │   │
│   │   └── target_value_mask/scl<s>/m<m>_n<n>_k<k>/
│   │       └── values.fp64                      # binary mask (cached on first run)
│   │
│   ├── test2c/
│   │   ├── <DGEMM_IMPL_NAME>/scl<s>/m<m>_n<n>_k<k>/
│   │   │   ├── values.fp64                      # full C matrix (column-major float64)
│   │   │   └── max_f_of_n.fp64                  # f_A(n) error metric
│   │   │
│   │   ├── C_ref/scl<s>/m<m>_n<n>_k<k>/
│   │   │   └── values.fp128                     # reference (high-precision, cached)
│   │   │
│   │   └── absA_absB_product/scl<s>/m<m>_n<n>_k<k>/
│   │       └── values.fp128                     # scale factor for computation of f_A(n) (cached)
│   │
│   ├── test3/
│   │   ├── <DGEMM_IMPL_NAME>/scl<s>/m<m>_n<n>_k<k>/
│   │   │   ├── values.fp64                      # full C matrix (column-major float64)
│   │   │   └── max_f_of_n.fp64                  # f_B(n) error metric
│   │   │
│   │   ├── C_ref/scl<s>/m<m>_n<n>_k<k>/
│   │   │   └── values.fp128                     # reference (high-precision, cached)
│   │   │
│   │   └── rowmax_absA_colmax_absB_product/scl<s>/m<m>_n<n>_k<k>/
│   │       └── values.fp128                     # scale factor for computation of f_B(n) (cached)
│   │
│   └── test2b_w_inner_permute/
│       └── <DGEMM_IMPL_NAME>/scl<s>/m<m>_n<n>_k<k>/
│           ├── values.fp64                      # full C matrix (column-major float64)
│           └── max_rel_error.fp64               # relative error metric
│
└── figures/
    ├── test1c_<impl>.png                        # heatmap (% of target recovered)
    ├── test2c_<impl>.png                        # line plot + heatmap
    ├── test3_<impl>.png                         # line plot + heatmap
    └── test2b_w_inner_permute_<impl>.png        # line plot + heatmap
```

**Cached reference data**: `C_ref`, `target_value_mask`, `absA_absB_product`, and `rowmax_absA_colmax_absB_product` are computed once and reused automatically across implementations.