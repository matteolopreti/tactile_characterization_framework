VENV := .venv
PYTHON ?= python

ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV)/Scripts/python
else
VENV_PY := $(VENV)/bin/python
endif

.PHONY: setup run clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e .

run:
	$(VENV_PY) main.py

clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage .coverage.*
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
