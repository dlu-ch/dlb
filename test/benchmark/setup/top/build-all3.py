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

            # update mtime of directory if content has later mtime
            # (requires monotonic system time to detect all mtime changes)
            mtime = library_path.propagate_mtime()
            assert mtime is None or mtime <= dlb.ex.Context.active.working_tree_time_ns
            coarse_check = dlb_contrib.generic.Check(input_directories=[library_path], input_files=api_version_files,
                                                     output_files=[archive_file])
            fine_check_completion = dlb_contrib.generic.ResultRemover(
                result_file=archive_file.with_appended_suffix('.uptodate'))

            if fine_check_completion.run(force_redo=coarse_check.run()):
                # take a closer look

                with dlb.di.Cluster(f'check API versioning'), dlb.ex.Context():
                    latest_path = library_path.find_latest_mtime(name_filter=r'(?!.+\.cpp$).+', recurse_name_filter='')
                    if latest_path:
                        api_version_file = library_path / 'api_version.h'
                        if latest_path.native.raw.stat().st_mtime_ns > api_version_file.native.raw.stat().st_mtime_ns:
                            # api_version.h must not be older than any non-.cpp file in the library;
                            # check the changes and update api_version.h accordingly.
                            raise Exception(f'newer than {api_version_file.as_string()!r}: {latest_path.as_string()!r}')

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

                fine_check_completion.result_file.native.raw.touch()  # mark successfull completion of update
            else:
                dlb.di.inform('skip')
