#! /bin/bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
VERSION_NUMBER=2.0

mkdir -p ${REPO_ROOT}/submodules
cd ${REPO_ROOT}/submodules

# clean
rm -rf blis-${VERSION_NUMBER}

# acquire src
if ! wget https://github.com/flame/blis/archive/refs/tags/${VERSION_NUMBER}.tar.gz; then
    exit 1
fi
tar -xvf ${VERSION_NUMBER}.tar.gz
rm ${VERSION_NUMBER}.tar.gz

cd ${REPO_ROOT}/submodules/blis-${VERSION_NUMBER}
make clean

CC=gcc ./configure --enable-threading=openmp auto

make -j 8 V=1