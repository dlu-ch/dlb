#!/bin/bash

set -e

PYTHON=python3
output_dir=out

"${PYTHON:?}" setup.py build --build-base="${output_dir}/build" bdist_wheel --dist-dir=dist
