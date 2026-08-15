#!/bin/bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd ${REPO_ROOT}

source "${SCRIPT_DIR}/artifact_env.sh"

TEST_CONFIGS=(
    ./paper_artifact/demo_test_configs/test4a.mk
    ./paper_artifact/demo_test_configs/test4b.mk
)

DGEMM_CONFIGS=(
    ./config_files/dgemm_configs/naive_triple_loop.mk
    ./config_files/dgemm_configs/ozaki1.mk
    ./config_files/dgemm_configs/ozaki2.mk
    ./config_files/dgemm_configs/strassen.mk
    ./config_files/dgemm_configs/strassen_w_outer_scaling.mk
)

for t in "${TEST_CONFIGS[@]}"
do
    for d in "${DGEMM_CONFIGS[@]}"
    do
        make run_test4 DGEMM_CONFIG_MK=${d} TEST_CONFIG_MK=${t}
    done
done

.venv/bin/python3 ./scripts/generate_summary_table.py \
    --name test4 \
    --test-configs "${TEST_CONFIGS[@]}" \
    --dgemm-configs "${DGEMM_CONFIGS[@]}"