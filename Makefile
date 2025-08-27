SHELL := /bin/bash

.PHONY: setup format lint test bench report

setup:
	@python -m pip install -r requirements.txt

format:
	@black .

lint:
	@ruff check .
	@mypy orderbook

test:
	@pytest -q

bench:
	@python -m orderbook.cli bench --n-events 300000 --report results/

report:
	@python -m orderbook.cli sim --seed 30 --n-events 200000 --report results/
	@python -m orderbook.cli report --report results/
