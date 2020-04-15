#!/bin/bash

set -e

PYTHON3=python3
COVERAGE3=coverage3  # pip3
PYTHON3COVERAGE=python3-coverage  # Debian

test_dir=test/
packages_under_test=("$@")
if [ "${#packages_under_test[@]}" -eq 0 ]; then
    packages_under_test=(dlb dlb_contrib)
fi

for package_under_test in "${packages_under_test[@]}"; do
(
    cd "./${test_dir:?}/${package_under_test:?}"  # as PyCharm does it

    if [ -n "$(which "${COVERAGE3:?}")" ]; then
        coverage="${COVERAGE3:?}"
    elif [ -n "$(which "${PYTHON3COVERAGE:?}")" ]; then
        coverage="${PYTHON3COVERAGE:?}"
    fi

    if [ -n "${coverage}" ]; then
        "${coverage:?}" run --source "../../src/${package_under_test:?}" -m unittest \
            && "${coverage:?}" report --show-missing
    else
        "${PYTHON3:?}" -m unittest
    fi
)
done
