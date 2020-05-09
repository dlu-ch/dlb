#!/bin/bash

set -e

SPHINXBUILD=sphinx-build
READLINK=readlink

script_dir="$("${READLINK:?}" -e -- "$0")"
script_dir="${script_dir%/*}"
cd -- "${script_dir}"

doc_dir=doc
doc_to_root=..
out_dir=build/out
sphinx_out_dir="${out_dir:?}/sphinx"

# list of builders: https://www.sphinx-doc.org/en/master/usage/builders/index.html
# most important: html, linkcheck, man
builders=("$@")
if [ "${#builders[@]}" -eq 0 ]; then
    builders=(html linkcheck)
fi

(
    cd "./${doc_dir:?}"  # as readthedocs does it
    rm -rf -- "./${doc_to_root:?}/${sphinx_out_dir:?}"
    sphinx_args=("-d" "./${doc_to_root:?}/${sphinx_out_dir:?}/doctrees")
    for builder in "${builders[@]}"; do
        "${SPHINXBUILD:?}" "${sphinx_args[@]}" -b "${builder:?}" \
            . "./${doc_to_root:?}/${sphinx_out_dir:?}/${builder:?}"
    done
)
