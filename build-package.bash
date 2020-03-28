#!/bin/bash

set -e

PYTHON=python3
out_dir=build/out

# may require this before: pip3 install wheel
# upload to PyPI with: twine upload dist/dlb-*.whl
"${PYTHON:?}" setup.py build --build-base="${out_dir}/setupbuild" bdist_wheel --dist-dir=dist
