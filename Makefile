.PHONY: format lint type test check

PYTHON_SOURCES := $(filter-out ci_shared/% scripts/% tests/% docs/%,$(wildcard *.py))

SOURCE_DIRS := .
TEST_DIRS := tests
FORMAT_TARGETS := $(PYTHON_SOURCES) $(TEST_DIRS)
RUFF_TARGETS := $(FORMAT_TARGETS)
PYLINT_TARGETS := $(PYTHON_SOURCES)
PYRIGHT_TARGETS := tests
STATIC_ANALYSIS_TARGETS := .
DOC_ROOT := .
PRIMARY_SOURCE_DIR := .
STRUCTURE_GUARD_EXCLUDES := ci_shared docs scripts tests .venv
COMPLEXITY_EXCLUDES := ci_shared docs scripts tests .venv
MODULE_GUARD_EXCLUDES := ci_shared docs scripts tests .venv
FUNCTION_GUARD_EXCLUDES := ci_shared docs scripts tests .venv
INHERITANCE_GUARD_EXCLUDES := ci_shared docs scripts tests .venv
METHOD_GUARD_EXCLUDES := ci_shared docs scripts tests .venv
DEPENDENCY_GUARD_EXCLUDES := ci_shared docs scripts tests .venv
PYTEST_TARGET := tests
PYTEST_NODES := 1
COMPILE_TARGETS := $(PYTHON_SOURCES) $(TEST_DIRS)
COMPLEXITY_GUARD_PATH := ci_shared/scripts/complexity_guard.py
SHARED_SOURCE_ROOT := .
COMPLEXITY_GUARD_ARGS := --root $(SHARED_SOURCE_ROOT) --max-cyclomatic 10 --max-cognitive 15 $(foreach dir,$(COMPLEXITY_EXCLUDES),--exclude $(dir))

include ci_shared/ci_shared.mk

format:
	black $(FORMAT_TARGETS)

lint:
	ruff check $(RUFF_TARGETS)

type:
	pyright $(PYRIGHT_TARGETS)

test:
	pytest $(PYTEST_TARGET)

check: shared-checks ## Run shared CI pipeline.
