SHELL := /bin/bash

BIN_DIR     := bin
SRC_DIR     := src
INCLUDE_DIR := include
RESULTS_DIR := results/raw_data

include $(DGEMM_CONFIG_MK)
include config_files/common.mk

CONFIG_VARS := DGEMM_IMPL_NAME SO_PATH LDFLAGS RUN_PREFIX CXX USE_CUDA CXXFLAGS \
               OUTER_SCALING INNER_SCALING LOG2_MIN_DIM LOG2_MAX_DIM \
               LOG2_MIN_SCALING_FACTOR LOG2_MAX_SCALING_FACTOR LOG2_INC_SCALING_FACTOR \
               REFERENCE_GEMM DUMP_A_B VERBOSE
$(foreach v,$(CONFIG_VARS),$(eval $(v) := $$(strip $$($(v)))))

# test4 permute: default INNER_PERMUTE=1; override on the command line with
# INNER_PERMUTE=k or OUTER_PERMUTE=k (OUTER_PERMUTE takes precedence when non-zero)
OUTER_PERMUTE ?= 0
INNER_PERMUTE ?= 10

# test2b-rectangle shape: m = 2^(d+LOG2_M_OFFSET), n = 2^(d+LOG2_N_OFFSET), k = 2^(d+LOG2_K_OFFSET)
# for each sweep exponent d; the three offsets must be pairwise distinct so m, n, k differ.
# Override on the command line, e.g. LOG2_M_OFFSET=1 LOG2_N_OFFSET=0 LOG2_K_OFFSET=-1
LOG2_M_OFFSET ?= 0
LOG2_N_OFFSET ?= -1
LOG2_K_OFFSET ?= 1

# --- common CPPFLAGS (all test binaries) ---
COMMON_CPPFLAGS :=
COMMON_CPPFLAGS += -DDGEMM_IMPL_NAME=\"$(DGEMM_IMPL_NAME)\"
COMMON_CPPFLAGS += -DLOG2_MIN_DIM=$(LOG2_MIN_DIM)
COMMON_CPPFLAGS += -DLOG2_MAX_DIM=$(LOG2_MAX_DIM)
COMMON_CPPFLAGS += -DLOG2_MIN_SCALING_FACTOR=$(LOG2_MIN_SCALING_FACTOR)
COMMON_CPPFLAGS += -DLOG2_MAX_SCALING_FACTOR=$(LOG2_MAX_SCALING_FACTOR)
COMMON_CPPFLAGS += -DLOG2_INC_SCALING_FACTOR=$(LOG2_INC_SCALING_FACTOR)
COMMON_CPPFLAGS += -DREFERENCE_GEMM=$(REFERENCE_GEMM)
ifeq ($(USE_CUDA),1)
COMMON_CPPFLAGS += -DUSE_CUDA
endif
ifeq ($(VERBOSE),1)
COMMON_CPPFLAGS += -DVERBOSE
endif
ifeq ($(OUTER_SCALING),1)
COMMON_CPPFLAGS += -DOUTER_SCALING
endif
ifeq ($(INNER_SCALING),1)
COMMON_CPPFLAGS += -DINNER_SCALING
endif
ifeq ($(DUMP_A_B),1)
COMMON_CPPFLAGS += -DDUMP_A_B
endif

# --- test4 CPPFLAGS: INPUT_TYPE=test2b + one permute mode ---
TEST4_BASE_INPUT_TYPE := test2b
TEST4_CPPFLAGS := -DINPUT_TYPE=\"$(TEST4_BASE_INPUT_TYPE)\"
ifneq ($(OUTER_PERMUTE),0)
TEST4_CPPFLAGS += -DOUTER_PERMUTE=$(OUTER_PERMUTE)
TEST4_OUTPUT_PATH := $(TEST4_BASE_INPUT_TYPE)_w_outer_permute
else
TEST4_CPPFLAGS += -DINNER_PERMUTE=$(INNER_PERMUTE)
TEST4_OUTPUT_PATH := $(TEST4_BASE_INPUT_TYPE)_w_inner_permute
endif

# --- test2b-rectangle CPPFLAGS ---
TEST2B_RECT_INPUT_TYPE := test2b_rectangle
TEST2B_RECT_CPPFLAGS := -DINPUT_TYPE=\"$(TEST2B_RECT_INPUT_TYPE)\" \
                        -DLOG2_M_OFFSET=$(LOG2_M_OFFSET) -DLOG2_N_OFFSET=$(LOG2_N_OFFSET) -DLOG2_K_OFFSET=$(LOG2_K_OFFSET)

DGEMM_WRAPPER := $(SRC_DIR)/dgemm_wrapper.cpp

.PHONY: run run_test1 run_test2 run_test3 run_test4 run_test2b_rectangle grade $(BIN_DIR)/test1 $(BIN_DIR)/test2 $(BIN_DIR)/test3 $(BIN_DIR)/test4 $(BIN_DIR)/test2b-rectangle compute_distribution_stats stats

# --- test binaries ---
$(BIN_DIR)/test1: $(SRC_DIR)/test1.cpp $(DGEMM_WRAPPER)
	@mkdir -p $(BIN_DIR)
	$(CXX) -std=c++17 $(CXXFLAGS) $(COMMON_CPPFLAGS) -DINPUT_TYPE=\"test1c\" -I$(INCLUDE_DIR) $^ $(LDFLAGS) -o $@

$(BIN_DIR)/test2: $(SRC_DIR)/test2.cpp $(DGEMM_WRAPPER)
	@mkdir -p $(BIN_DIR)
	$(CXX) -std=c++17 $(CXXFLAGS) $(COMMON_CPPFLAGS) -DINPUT_TYPE=\"test2c\" -I$(INCLUDE_DIR) $^ $(LDFLAGS) -o $@

