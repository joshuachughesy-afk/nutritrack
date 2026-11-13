# Everyday developer commands. Requires the virtualenv from the README (.venv).
PY ?= .venv/bin/python

.PHONY: test lint check run web debug assets

test:            ## run the test suite
	$(PY) -m pytest -q

lint:            ## static checks for common bug patterns
	$(PY) -m ruff check src tests

check: lint test ## what CI runs

run:             ## desktop window
	cd src && ../$(PY) main.py

web:             ## in the browser at http://localhost:8551
	cd src && NUTRITRACK_WEB=1 ../$(PY) main.py

debug:           ## web, with the "Simulate an error" button on Profile and verbose logs
	cd src && NUTRITRACK_WEB=1 NUTRITRACK_DEBUG=1 ../$(PY) main.py

assets:          ## re-render the bundled seasonal tree images after changing core/render3d.py
	$(PY) -c "import sys; sys.path.insert(0, 'src'); from nutritrack.core import render3d as r; \
	[open(f'src/assets/trees/{s}/{sp}_{st}.png', 'wb').write(r.tree_png(sp, st, 30, 128, s)) \
	 for s in r.SEASONS for sp in r.SPECIES_COLORS for st in range(6)]"
