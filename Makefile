.PHONY: format lint type test check

CI_SHARED_ROOT ?= $(HOME)/ci_shared
export PYTHONPATH := $(CI_SHARED_ROOT)$(if $(PYTHONPATH),:$(PYTHONPATH))

# ============================================================================
# AWS REPOSITORY CONFIGURATION
# ============================================================================
# This repo uses a flat structure (source at root, not in src/)
SHARED_SOURCE_ROOT := .
SHARED_TEST_ROOT := tests
SHARED_DOC_ROOT := .

# ============================================================================
# STRICT STANDARDS ARE ENFORCED - THESE CANNOT BE OVERRIDDEN
# ============================================================================
# The following settings are MANDATORY and defined in ci_shared.mk:
# - SHARED_PYTEST_THRESHOLD := 80          (80% coverage required)
# - COVERAGE_GUARD_THRESHOLD := 80         (coverage guard enforced)
# - ENABLE_PYLINT := 1                     (pylint always runs)
# - COMPLEXITY_MAX_CYCLOMATIC := 10        (max cyclomatic complexity)
# - COMPLEXITY_MAX_COGNITIVE := 15         (max cognitive complexity)
# - MODULE_MAX_LINES := 400                (max module size)
# - FUNCTION_MAX_LINES := 80               (max function size)
# - SHARED_PYRIGHT_TARGETS := . tests      (type check ALL code)
# - SHARED_PYLINT_TARGETS := . tests       (lint ALL code)
#
# If CI fails, FIX THE CODE to meet these standards.
# Do not try to override these values - they will be ignored.

# ============================================================================
# ALLOWED CUSTOMIZATIONS
# ============================================================================

include ci_shared.mk

# Exclude standalone CLI scripts from unused module check
UNUSED_MODULE_GUARD_ARGS := --root $(SHARED_SOURCE_ROOT) --exclude tests conftest.py __init__.py cost_toolkit/scripts/rds

format:
	black $(FORMAT_TARGETS)

lint:
	ruff check $(RUFF_TARGETS)

type:
	pyright $(PYRIGHT_TARGETS)

test:
	pytest $(PYTEST_TARGET)

check: shared-checks ## Run shared CI pipeline.
