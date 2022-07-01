#!/bin/bash

# Runs tests for the given packages with or without generation of a coverage report.
#
# The status and result (pass/fail) of running tests is written to standard error output.
# The output (standard output and standard error output) of tests is written to standard output.
#
# A coverage report 'build/out/test/*/coverage.log' is generated, if the environment variable PYTHON3COVERAGE is not
# empty; it then must be the name (found in the executable search paths) or path of python3-coverage.
#
# After successful execution, there is a file 'build/out/test/skipped.log' that contains a line for each skipped test.
#
# Usage example:
#
#     PYTHON3COVERAGE= run-tests.bash  # all packages, without coverage report
#     run-tests.bash dlb  # only package dlb, with coverage report

set -e
set -o pipefail
shopt -s nullglob

PYTHON3="${PYTHON3:-python3}"
PYTHON3COVERAGE="${PYTHON3COVERAGE}"  # Debian: 'python3-coverage', pip3: 'coverage3'
RM=rm
MV=mv
MKDIR=mkdir
TEE=tee
GREP=grep
FIND=find

PYTHONWARNINGS="${PYTHONWARNINGS:-error::DeprecationWarning,error::PendingDeprecationWarning}"

script_dir="/${0:?}"
script_dir="${script_dir%/*}"
script_dir="${script_dir:1}"
script_dir="${script_dir:-.}"
cd -- "${script_dir}"

test_dir=test
test_out_dir="build/out/test"
test_report_name="report.log"
test_output_name="stdout_and_stderr.log"

packages_under_test=("$@")
if [ "${#packages_under_test[@]}" -eq 0 ]; then
    packages_under_test=(dlb dlb_contrib)
fi

if [ "${EUID:?}" -eq 0 ]; then
    printf "error: must not be executed with 'root' privileges\n" >&2
    exit 1
fi

"${RM:?}" -rf -- "${test_out_dir:?}"
trap 'printf "\ntest failed\n" >&2' EXIT

for package_under_test in "${packages_under_test[@]}"; do
(
    cd "./${test_dir:?}/${package_under_test:?}"  # as PyCharm does it

    root_dir="../.."
    test_report_dir="${root_dir:?}/${test_out_dir:?}/${package_under_test:?}"
    test_report="${test_report_dir:?}/${test_report_name:?}"
    test_output="${test_report_dir:?}/${test_output_name:?}"
    "${MKDIR:?}" -p -- "${test_report_dir:?}"

    (
        (
            for f in test_*.bash; do
                "${BASH:?}" "./${f:?}"
            done
        ) 4>&1- 1>&2 3>&4 \
        | "${TEE:?}" -- "${test_report:?}.t"
    ) 3>&2 2>&1 1>&3- | "${TEE:?}" -- "${test_output:?}.t"

    "${MV:?}" -- "${test_output:?}.t" "${test_output:?}"
    "${MV:?}" -- "${test_report:?}.t" "${test_report:?}"

    # tests in different test contexts are run in different Python interpreter processes
    for context_dir in *; do
        if ! [[ "${context_dir:?}" =~ ^0|[1-9][0-9]*$ ]]; then
            continue
        fi

        test_report_dir="${root_dir:?}/${test_out_dir:?}/${package_under_test:?}/${context_dir:?}"
        test_report="${test_report_dir:?}/${test_report_name:?}"
        test_output="${test_report_dir:?}/${test_output_name:?}"
        "${MKDIR:?}" -p -- "${test_report_dir:?}"

        command=("${PYTHON3:?}")
        if [ -n "${PYTHON3COVERAGE}" ]; then
            command=("${PYTHON3COVERAGE:?}" run -p --source "${root_dir:?}/src/${package_under_test:?}")
        fi

        # Run all test files with same test context index in same Python process, each with a different data file.
        (
            # unittest_dlb writes report to file descriptor 3.
            PYTHONPATH="${root_dir:?}/${test_dir:?}" PYTHONWARNINGS="${PYTHONWARNINGS}" \
                "${command[@]}" -m unittest_dlb discover --start-directory "${context_dir:?}" \
                4>&1- 1>&2 3>&4 \
            | "${TEE:?}" -- "${test_report:?}.t"
        ) 3>&2 2>&1 1>&3- | "${TEE:?}" -- "${test_output:?}.t"
        # Redirect file descriptor 3 from unittest_dlb to stderr and "${test_report:?}.t", and
        # redirect file descriptors 1, 2 from unittest_dlb to stdout and "${test_report:?}.t".

        "${MV:?}" -- "${test_output:?}.t" "${test_output:?}"
        "${MV:?}" -- "${test_report:?}.t" "${test_report:?}"
    done

    if [ -n "${PYTHON3COVERAGE}" ]; then
        printf 'preparing coverage report\n' >&2
        "${PYTHON3COVERAGE:?}" erase  # removes '.coverage' but not '.coverage.*'
        "${PYTHON3COVERAGE:?}" combine  # creates/overwrite/appends '.coverage', removes '.coverage.*'
        # before PYTHON3COVERAGE 4.2: appends

        coverage_report="${root_dir:?}/${test_out_dir:?}/${package_under_test:?}/coverage.log"
        "${PYTHON3COVERAGE:?}" report --show-missing | "${TEE:?}" -- "${coverage_report:?}.t" >&2
        "${MV:?}" -- "${coverage_report:?}.t" "${coverage_report:?}"
    fi
)
done

# Summarize all skipped tests
(
    cd "./${test_out_dir:?}"
    skipped_report="skipped.log"
    "${FIND:?}" . -name "${test_report_name:?}" -exec "${GREP:?}" -e ' \.\.\. skipped ' {} \; > "${skipped_report:?}.t"
    "${MV:?}" -- "${skipped_report:?}.t" "${skipped_report:?}"

    if [ -s "${skipped_report:?}" ]; then
        printf '\nSkipped tests:\n%s\n' "$(<"${skipped_report:?}")" >&2
    fi
)

trap - EXIT
printf '\ntest of packages was successful: %s\n' "${packages_under_test[*]}" >&2
