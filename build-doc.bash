#!/bin/bash

set -e

SPHINXBUILD=sphinx-build

doc_dir=doc
doc_to_root=..
out_dir=out
sphinx_out_dir="${out_dir:?}/sphinx"

(
    cd "./${doc_dir:?}"  # as readthedocs does it
    sphinx_args=("-d" "./${doc_to_root:?}/${sphinx_out_dir:?}/doctrees")
    "${SPHINXBUILD:?}" "${sphinx_args[@]}" -b html . "./${doc_to_root:?}/${sphinx_out_dir:?}/html"
    "${SPHINXBUILD:?}" "${sphinx_args[@]}" -b linkcheck  . "./${doc_to_root:?}/${sphinx_out_dir:?}/linkcheck"
)
