import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.partition
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
            # group multiple source files for the same compiler tool instance to reduce time
            # and space for dependency checking

            source_files = library_source_directory.list(name_filter=r'.+\.cpp', is_dir=False)
            source_file_groups = \
                dlb_contrib.partition.by_working_tree_path(source_files, number_of_groups=len(source_files) // 5)
            del source_files
            source_file_groups = dlb_contrib.partition.split_longer(source_file_groups, max_length=8)
            # source_file_groups contains lists of approx. 10 (max. 15) source file paths each

            with dlb.di.Cluster(f'compile'), dlb.ex.Context():
                compile_results = [
                    CplusplusCompiler(
                        source_files=g,
                        object_files=[output_directory / p.with_appended_suffix('.o') for p in g],
                        include_search_directories=[source_directory]
                    ).start()
                    for g in source_file_groups
                ]

            object_file_groups = [r.object_files for r in compile_results]
            object_files = [o for g in object_file_groups for o in g]

            with dlb.di.Cluster(f'link'):
                archive_file = output_directory / (library_source_directory.components[-1] + '.a')
                dlb_contrib.gnubinutils.Archive(object_files=object_files, archive_file=archive_file).start()
