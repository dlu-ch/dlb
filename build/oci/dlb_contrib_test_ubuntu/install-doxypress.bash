#!/bin/bash

set -e
set -o pipefail

CURL=curl
AWK=awk
TAR=tar
MKDIR=mkdir
MKTEMP=mktemp
CP=cp
RM=rm

base_url="https://download.copperspice.com/doxypress/binary"

cd /tmp

archive_filename=($(
    "${CURL:?}" --silent "${base_url:?}/sha512.txt" \
    | "${AWK:?}" '/^[0-9a-f]+ \*doxypress-[0-9.]+-ubuntu[0-9.]+-[a-z0-9]+\.tar\.bz2$/ {print substr($2, 2)}' \
    | sort -r
))
archive_filename="${archive_filename[0]}"

if [ -z "${archive_filename}" ]; then
    printf 'error: no doxypress for Ubuntu found in sha512.txt\n' >&2
    exit 1
fi

archive_url="${base_url:?}/${archive_filename:?}"
archive_file="doxypress.tar.bz2"

temp_dir="$("${MKTEMP:?}" -d)"
function clear_temp() { "${RM:?}" -rf -- "${temp_dir:?}"; }
trap clear_temp EXIT

printf 'downloading %q...\n' "${archive_url:?}"
"${CURL:?}" --silent -o "${temp_dir:?}/${archive_file}" "${archive_url:?}"

printf 'extracting downloaded %q...\n' "${archive_file:?}"
"${MKDIR:?}" -- "${temp_dir:?}/a"
"${TAR:?}" -C "${temp_dir:?}/a" -xf "${temp_dir:?}/${archive_file}"

printf 'installing...\n'
"${CP:?}" -ar -- "${temp_dir:?}/a/"* "/usr/local/bin/"

printf 'done\n'
