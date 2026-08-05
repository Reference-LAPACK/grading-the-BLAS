#! /bin/bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
VERSION_NUMBER=3.12.1

mkdir -p ${REPO_ROOT}/submodules
cd ${REPO_ROOT}/submodules

# clean
rm -rf lapack-${VERSION_NUMBER}

# acquire src
if ! wget https://github.com/Reference-LAPACK/lapack/archive/refs/tags/v${VERSION_NUMBER}.tar.gz; then
    exit 1
fi
tar -xvf v${VERSION_NUMBER}.tar.gz
rm v${VERSION_NUMBER}.tar.gz


cd ${REPO_ROOT}/submodules/lapack-${VERSION_NUMBER}

make clean

cp INSTALL/make.inc.gfortran make.inc

# minimal build of LAPACK/BLAS
make -j 8 blaslib