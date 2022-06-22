#!/bin/bash

set -e

PYTHON3=python3

script_dir="/${0:?}"
script_dir="${script_dir%/*}"
script_dir="${script_dir:1}"
script_dir="${script_dir:-.}"
path_to_root=../..
cd -- "${script_dir:?}"

(
    trap 'echo error: ${0##*/} aborted' EXIT
    cd data/fakedlb
    path_to_root="../../${path_to_root:?}"
    script_output="$(PYTHONPATH="${path_to_root:?}/src" "${PYTHON3:?}" -m dlb_launcher script 2>/dev/null)"
    if [ "${script_output}" != "successfully completed." ]; then
        printf "unexpected script output: %q\n" "${script_output}"
        exit 1
    fi
    trap - EXIT
)

echo "${0##*/}: completed successfully"
