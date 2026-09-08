#!/bin/bash
#
# Resolves CUBLAS_SO_PATH and exports it. Meant to be sourced, not executed:
# both artifact_env.sh (to advertise the path to demo scripts) and any
# install script that links against cuBLAS (install_ozimmu.sh,
# install_gemmul8.sh) source this directly, so none of them depend on a
# particular sourcing order relative to one another.

unset CUBLAS_SO_PATH
if [ -n "${CUDA_HOME}" ]
then
    # covers both a standard CUDA Toolkit install (libcublas.so under
    # CUDA_HOME itself) and an NVIDIA HPC SDK install (CUDA_HOME is the
    # .../cuda/<ver> dir, with libcublas.so under the sibling math_libs/<ver>)
    CUBLAS_SO_PATH=$(find ${CUDA_HOME} ${CUDA_HOME}/../../math_libs -name "libcublas.so" 2>/dev/null | head -n 1 | xargs -r realpath)
fi
if [ -e "${CUBLAS_SO_PATH}" ]
then
    echo "Found libcublas.so at ${CUBLAS_SO_PATH}"
    export CUBLAS_SO_PATH
else
    echo "Warning: Could not find libcublas.so (CUDA_HOME=${CUDA_HOME:-unset})"
fi