$(BIN_DIR)/test3: $(SRC_DIR)/test3.cpp $(DGEMM_WRAPPER)
	@mkdir -p $(BIN_DIR)
	$(CXX) -std=c++17 $(CXXFLAGS) $(COMMON_CPPFLAGS) -DINPUT_TYPE=\"test3\" -I$(INCLUDE_DIR) $^ $(LDFLAGS) -o $@

$(BIN_DIR)/test4: $(SRC_DIR)/test4.cpp $(DGEMM_WRAPPER)
	@mkdir -p $(BIN_DIR)
	$(CXX) -std=c++17 $(CXXFLAGS) $(COMMON_CPPFLAGS) $(TEST4_CPPFLAGS) -I$(INCLUDE_DIR) $^ $(LDFLAGS) -o $@

$(BIN_DIR)/test2b-rectangle: $(SRC_DIR)/test2b-rectangle.cpp $(DGEMM_WRAPPER)
	@mkdir -p $(BIN_DIR)
	$(CXX) -std=c++17 $(CXXFLAGS) $(COMMON_CPPFLAGS) $(TEST2B_RECT_CPPFLAGS) -I$(INCLUDE_DIR) $^ $(LDFLAGS) -o $@

# --- run targets ---
run_test1: $(BIN_DIR)/test1
	@mkdir -p $(RESULTS_DIR)
	$(RUN_PREFIX) ./$(BIN_DIR)/test1
	.venv/bin/python3 ./scripts/plot_results_test_1.py $(RESULTS_DIR)/test1c/$(DGEMM_IMPL_NAME)

run_test2: $(BIN_DIR)/test2
	@mkdir -p $(RESULTS_DIR)
	$(RUN_PREFIX) ./$(BIN_DIR)/test2
	.venv/bin/python3 ./scripts/plot_results_test_2_3_4.py $(RESULTS_DIR)/test2c/$(DGEMM_IMPL_NAME)

run_test3: $(BIN_DIR)/test3
	@mkdir -p $(RESULTS_DIR)
	$(RUN_PREFIX) ./$(BIN_DIR)/test3
	.venv/bin/python3 ./scripts/plot_results_test_2_3_4.py $(RESULTS_DIR)/test3/$(DGEMM_IMPL_NAME)

run_test4: $(BIN_DIR)/test4
	@mkdir -p $(RESULTS_DIR)
	$(RUN_PREFIX) ./$(BIN_DIR)/test4
	.venv/bin/python3 ./scripts/plot_results_test_2_3_4.py $(RESULTS_DIR)/$(TEST4_OUTPUT_PATH)/$(DGEMM_IMPL_NAME)

# rectangular test2b: m, n, k pairwise distinct. Per-cell max f_A(n) is printed to stdout
# and written to $(RESULTS_DIR)/$(TEST2B_RECT_INPUT_TYPE)/; the plotting scripts assume
# m = n = k, so no figure is produced.
run_test2b_rectangle: $(BIN_DIR)/test2b-rectangle
	@mkdir -p $(RESULTS_DIR)
	$(RUN_PREFIX) ./$(BIN_DIR)/test2b-rectangle

run: run_test1 run_test2 run_test3 run_test4

# Run tests 1–3, capture pass/fail, and print a letter grade.
#   Grade A: test1 PASS and test2 PASS
#   Grade B: test3 PASS
#   Grade C: otherwise
grade: $(BIN_DIR)/test1 $(BIN_DIR)/test2 $(BIN_DIR)/test3 $(BIN_DIR)/test4
	@mkdir -p $(RESULTS_DIR); \
	echo;\
	echo " ** Administering Test 1"; \
	$(RUN_PREFIX) ./$(BIN_DIR)/test1; \
	.venv/bin/python3 ./scripts/plot_results_test_1.py $(RESULTS_DIR)/test1c/$(DGEMM_IMPL_NAME); p1=$$?; \
	echo;\
	echo " ** Administering Test 2"; \
	$(RUN_PREFIX) ./$(BIN_DIR)/test2; \
	.venv/bin/python3 ./scripts/plot_results_test_2_3_4.py $(RESULTS_DIR)/test2c/$(DGEMM_IMPL_NAME); p2=$$?; \
	echo;\
	echo " ** Administering Test 3"; \
	$(RUN_PREFIX) ./$(BIN_DIR)/test3; \
	.venv/bin/python3 ./scripts/plot_results_test_2_3_4.py $(RESULTS_DIR)/test3/$(DGEMM_IMPL_NAME); p3=$$?; \
	echo;\
	echo " ** Administering Test 4"; \
	$(RUN_PREFIX) ./$(BIN_DIR)/test4; \
	.venv/bin/python3 ./scripts/plot_results_test_2_3_4.py $(RESULTS_DIR)/$(TEST4_OUTPUT_PATH)/$(DGEMM_IMPL_NAME); \
	echo; \
	SEP="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	if [ $$p1 -eq 0 ] && [ $$p2 -eq 0 ]; then \
	    echo "$$SEP"; echo "  Grade: A  (test1 PASS, test2 PASS)"; echo "$$SEP"; \
	elif [ $$p3 -eq 0 ]; then \
	    echo "$$SEP"; echo "  Grade: B  (test3 PASS)"; echo "$$SEP"; \
	else \
	    echo "$$SEP"; echo "  Grade: C"; echo "$$SEP"; \
	fi

# --- standalone stats utility ---
$(BIN_DIR)/compute_distribution_stats: $(SRC_DIR)/compute_distribution_stats.cpp
	@mkdir -p $(BIN_DIR)
	$(CXX) -I$(INCLUDE_DIR) $^ -o $@

compute_distribution_stats stats: $(BIN_DIR)/compute_distribution_stats
