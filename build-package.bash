#!/bin/bash

# Builds packages in dist/.
#
# Install the created Wheel archive with
#
#     pip3 install dist/dlb-*.whl

set -e

PYTHON="${PYTHON3:-python3}"

RM=rm

script_dir="/${0:?}"
script_dir="${script_dir%/*}"
script_dir="${script_dir:1}"
script_dir="${script_dir:-.}"
cd -- "${script_dir}"

out_dir=build/out
setup_build_dir="${out_dir}/setupbuild"

# may require this before: pip3 install wheel
# upload to PyPI with: twine upload dist/dlb-*.whl
"${RM:?}" -rf -- "${setup_build_dir:?}"
"${PYTHON:?}" setup.py build --build-base="${setup_build_dir:?}" bdist_wheel --dist-dir=dist
