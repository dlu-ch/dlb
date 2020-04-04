import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.gcc
from typing import Iterable, Union


source_path = dlb.fs.Path('./')
output_path = dlb.fs.Path('out/')


class CplusplusCompiler(dlb_contrib.gcc.CplusplusCompilerGcc):
    def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return ['-g']


class Archive(dlb.ex.Tool):
    EXECUTABLE = 'ar'

    object_files = dlb.ex.Tool.Input.RegularFile[1:]()
    archive_file = dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False)

    async def redo(self, result, context):
        await context.execute_helper(self.EXECUTABLE, ['-cr', result.archive_file] + [p for p in result.object_files])


with dlb.ex.Context():

    for library_path in source_path.list(name_filter=r'lib_.*'):

        with dlb.di.Cluster(f'library in {library_path.as_string()!r}'):
            with dlb.di.Cluster(f'compile'), dlb.ex.Context():
                compile_results = [
                    CplusplusCompiler(source_file=source_file,
                                      object_file=output_path / source_file[1:].with_appended_suffix('.o'),
                                      include_search_directories=[source_path]).run()
                    for source_file in library_path.list(name_filter=r'.+\.cpp') if not source_file.is_dir()
                ]
            with dlb.di.Cluster(f'link'):
                archive_file = output_path / (library_path.components[-1] + '.a')
                Archive(object_files=[r.object_file for r in compile_results],
                        archive_file=archive_file).run()
