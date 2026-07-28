.DEFAULT_GOAL := help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: help build test knowledge-check knowledge-resolve knowledge-build knowledge-preview

help:
	@printf '%s\n' \
	  'make knowledge-check                         validate trusted theory/' \
	  'make knowledge-resolve QUERY="..."           resolve a curated reading bundle' \
	  'make knowledge-build                         safely build _site/' \
	  'make knowledge-preview                       preview a safe temporary projection' \
	  'make build                                   alias for knowledge-build' \
	  'make test                                    run the Python test suite'

knowledge-check:
	@$(PYTHON) -m scripts.knowledge check

knowledge-resolve:
	@if [ -z "$(strip $(QUERY))" ]; then \
	  printf '%s\n' 'Usage: make knowledge-resolve QUERY="research question"' >&2; \
	  exit 2; \
	fi
	@$(PYTHON) -m scripts.knowledge resolve --query "$(QUERY)"

knowledge-build:
	@$(PYTHON) -m scripts.knowledge build

knowledge-preview:
	@$(PYTHON) -m scripts.knowledge preview

build: knowledge-build

test:
	@$(PYTHON) -m unittest discover -s tests
