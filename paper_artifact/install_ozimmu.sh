#! /bin/bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
VERSION_HASH=08eea92

mkdir -p ${REPO_ROOT}/submodules
cd ${REPO_ROOT}/submodules

# clean
rm -rf ozIMMU-${VERSION_HASH}

# acquire
if ! git clone https://github.com/enp1s0/ozIMMU --recursive; then
    exit 1
fi

mv ozIMMU ozIMMU-${VERSION_HASH}
cd ozIMMU-${VERSION_HASH}

# checkout specific commit
git checkout ${VERSION_HASH}

# build
mkdir build
cd build
cmake ..
make -j4