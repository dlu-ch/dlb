import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.gcc
import dlb_contrib.gnubinutils
from typing import Iterable, Union


source_path = dlb.fs.Path('.')
output_path = dlb.fs.Path('out/')


class CplusplusCompiler(dlb_contrib.gcc.CplusplusCompilerGcc):
    def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return ['-g']


with dlb.ex.Context():

    library_paths = source_path.list(name_filter=r'lib_.*')
    api_version_files = [p / 'api_version.h' for p in library_paths]

    for library_path in library_paths:

        with dlb.di.Cluster(f'library in {library_path.as_string()!r}'):
            archive_file = output_path / (library_path.components[-1] + '.a')

            with dlb.ex.Context():
                # update mtime of directory if content has later mtime
                # (requires monotonic system time to detect all mtime changes)
                mtime = library_path.propagate_mtime()
                assert mtime is None or mtime <= dlb.ex.Context.active.working_tree_time_ns

                needs_update = dlb_contrib.generic.ResultRemover(
                    result_file=archive_file.with_appended_suffix('.uptodate')
                ).run(
                    force_redo=dlb_contrib.generic.Check(
                        input_directories=[library_path],  # with potentially changed mtime due to propagate_mtime()
                        input_files=api_version_files,
                        output_files=[archive_file]
                    ).run()
                )
                # after normal exit from this context, needs_update.result_file does not exist
                # if bool(needs_update) is True

            if needs_update:
                # take a closer look

                with dlb.di.Cluster(f'check API versioning'):
                    # make sure api_version.h is the non-.cpp file with the latest mtime
                    latest_path = library_path.find_latest_mtime(name_filter=r'(?!.+\.cpp$).+', recurse_name_filter='')
                    api_version_file = library_path / 'api_version.h'
                    if latest_path != api_version_file:
                        api_version_file.native.raw.touch()

                with dlb.di.Cluster(f'compile'), dlb.ex.Context():
                    compile_results = [
                        CplusplusCompiler(
                            source_files=[source_file],
                            object_files=[output_path / source_file.with_appended_suffix('.o')],
                            include_search_directories=[source_path]
                        ).run()
                        for source_file in library_path.iterdir(name_filter=r'.+\.cpp', is_dir=False)
                    ]

                with dlb.di.Cluster(f'link'):
                    dlb_contrib.gnubinutils.Archive(object_files=[r.object_files[0] for r in compile_results],
                                                    archive_file=archive_file).run()

                needs_update.result_file.native.raw.touch()  # mark successfull completion of update
            else:
                dlb.di.inform('skip')
