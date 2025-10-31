# ci_shared.mk - Shared CI checks for kalshi/zeus
#
# This file contains the common CI pipeline checks used by both repositories.
# Include this in your Makefile with: include ci_shared.mk

# Shared variables (can be overridden in individual Makefiles)
SOURCE_DIRS ?= src
TEST_DIRS ?= tests
FORMAT_TARGETS ?= $(SOURCE_DIRS) $(TEST_DIRS)
RUFF_TARGETS ?= $(FORMAT_TARGETS)
PYLINT_TARGETS ?= $(SOURCE_DIRS) $(TEST_DIRS)
PYRIGHT_TARGETS ?= $(SOURCE_DIRS)
STATIC_ANALYSIS_TARGETS ?= $(FORMAT_TARGETS)
DOC_ROOT ?= .
PYTEST_NODES ?= 7
PYTHON ?= python
MAX_CLASS_LINES ?= 120
MAX_CYCLOMATIC_COMPLEXITY ?= 10
MAX_COGNITIVE_COMPLEXITY ?= 15
MAX_MODULE_LINES ?= 400
MAX_FUNCTION_LINES ?= 80
MAX_INHERITANCE_DEPTH ?= 2
MAX_PUBLIC_METHODS ?= 15
MAX_TOTAL_METHODS ?= 25
METHOD_GUARD_EXCLUDES ?=
STRUCTURE_GUARD_EXCLUDES ?=
COMPLEXITY_EXCLUDES ?=
MODULE_GUARD_EXCLUDES ?=
FUNCTION_GUARD_EXCLUDES ?=
INHERITANCE_GUARD_EXCLUDES ?=
DEPENDENCY_GUARD_EXCLUDES ?=
MAX_DEPENDENCY_INSTANTIATIONS ?= 5
COVERAGE_THRESHOLD ?= 80
PRIMARY_SOURCE_DIR ?= $(firstword $(SOURCE_DIRS))
PYTEST_TARGET ?= $(TEST_DIRS)
COMPILE_TARGETS ?= $(SOURCE_DIRS) $(TEST_DIRS)
CODESPELL_SKIP ?= ".git,artifacts,models,node_modules,logs,htmlcov,*.json,*.csv"
COVERAGE_DATA_FILE ?= $(CURDIR)/.coverage

export PYTHONDONTWRITEBYTECODE=1

