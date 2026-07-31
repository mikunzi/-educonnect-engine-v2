PYTHON ?= python3.14

.PHONY: install install-dev format lint typecheck test check pre-commit clean

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]
	pre-commit install --hook-type pre-commit --hook-type pre-push

format:
	ruff format src tests examples

lint:
	ruff check src tests examples

typecheck:
	mypy src

test:
	pytest

check: lint typecheck test

pre-commit:
	pre-commit run --all-files

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info
