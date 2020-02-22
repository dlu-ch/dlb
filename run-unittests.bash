#!/bin/bash

set -e

PYTHON3=python3
COVERAGE3=coverage3  # pip3
PYTHON3COVERAGE=python3-coverage  # Debian

test_dir=test

(
    cd "./${test_dir:?}"  # as PyCharm does it

    if [ -n "$(which "${COVERAGE3:?}")" ]; then
        coverage="${COVERAGE3:?}"
    elif [ -n "$(which "${PYTHON3COVERAGE:?}")" ]; then
        coverage="${PYTHON3COVERAGE:?}"
    fi

    if [ -n "${coverage}" ]; then
        "${coverage:?}" run --source dlb -m unittest && "${coverage:?}" report --show-missing
    else
        "${PYTHON3:?}" -m unittest
    fi
)
