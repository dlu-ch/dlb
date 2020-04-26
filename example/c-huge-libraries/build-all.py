# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file.
#    python3 "$PWD"/build-all.py'   # in the directory of this file.

import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.gcc
import dlb_contrib.gnubinutils
import dlb_contrib.versioned_interface


# build library and enforce declared dependencies between libraries as well as API versioning
def build_library(*, library_path, archive_file, api_version_file, includeable_library_paths, output_path):
    with dlb.di.Cluster(f'check API version'):
        # compare hash of header file content with hash in 'api-version.h'
        dlb_contrib.versioned_interface.check_hash(
            # everything that does not end in '.c':
            files_to_hash=library_path.iterdir(name_filter=r'(?!.+\.c$).+', recurse_name_filter=''),
            hash_line_file=api_version_file,
            hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
            warnonly_hash=b'<none>'
        )

        # make sure api_version.h is the non-.c file with the latest mtime
        latest_path = library_path.find_latest_mtime(name_filter=r'(?!.+\.c$).+', recurse_name_filter='')
        if latest_path != api_version_file:
            api_version_file.native.raw.touch()

    with dlb.di.Cluster(f'compile'), dlb.ex.Context(max_parallel_redo_count=4):
        compile_results = [
            dlb_contrib.gcc.CCompilerGcc(
                source_files=[source_file],
                object_files=[output_path / source_file.with_appended_suffix('.o')],
                include_search_directories=[source_path]
            ).run()
            for source_file in library_path.iterdir(name_filter=r'.+\.c', is_dir=False)
        ]

    # enforce library dependencies described by *library_names*
    with dlb.di.Cluster(f'check included files'):
        n = len(library_path.parts)
        for r in compile_results:
            if r:
                for p in r.included_files:
                    if p[:n] not in includeable_library_paths:
                        raise Exception(f'{library_path.as_string()!r} must not depend on {p.as_string()!r}')

    with dlb.di.Cluster(f'link'):
        dlb_contrib.gnubinutils.Archive(object_files=[r.object_files[0] for r in compile_results],
                                        archive_file=archive_file).run()


# build huge C libraries (to many source files to check every time) when file in their source directory has changes
# of then 'api_version.h' of a library it depends on has changed.
with dlb.ex.Context():
    source_path = dlb.fs.Path('src/')
    output_path = dlb.fs.Path('build/out/')

    library_names = ['libx', 'liby']  # later may depend on earlier but not the other way around

    library_paths = [source_path / f'{n}/' for n in library_names]
    for i, library_path in enumerate(library_paths):

        with dlb.di.Cluster(f'library in {library_path.as_string()!r}'):
            api_version_files = [p / 'api-version.h' for p in library_paths[:i + 1]]
            api_version_file = api_version_files[-1]
            includeable_library_paths = frozenset(library_paths[:i + 1])
            archive_file = output_path / (library_path.components[-1] + '.a')

            with dlb.ex.Context():
                # update mtime of directory if content has later mtime
                # (requires monotonic system time to detect all mtime changes)
                mtime = library_path.propagate_mtime()
                assert mtime is None or mtime <= dlb.ex.Context.active.working_tree_time_ns

                needs_update = dlb_contrib.generic.ResultRemover(
                    result_file=output_path / f'check/{library_path.components[-1]}.complete'
                ).run(
                    force_redo=dlb_contrib.generic.Check(
                        input_directories=[library_path],  # with potentially changed mtime due to propagate_mtime()
                        input_files=api_version_files[:-1],
                        output_files=[archive_file]
                    ).run()
                )
                # after normal exit from this context, needs_update.result_file does not exist
                # if bool(needs_update) is True

            if needs_update:
                # take a closer look
                build_library(library_path=library_path, archive_file=archive_file,
                              api_version_file=api_version_file,
                              includeable_library_paths=includeable_library_paths,
                              output_path=output_path)
                needs_update.result_file.native.raw.touch()  # mark successfull completion of update
            else:
                dlb.di.inform('skip')
