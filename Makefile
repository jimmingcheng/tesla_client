venv: venv/bin/activate

venv/bin/activate: poetry.lock
	python3 -m venv ./venv
	. venv/bin/activate && pip install poetry && poetry install

.PHONY: test
test: venv
	venv/bin/pytest tests/
	touch venv

.PHONY: package
package: venv
	rm -fr dist/*
	venv/bin/python setup.py sdist bdist_wheel

.PHONY: deploy-to-pypi
deploy-to-pypi: package
	venv/bin/twine upload dist/*

.PHONY: clean
clean:
	rm -fr dist/*
	rm -fr venv
