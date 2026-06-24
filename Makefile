.PHONY: test lint data-check

test:
	python -m pytest

lint:
	python -m ruff check .
	python -m ruff format --check .

data-check:
	python -m scripts.check_data
