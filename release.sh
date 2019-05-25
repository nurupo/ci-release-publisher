#!/usr/bin/env bash

set -exo pipefail

rm -rf dist/ ci_release_publisher.egg-info/ build/ env/
virtualenv -p /usr/bin/python3 env
source env/bin/activate
pip install pytest twine
nano ci_release_publisher/__version__.py
python setup.py sdist bdist_wheel
pip install dist/*.whl
pytest
gpg -u 0x6F5509774B1EF0C2 --detach-sign -a dist/*.gz
gpg -u 0x6F5509774B1EF0C2 --detach-sign -a dist/*.whl
#twine upload --repository-url https://test.pypi.org/legacy/ dist/*
twine upload dist/*
deactivate
