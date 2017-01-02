#!/bin/bash

set -e

PYTHON3=python3

test_dir=test

(
    cd "./${test_dir:?}"  # as PyCharm does it
    "${PYTHON3:?}" -m unittest  # test discovery: since Python 3.2
)
