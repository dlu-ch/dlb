#!/bin/bash

set -e

PYTHON3=python3
COVERAGE3=coverage3

test_dir=test

(
    cd "./${test_dir:?}"  # as PyCharm does it
    if [ -n "$(which "${COVERAGE3:?}")" ]; then
        "${COVERAGE3:?}" run --source dlb -m unittest && "${COVERAGE3:?}" report
    else
        "${PYTHON3:?}" -m unittest
    fi
)
