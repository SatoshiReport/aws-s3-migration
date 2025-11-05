.PHONY: format lint type test check

CI_SHARED_ROOT ?= $(HOME)/ci_shared
export PYTHONPATH := $(CI_SHARED_ROOT)$(if $(PYTHONPATH),:$(PYTHONPATH))

# Repository layout overrides for shared CI targets
SHARED_SOURCE_ROOT := .
SHARED_TEST_ROOT := tests
SHARED_DOC_ROOT := .
FORMAT_TARGETS := $(SHARED_SOURCE_ROOT) $(SHARED_TEST_ROOT)
SHARED_PYRIGHT_TARGETS := $(SHARED_SOURCE_ROOT)
SHARED_PYLINT_TARGETS := $(SHARED_SOURCE_ROOT)

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
