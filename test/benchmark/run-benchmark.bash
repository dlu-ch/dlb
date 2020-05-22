#!/usr/bin/env bash

# https://github.com/SCons/scons/wiki/WhySconsIsNotSlow
# Run benchmark as suggested by http://gamesfromwithin.com/the-quest-for-the-perfect-build-system.
# Result: text file $result_file with a line for each build configuration (duration in seconds)
#
# Some thoughts:
#
#  - This setup is not realistic with respect to compilation time, since the code consists only of class definitions
#    with empty constructors and destructors.
#
#  - It allows only one compiler process at a time which is not representative for a large project.
#
#  - The comparison of the build tools is not completely fair, since the amount of a-priori information put into
#    the "build configuration files" by 'generate_libs.py' varies between the build tools.
#
#  - However, it gives a reasonable idea of the (almost) worst-case where the dependency checking dominates
#    the build time.

set -e
shopt -s nullglob

RM=rm
CP=cp
MKDIR=mkdir
TOUCH=touch
GREP=grep
READLINK=readlink
CURL=curl
PYTHON2=python2
PYTHON3=python3
READLINK=readlink

script_dir="$("${READLINK:?}" -e -- "$0")"
script_dir="${script_dir%/*}"
cd -- "${script_dir}"

build_dir="../../build/out/benchmark/"
build_generated_dir="${build_dir:?}generated/"
result_file="${build_dir:?}result.txt"
setup_dir="setup/"

"${MKDIR:?}" -p -- "${build_dir:?}"
if ! [ -f  "${build_dir:?}/generate_libs.py" ]; then
    "${CURL:?}" -o "${build_dir:?}/generate_libs.py" \
        'http://www.gamesfromwithin.com/wp-content/uploads/bin/generate_libs_py.txt'
fi


