PYTHON ?= /usr/bin/env python

default: all

all:
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install

repo:
	cd tools && ./build_repo.sh ../alda/test/repo.json

test: repo
	$(PYTHON) alda/test/test_alda.py

clean:
	-rm -rf build
