#!/bin/bash

set -e
shopt -s nullglob

PYTHON3=python3
COVERAGE3=coverage3  # pip3
PYTHON3COVERAGE=python3-coverage  # Debian

script_dir="/${0:?}"
script_dir="${script_dir%/*}"
script_dir="${script_dir:1}"
script_dir="${script_dir:-.}"
cd -- "${script_dir}"

test_dir=test
packages_under_test=("$@")
if [ "${#packages_under_test[@]}" -eq 0 ]; then
    packages_under_test=(dlb dlb_contrib)
fi

for package_under_test in "${packages_under_test[@]}"; do
(
    cd "./${test_dir:?}/${package_under_test:?}"  # as PyCharm does it

    for f in test_*.bash; do
        "${BASH:?}" "./${f:?}"
    done

    if [ -n "$(which "${COVERAGE3:?}")" ]; then
        coverage="${COVERAGE3:?}"
    elif [ -n "$(which "${PYTHON3COVERAGE:?}")" ]; then
        coverage="${PYTHON3COVERAGE:?}"
    fi

    # tests in different test contexts are run in different Python interpreter processes
    for context_dir in *; do
        if ! [[ "${context_dir:?}" =~ ^0|[1-9][0-9]*$ ]]; then
            continue
        fi

        # run all test files with same test context index in same Python process, each with a different data file
        command=("${PYTHON3:?}")
        if [ -n "${coverage}" ]; then
            command=("${coverage:?}" run -p --source "../../src/${package_under_test:?}")
        fi
        "${command[@]}" -m unittest discover --start-directory "${context_dir:?}"
    done

    if [ -n "${coverage}" ]; then
        "${coverage:?}" erase  # removes '.coverage' but not '.coverage.*'
        "${coverage:?}" combine  # creates/overwrite/appends '.coverage', removes '.coverage.*'
        # before coverage 4.2: appends

        "${coverage:?}" report --show-missing
    fi
)
done
