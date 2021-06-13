import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.gcc
import dlb_contrib.gnubinutils
from typing import List, Union


source_directory = dlb.fs.Path('.')
output_directory = dlb.fs.Path('out/')


class CplusplusCompiler(dlb_contrib.gcc.CplusplusCompilerGcc):
    def get_extra_compile_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return ['-g']


with dlb.ex.Context():
    for library_source_directory in source_directory.list(name_filter=r'lib_.*'):

        with dlb.di.Cluster(f'library in {library_source_directory.as_string()!r}'):
            with dlb.di.Cluster(f'compile'), dlb.ex.Context():
                compile_results = [
                    CplusplusCompiler(source_files=[source_file],
                                      object_files=[output_directory / source_file.with_appended_suffix('.o')],
                                      include_search_directories=[source_directory]).start()
                    for source_file in library_source_directory.iterdir(name_filter=r'.+\.cpp', is_dir=False)
                ]
            with dlb.di.Cluster(f'link'):
                archive_file = output_directory / (library_source_directory.components[-1] + '.a')
                dlb_contrib.gnubinutils.Archive(object_files=[r.object_files[0] for r in compile_results],
                                                archive_file=archive_file).start()
