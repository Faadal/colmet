SHELL := /bin/bash

# Internal variables.
PACKAGE=colmet
# these files should pass flakes8
FLAKE8_WHITELIST=$(shell find . -name "*.py" \
                    ! -path "./docs/*" ! -path "./.tox/*" \
                    ! -path "./env/*" ! -path "./venv/*" \
                    ! -path "**/genetlink/*" \
                    ! -path "**/compat.py")

open := $(shell { which xdg-open || which open; } 2>/dev/null)

.PHONY: docs dist

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo "  init       to install the project in development mode (using virtualenv is highly recommended)"
	@echo "  clean      to remove build and Python file (.pyc) artifacts"
	@echo "  test       to run tests quickly with the default Python"
	@echo "  testall    to run tests on every Python version with tox"
	@echo "  ci         to run all tests and get junitxml report for CI (Travis, Jenkins...)"
	@echo "  coverage   to check code coverage quickly with the default Python"
	@echo "  lint       to check style with flake8"
	@echo "  sdist      to package"
	@echo "  release     to package and upload a release"
	@echo "  bumpversion to bump the release version number"
	@echo "  newversion  to set the new development version"

init:
	pip install -U setuptools pip tox ipdb jedi pytest pytest-cov flake8 bumpversion
	pip install -e .

clean:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	find . -name '*.pyc' -type f -exec rm -f {} +
	find . -name '*.pyo' -type f -exec rm -f {} +
	find . -name '*~' -type f -exec rm -f {} +
	find . -name '__pycache__' -type d -exec rm -rf {} +

test:
	py.test --verbose

testall:
	tox

ci:
	py.test --junitxml=junit.xml

coverage:
	py.test --verbose --cov-report term --cov-report html --cov=${PACKAGE} || true
	$(open) htmlcov/index.html

lint:
	flake8 $(FLAKE8_WHITELIST)

sdist: clean
	python setup.py sdist
	ls -l dist

release: clean
	python setup.py register
	python setup.py sdist upload

bumpversion:
	python scripts/bump-release-version.py

newversion:
	@python scripts/bump-dev-version.py $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
