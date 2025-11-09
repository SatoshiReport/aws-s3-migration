.PHONY: format lint type test check

CI_SHARED_ROOT ?= $(HOME)/ci_shared
export PYTHONPATH := $(CI_SHARED_ROOT)$(if $(PYTHONPATH),:$(PYTHONPATH))

# Repository layout overrides for shared CI targets
SHARED_SOURCE_ROOT := .
SHARED_TEST_ROOT := tests
SHARED_DOC_ROOT := .
FORMAT_TARGETS := $(SHARED_SOURCE_ROOT) $(SHARED_TEST_ROOT)
SHARED_PYRIGHT_TARGETS := tests
SHARED_PYLINT_TARGETS := tests
PYLINT_ARGS := --disable=R0801
RUFF_TARGETS := tests
COMPLEXITY_GUARD_ARGS := --root $(SHARED_SOURCE_ROOT) --max-cyclomatic 35 --max-cognitive 60 --exclude cost_toolkit/scripts
MODULE_GUARD_ARGS := --root $(SHARED_SOURCE_ROOT) --max-module-lines 900
FUNCTION_GUARD_ARGS := --root $(SHARED_SOURCE_ROOT) --max-function-lines 400
UNUSED_MODULE_GUARD_ARGS := --root $(SHARED_SOURCE_ROOT) --exclude tests cost_toolkit/scripts duplicate_tree_cli_exports.py conftest.py __init__.py
ENABLE_PYLINT := 0
COVERAGE_GUARD_THRESHOLD := 0
SHARED_PYTEST_THRESHOLD := 0

include ci_shared.mk

format:
	black $(FORMAT_TARGETS)

lint:
	ruff check $(RUFF_TARGETS)

type:
	pyright $(PYRIGHT_TARGETS)

test:
	pytest $(PYTEST_TARGET)

check: shared-checks ## Run shared CI pipeline.
