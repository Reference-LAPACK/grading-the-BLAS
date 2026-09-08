import re
import numpy as np
from pathlib import Path

def load_matrix(path: str) -> np.ndarray:
    path = Path(path)
    match = re.search(r'm(\d+)_n(\d+)', str(path))
    if not match:
        raise ValueError(f"Could not extract m and n from path: {path}")
    m, n = int(match.group(1)), int(match.group(2))
    if path.suffix == ".fp64":
        data = np.fromfile(path, dtype=np.float64)
    elif path.suffix == ".fp128":
        data = np.fromfile(path, dtype=np.float128)
    else:
        raise ValueError(f"file extension is not one of .fp64 or .fp128: {path}")
    if data.size != m * n:
        raise ValueError(f"Expected {m*n} elements, got {data.size}")
    return data.reshape((m, n), order='F')

def unique_output_path(path: Path) -> Path:
    """Return path if it doesn't exist; otherwise return path.stem-1.ext, -2, … until free."""
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1

def reference_curves(input_type, xs):
    """Return [(ys, label), ...]: labeled reference curves to overlay on a
    dimension-vs-value plot for the given input_type, evaluated at xs."""
    xs = list(xs)
    if input_type == "test3":
        return [
            ([x ** 2 for x in xs], r"  $f_B(n)=n^2$"),
            (xs, r"  $f_B(n)=n$"),
        ]
    return [(xs, r"  $f_A(n)=n$")]

def parse_path_metadata(path: str) -> dict:
    """Extract scale factor s, dimension d (assuming m == n == k), impl name, and value descriptor from path."""
    path_str = str(path)
    scl_match = re.search(r'scl(\d+)', path_str)
    dim_match = re.search(r'm(\d+)_n(\d+)_k(\d+)', path_str)
    if not (scl_match and dim_match):
        raise ValueError(f"Could not parse scl/m/n/k from path: {path}")
    s = int(scl_match.group(1))
    m, n, k = (int(dim_match.group(i)) for i in (1, 2, 3))
    if not (m == n == k):
        raise ValueError(f"Expected m == n == k, got m={m}, n={n}, k={k} in {path}")
    impl_match = re.search(r'/([^/]+)/scl\d+/', path_str)
    impl_name = impl_match.group(1) if impl_match else Path(path).parent.name
    value_descriptor = Path(path).stem
    return {"s": s, "d": m, "impl": impl_name, "value_descriptor": value_descriptor}