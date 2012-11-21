PYTHON ?= /usr/bin/env python

default: all

all:
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install

clean:
	-rm -rf build
