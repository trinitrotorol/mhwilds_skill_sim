.PHONY: test lint data-check

test:
	sh scripts/pyw -m pytest --capture=sys

lint:
	sh scripts/pyw -m ruff check .
	sh scripts/pyw -m ruff format --check .

data-check:
	sh scripts/pyw -m scripts.check_data
