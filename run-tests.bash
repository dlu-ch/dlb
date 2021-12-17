#!/bin/bash

# Runs tests with or without generation of a coverage report.
#
# Usage example:
#
#     PYTHON3COVERAGE= run-tests.bash  # all packages, without coverage report
#     run-tests.bash dlb  # only package dlb, with coverage report

set -e
shopt -s nullglob

PYTHON3="${PYTHON3:-python3}"
PYTHON3COVERAGE="${PYTHON3COVERAGE}"  # Debian: 'python3-coverage', pip3: 'coverage3'

PYTHONWARNINGS="${PYTHONWARNINGS:-error::DeprecationWarning,error::PendingDeprecationWarning}"

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

if [ "${EUID:?}" -eq 0 ]; then
    printf "error: must not be executed with 'root' privileges\n" >&2
    exit 1
fi

for package_under_test in "${packages_under_test[@]}"; do
(
    cd "./${test_dir:?}/${package_under_test:?}"  # as PyCharm does it

    for f in test_*.bash; do
        "${BASH:?}" "./${f:?}"
    done

    # tests in different test contexts are run in different Python interpreter processes
    for context_dir in *; do
        if ! [[ "${context_dir:?}" =~ ^0|[1-9][0-9]*$ ]]; then
            continue
        fi

        # run all test files with same test context index in same Python process, each with a different data file
        command=("${PYTHON3:?}")
        if [ -n "${PYTHON3COVERAGE}" ]; then
            command=("${PYTHON3COVERAGE:?}" run -p --source "../../src/${package_under_test:?}")
        fi
        PYTHONWARNINGS="${PYTHONWARNINGS}" "${command[@]}" -m unittest discover --start-directory "${context_dir:?}"
    done

    if [ -n "${PYTHON3COVERAGE}" ]; then
        printf 'preparing coverage report\n' >&2
        "${PYTHON3COVERAGE:?}" erase  # removes '.coverage' but not '.coverage.*'
        "${PYTHON3COVERAGE:?}" combine  # creates/overwrite/appends '.coverage', removes '.coverage.*'
        # before PYTHON3COVERAGE 4.2: appends

        "${PYTHON3COVERAGE:?}" report --show-missing
    fi
)
done
