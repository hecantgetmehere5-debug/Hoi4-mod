PY := .venv/bin/python
HOI4 ?= $(HOME)/Library/Application Support/Steam/steamapps/common/Hearts of Iron IV
MODDIR ?= $(HOME)/Documents/Paradox Interactive/Hearts of Iron IV/mod

.PHONY: setup fetch build test install

setup:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

fetch:
	$(PY) -m tools.fetch

build: fetch
	$(PY) -m tools.build all

test:
	$(PY) -m pytest -q

install:
	$(PY) -m tools.build install --moddir "$(MODDIR)"
