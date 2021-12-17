#!/bin/bash

# Build documentation with Sphinx <https://www.sphinx-doc.org> in a virtual Python environment.
# Installs required packages from PyPI according to 'doc/requirements.txt'.
# Required Python version: see 'doc/requirements.txt'.

set -e

PYTHON3="${PYTHON3:-python3}"
DOT="${DOT:-dot}"  # required by sphinx.ext.graphviz, sphinx.ext.inheritance_diagram

RM=rm
CP=cp
MV=mv
CMP=cmp

script_dir="/${0:?}"
script_dir="${script_dir%/*}"
script_dir="${script_dir:1}"
script_dir="${script_dir:-.}"
cd -- "${script_dir}"

doc_dir=doc
doc_to_root=..
out_dir=build/out
sphinx_out_dir="${out_dir:?}/sphinx"
sphinxvenv_dir="${out_dir:?}/sphinxvenv"

if [ -f "${sphinxvenv_dir:?}/requirements.txt" ] \
    && "${CMP:?}" -- "${doc_dir:?}/requirements.txt" "${sphinxvenv_dir:?}/requirements.txt";
then
    printf '(re)use virtual environment: %q\n' "${sphinxvenv_dir:?}/bin/activate"
    source -- "${sphinxvenv_dir:?}/bin/activate"
else
    printf '(re)create virtual environment: %q\n' "${sphinxvenv_dir:?}/bin/activate"
    "${RM:?}" -rf -- "./${sphinxvenv_dir:?}"
    "${PYTHON3:?}" -m venv "./${sphinxvenv_dir:?}"
    source -- "${sphinxvenv_dir:?}/bin/activate"
    pip install --upgrade -r "./${doc_dir:?}/requirements.txt"
    "${CP:?}" -- "${doc_dir:?}/requirements.txt" "${sphinxvenv_dir:?}/requirements.txt.t"
    "${MV:?}" -- "${sphinxvenv_dir:?}/requirements.txt.t" "${sphinxvenv_dir:?}/requirements.txt"
fi

sphinxbuild_file="$(command -v sphinx-build || echo)"
sphinxvenv_abs_dir="${PWD:?}/${sphinxvenv_dir:?}"
if [ -z "${sphinxbuild_file}" ] || ! [ -f "${sphinxbuild_file}" ] \
    || [ "${sphinxbuild_file:0:${#sphinxvenv_abs_dir}+1}" != "${sphinxvenv_abs_dir:?}/" ];
then
    printf "error: 'sphinx-build' not found in virtual environment: %q\n" "${sphinxvenv_dir:?}" >&2
    exit 1
fi

dot_file="$(command -v dot || echo)"
if [ -z "${dot_file}" ] || ! [ -f "${dot_file}" ]; then
    printf "error: 'dot' not found\n" >&2
    exit 1
fi

# list of builders: https://www.sphinx-doc.org/en/master/usage/builders/index.html
# most important: html, linkcheck, man
builders=("$@")
if [ "${#builders[@]}" -eq 0 ]; then
    builders=(html linkcheck)
fi

(
    cd "./${doc_dir:?}"  # as readthedocs does it
    "${RM:?}" -rf -- "./${doc_to_root:?}/${sphinx_out_dir:?}"
    sphinx_args=("-d" "./${doc_to_root:?}/${sphinx_out_dir:?}/doctrees")
    for builder in "${builders[@]}"; do
        "${sphinxbuild_file:?}" "${sphinx_args[@]}" -b "${builder:?}" \
            -D graphviz_dot="${dot_file:?}" \
            . "./${doc_to_root:?}/${sphinx_out_dir:?}/${builder:?}"
    done
)