# Shared CI check pipeline
.PHONY: shared-checks
shared-checks:
	@echo "Running shared CI checks..."
	@targets="$(strip $(FORMAT_TARGETS))"; \
	if [ -n "$$targets" ]; then \
		isort --profile black $$targets && \
		black $$targets; \
	else \
		echo "Skipping formatting (FORMAT_TARGETS unset)."; \
	fi
	@compile_targets="$(strip $(COMPILE_TARGETS))"; \
	if [ -n "$$compile_targets" ]; then \
		$(PYTHON) -m compileall $$compile_targets; \
	else \
		echo "Skipping bytecode compilation (COMPILE_TARGETS unset)."; \
	fi
	codespell --skip="$(CODESPELL_SKIP)" --quiet-level=2 --ignore-words=ci_shared/config/codespell_ignore_words.txt $(DOC_ROOT)
	@targets="$(strip $(STATIC_ANALYSIS_TARGETS))"; \
	if [ -n "$$targets" ]; then \
		vulture $$targets --min-confidence 80 && \
		deptry --config pyproject.toml $$targets; \
	else \
		echo "Skipping vulture/deptry (FORMAT_TARGETS unset)."; \
	fi
	$(PYTHON) -m ci_tools.scripts.policy_guard
	$(PYTHON) -m ci_tools.scripts.data_guard
	@if [ -n "$(strip $(PRIMARY_SOURCE_DIR))" ]; then \
		$(PYTHON) -m ci_tools.scripts.structure_guard --root $(PRIMARY_SOURCE_DIR) --max-class-lines $(MAX_CLASS_LINES) $(addprefix --exclude ,$(STRUCTURE_GUARD_EXCLUDES)) && \
		$(PYTHON) ci_shared/scripts/complexity_guard.py --root $(PRIMARY_SOURCE_DIR) --max-cyclomatic $(MAX_CYCLOMATIC_COMPLEXITY) --max-cognitive $(MAX_COGNITIVE_COMPLEXITY) $(addprefix --exclude ,$(COMPLEXITY_EXCLUDES)) && \
		$(PYTHON) -m ci_tools.scripts.module_guard --root $(PRIMARY_SOURCE_DIR) --max-module-lines $(MAX_MODULE_LINES) $(addprefix --exclude ,$(MODULE_GUARD_EXCLUDES)) && \
		$(PYTHON) -m ci_tools.scripts.function_size_guard --root $(PRIMARY_SOURCE_DIR) --max-function-lines $(MAX_FUNCTION_LINES) $(addprefix --exclude ,$(FUNCTION_GUARD_EXCLUDES)) && \
		$(PYTHON) -m ci_tools.scripts.inheritance_guard --root $(PRIMARY_SOURCE_DIR) --max-depth $(MAX_INHERITANCE_DEPTH) $(addprefix --exclude ,$(INHERITANCE_GUARD_EXCLUDES)) && \
		$(PYTHON) -m ci_tools.scripts.method_count_guard --root $(PRIMARY_SOURCE_DIR) --max-public-methods $(MAX_PUBLIC_METHODS) --max-total-methods $(MAX_TOTAL_METHODS) $(addprefix --exclude ,$(METHOD_GUARD_EXCLUDES)) && \
		$(PYTHON) -m ci_tools.scripts.dependency_guard --root $(PRIMARY_SOURCE_DIR) --max-instantiations $(MAX_DEPENDENCY_INSTANTIATIONS) $(addprefix --exclude ,$(DEPENDENCY_GUARD_EXCLUDES)); \
	else \
		echo "Skipping structural guards (no PRIMARY_SOURCE_DIR defined)."; \
	fi
	$(PYTHON) -m ci_tools.scripts.documentation_guard --root $(DOC_ROOT)
	@ruff_targets="$(strip $(RUFF_TARGETS))"; \
	if [ -n "$$ruff_targets" ]; then \
		ruff check --target-version=py310 --fix $$ruff_targets; \
	else \
		echo "Skipping ruff check (RUFF_TARGETS unset)."; \
	fi
	@pyright_targets="$(strip $(PYRIGHT_TARGETS))"; \
	if [ -n "$$pyright_targets" ]; then \
		pyright $$pyright_targets; \
	else \
		echo "Skipping pyright (PYRIGHT_TARGETS unset)."; \
	fi
	@pylint_targets="$(strip $(PYLINT_TARGETS))"; \
	if [ -n "$$pylint_targets" ]; then \
		pylint -j $(PYTEST_NODES) $$pylint_targets; \
	else \
		echo "Skipping pylint (PYLINT_TARGETS unset)."; \
	fi
	@pytest_target="$(strip $(PYTEST_TARGET))"; \
	if [ -n "$$pytest_target" ]; then \
		if [ -n "$(strip $(PRIMARY_SOURCE_DIR))" ]; then \
			pytest -n $(PYTEST_NODES) $$pytest_target --cov=$(PRIMARY_SOURCE_DIR) --cov-fail-under=$(COVERAGE_THRESHOLD) --strict-markers --cov-report=term -W error; \
		else \
			pytest -n $(PYTEST_NODES) $$pytest_target --strict-markers -W error; \
		fi; \
	else \
		echo "Skipping pytest (PYTEST_TARGET unset)."; \
	fi
	@if [ -n "$(strip $(PRIMARY_SOURCE_DIR))" ]; then \
		$(PYTHON) -m ci_tools.scripts.coverage_guard --threshold $(COVERAGE_THRESHOLD) --data-file "$(COVERAGE_DATA_FILE)"; \
	else \
		echo "Skipping coverage guard (no PRIMARY_SOURCE_DIR defined)."; \
	fi
	@echo "✅ All shared CI checks passed!"
