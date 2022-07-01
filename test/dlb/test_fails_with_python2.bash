#!/bin/bash

set -e

PYTHON2=python2

script_dir="/${0:?}"
script_dir="${script_dir%/*}"
script_dir="${script_dir:1}"
script_dir="${script_dir:-.}"
path_to_root=../..
cd -- "${script_dir:?}"

python2="$(command -v "${PYTHON2:?}" || echo)"
if [ -z "${python2}" ]; then
    echo "${0##*/} ... skipped 'requires Python 2'" >&3
    exit 0
fi

(
    trap 'echo error: ${0##*/} aborted' EXIT
    PYTHONPATH="${path_to_root:?}/src" "${PYTHON2:?}" <<EOF
try:
    import dlb
    assert False, "could import 'dlb'"
except AssertionError as e:
    msg = str(e)
    assert msg == 'requires Python 3.7 or higher', 'unexpected exception message: {!r}'.format(msg)
EOF
    trap - EXIT
)

echo "${0##*/} ... ok" >&3
