.PHONY: build
build:
	python setup.py sdist bdist_wheel

.PHONY: deploy-to-pypi
deploy-to-pypi: build
	twine upload dist/*

.PHONY: clean
clean:
	rm dist/*
