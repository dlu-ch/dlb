#!/bin/bash

set -e

PYTHON=python3
out_dir=build/out

# may require this before: pip3 install wheel
"${PYTHON:?}" setup.py build --build-base="${out_dir}/setupbuild" bdist_wheel --dist-dir=dist
