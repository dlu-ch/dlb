#!/bin/bash

set -e

RM=rm
PYTHON=python3
out_dir=build/out
setup_build_dir="${out_dir}/setupbuild"

# may require this before: pip3 install wheel
# upload to PyPI with: twine upload dist/dlb-*.whl
"${RM:?}" -rf -- "${setup_build_dir:?}"
"${PYTHON:?}" setup.py build --build-base="${setup_build_dir:?}" bdist_wheel --dist-dir=dist
