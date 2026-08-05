# === test4b subtest (inner permute) ===
# pair with: make run_test4 TEST_CONFIG_MK=paper_artifact/demo_test_configs/test4b.mk
# (test4's INPUT_TYPE is fixed to test2b by the Makefile; this file only
# selects the permute mode and overrides the sweep)

LOG2_MIN_DIM := 5
LOG2_MAX_DIM := 5

LOG2_MIN_SCALING_FACTOR := 500
LOG2_MAX_SCALING_FACTOR := 500
LOG2_INC_SCALING_FACTOR := 100

DUMP_A_B := 1

OUTER_PERMUTE := 0
INNER_PERMUTE := 10
