#!/bin/bash

set -e

PYTHON3=python3

test_dir=test

(
    cd "./${test_dir:?}"  # as PyCharm does it
    for f in test_*.py; do
        "${PYTHON3:?}" -m unittest "$f"
    done
)