# prepare project for Make, SCons and dlb in $build_generated_dir
function prepare_testdata() {
    "${RM:?}" -rf -- "${build_generated_dir:?}"
    "${MKDIR:?}" -p -- "${build_generated_dir:?}.dlbroot"

    "${PYTHON2:?}" "${build_dir:?}generate_libs.py" "${build_generated_dir:?}" "$@"

    for q in "${setup_dir:?}"top/* ; do "${CP:?}" -- "${q}" "${build_generated_dir:?}"; done
    for p in "${build_generated_dir:?}"lib_* ; do
        for q in "${setup_dir:?}"eachlib/* ; do "${CP:?}" -- "${q}" "${p}"; done
    done
}


function run_after_touch() {
    local f="$1"
    shift
    "${TOUCH:?}" -- "$f" && "$@"
}


# run "$@" in directory "$build_generated_dir" exactly $1 time and return average durations (wall time) in seconds
# in $duration and size of database file in bytes $filesize
function run_and_return_avg_duration() {
    local n="$1"
    local database_file_prefix="$2"
    shift 2

    local i
    declare -i i="$n"
    local start_time

    start_time="$("${PYTHON3:?}" -c "import time; print(time.time_ns())")"
    while [ "$i" -gt 0 ]; do
        (cd "${build_generated_dir:?}"; "$@") || return $?
        i=$((i-1))
    done
    duration="$("${PYTHON3:?}" -c "import time; print((time.time_ns() - ${start_time}) / 1e9 / ${n})")"

    filesize=0
    if [ -n "${database_file_prefix}" ]; then
        filesize="$(stat -c%s "${build_generated_dir:?}/${database_file_prefix}"*)"
    fi
}


function run_builds_return_avg_durations() {
    local number_of_runs="$1"
    local file_to_touch="$2"
    local database_file_prefix="$3"
    shift 3
    local duration

    durations=()
    filesizes=()

    echo "-- first (full)" >&2
    run_and_return_avg_duration 1 "${database_file_prefix}" "$@" || return $?
    durations+=("$duration")
    filesizes+=("$filesize")

    echo "-- second (full or empty, depending on build tool)" >&2
    run_and_return_avg_duration 1 "${database_file_prefix}" "$@" || return $?
    durations+=("$duration")
    filesizes+=("$filesize")

    echo "-- empty" >&2
    run_and_return_avg_duration "${number_of_runs}" "${database_file_prefix}" "$@" || return $?
    durations+=("$duration")
    filesizes+=("$filesize")

    echo "-- first partial" >&2
    run_and_return_avg_duration "${number_of_runs}" "${database_file_prefix}" run_after_touch "${file_to_touch}" "$@" || return $?
    durations+=("$duration")
    filesizes+=("$filesize")

    echo "-- seconds partial" >&2
    run_and_return_avg_duration "${number_of_runs}" "${database_file_prefix}" run_after_touch "${file_to_touch}" "$@" || return $?
    durations+=("$duration")
    filesizes+=("$filesize")
}


function run_build_and_append_results_to_result_file() {
    # $1 is number of runs to average for empty and partial builds
    # $2 is number of libraries; must be > 0
    # $3 is number of classes per library - must be >= max(15, 5) due to limitation of 'generate_libs.py'
    # $4 is name of the test (single word of printable, non-space characters)
    # $5 is path of database file or empty
    # $6 ...: build command to run with arguments

    local number_of_runs
    local number_of_libraries
    local number_of_classes_per_library
    local name="$4"
    local database_file_prefix="$5"
    declare -i number_of_runs="$1"
    declare -i number_of_libraries="$2"
    declare -i number_of_classes_per_library="$3"
    shift 5

    local file_to_touch="lib_0/class_0.cpp"
    prepare_testdata "${number_of_libraries}" "${number_of_classes_per_library}" 15 5
    result_line="${name:?} ${number_of_libraries} ${number_of_classes_per_library}"
    if run_builds_return_avg_durations "${number_of_runs}" "${file_to_touch}" "${database_file_prefix}" "$@"; then
        result_line="${result_line} ${durations[*]} ${filesizes[*]}"
    fi
    echo  "${result_line}" >> "${result_file:?}"
}


function run_builds_and_append_results_to_result_file() {
    # $1 is number of runs to average for empty and partial builds
    # $2 is number of libraries; must be > 0
    # $3 is number of classes per library - must be >= max(15, 5) due to limitation of 'generate_libs.py'
    local dlb_rundb_file_prefix=".dlbroot/runs-"

    run_build_and_append_results_to_result_file "$1" "$2" "$3" "make" "" "make"

    # based on example/c-minimal-gnumake
    run_build_and_append_results_to_result_file "$1" "$2" "$3" "make2" "" "./build-all"

    # based on example/c-minimal:
    run_build_and_append_results_to_result_file "$1" "$2" "$3" "dlb" "${dlb_rundb_file_prefix:?}" "dlb" "build-all"

    # based on example/c-huge:
    run_build_and_append_results_to_result_file "$1" "$2" "$3" "dlb2" "${dlb_rundb_file_prefix:?}" "dlb" "build-all2"

    run_build_and_append_results_to_result_file "$1" "$2" "$3" "dlb3" "${dlb_rundb_file_prefix:?}" "dlb" "build-all3"

    run_build_and_append_results_to_result_file "$1" "$2" "$3" "scons" ".sconsign.db" "scons"
}


echo "#" $(dlb --help | "${GREP:?}" -e '^dlb version:') > "${result_file:?}"
echo "#" $(make --version) >> "${result_file:?}"
echo "#" $(scons --version) >> "${result_file:?}"

run_builds_and_append_results_to_result_file 8 3 100
run_builds_and_append_results_to_result_file 4 3 500
run_builds_and_append_results_to_result_file 2 3 1000
run_builds_and_append_results_to_result_file 1 3 2000
run_builds_and_append_results_to_result_file 1 3 3500
run_builds_and_append_results_to_result_file 1 3 5000

run_builds_and_append_results_to_result_file 4 10 100
run_builds_and_append_results_to_result_file 2 20 100
run_builds_and_append_results_to_result_file 2 35 100

# orginal setup of http://gamesfromwithin.com/the-quest-for-the-perfect-build-system:
#
# The specific parameters I used for this test were:
#
#    50 static libraries
#    100 classes (2 files per class, .h and .cpp) per library
#    15 includes from that library in each class
#    5 includes from other libraries in each class

run_builds_and_append_results_to_result_file 2 50 100
