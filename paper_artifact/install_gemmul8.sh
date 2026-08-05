#! /bin/bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
VERSION_NUMBER=2.0.10

mkdir -p ${REPO_ROOT}/submodules
cd ${REPO_ROOT}/submodules

# clean
rm -rf GEMMul8-${VERSION_NUMBER}

# acquire
if ! wget https://github.com/RIKEN-RCCS/GEMMul8/archive/refs/tags/v${VERSION_NUMBER}.tar.gz; then
    exit 1
fi
tar -xvf v${VERSION_NUMBER}.tar.gz
rm v${VERSION_NUMBER}.tar.gz

cd GEMMul8-${VERSION_NUMBER}/GEMMul8

# # comment out any APIs not relevant to INT8 DGEMM for faster compilation
sed -i '102,114s/^/\/\/ /; 120,157s/^/\/\/ /' src/gemmul8.cu

make -j4 lib/libgemmul8.so