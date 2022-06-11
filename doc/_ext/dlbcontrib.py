# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Documentation generation from dlb_contrib modules."""

import re
import collections
import importlib
import inspect
from typing import Tuple, List, Callable, Sequence
import docutils
import docutils.parsers.rst
import sphinx
import sphinx.addnodes
import sphinx.directives
import sphinx.domains
from sphinx.locale import _
import dlb.ex

DOMAIN_NAME = 'dlbcontrib'

DOCSTRING_REGEX = re.compile(r'^(?P<summary>.+\.)(\s|$)')
assert not DOCSTRING_REGEX.match('')
assert not DOCSTRING_REGEX.match('.')
assert not DOCSTRING_REGEX.match('a.b')
assert DOCSTRING_REGEX.match('a. b').group('summary') == 'a.'
assert DOCSTRING_REGEX.match('a.b.\nc').group('summary') == 'a.b.'

LICENSE_REGEX = re.compile(r'^ SPDX-License-Identifier: (?P<license>[A-Za-z][A-Za-z_\d.-]+)$')
assert LICENSE_REGEX.match(' SPDX-License-Identifier: LGPL-3.0-or-later').group('license') == 'LGPL-3.0-or-later'

DEFINITION_REGEX = re.compile(r'^ (?P<name>[^:]+): +(?P<value>.+)$')
assert DEFINITION_REGEX.match(' Git: https://git-scm.com/')

URL_REGEX = re.compile(r'(?P<before>^|\W)<(?P<url>[A-Za-z][A-Za-z\d+-.]*://[^<>\s]+)>(?P<after>\W|$)')
assert URL_REGEX.search('<https://x>')
assert not URL_REGEX.search('<https://a.b.c/<>')
assert not URL_REGEX.search('<https://a.b .c/>')
assert URL_REGEX.search('a <https://a.b.c/> b')
assert not URL_REGEX.search('a<https://a.b.c/>b')


def text_and_reference_nodes_from_plaintext(text):
    nodes = []
    while True:
        m = URL_REGEX.search(text)
        if not m:
            break

        token = text[:m.end('before')]
        if token:
            nodes.append(docutils.nodes.Text(token))
        text = text[m.start('after'):]

        url = m.group('url')
        nodes.append(docutils.nodes.reference('', docutils.nodes.Text(url), refuri=url, nolinkurl=True))

    if text:
        nodes.append(docutils.nodes.Text(text))

    return nodes


def paragraph_for_object_definition(name, obj, fq_modname, resolve_function):
    try:
        _, lineno = inspect.getsourcelines(obj)
    except (TypeError, OSError):
        lineno = None
    url = resolve_function(fq_modname, lineno)

    paragraph = docutils.nodes.paragraph()
    reference = docutils.nodes.reference('', '', internal=False, refuri=url)
    reference += docutils.nodes.literal(name, name, classes=['xref', 'py', 'py-class'])
    paragraph += reference

    return paragraph


def bullet_list_with_source_link(object_by_name, fq_modname, resolve_function):
    bullet_list = docutils.nodes.bullet_list()
    for name, obj in object_by_name.items():
        item = docutils.nodes.list_item()
        item += paragraph_for_object_definition(name, obj, fq_modname, resolve_function)
        bullet_list += item
    return bullet_list


def table_row_from_paragraphs(paragraphs):
    row = docutils.nodes.row()
    for p in paragraphs:
        entry = docutils.nodes.entry()
        entry += p
        row += entry
    return row


def table_from_header_texts_and_rows_of_paragraphs(
        header_row_texts: Sequence[str],
        paragraphs_in_rows: Sequence[Sequence[docutils.nodes.paragraph]],
        rel_col_widths: Sequence[int] = ()) -> docutils.nodes.table:

    assert len(header_row_texts) > 1
    assert all(len(r) <= len(header_row_texts) for r in paragraphs_in_rows)

    if not rel_col_widths:
        rel_col_widths = [1]
    rel_col_widths = rel_col_widths[:len(header_row_texts)]
    rel_col_widths.extend(rel_col_widths[-1:] * (len(header_row_texts) - len(rel_col_widths)))

    table = docutils.nodes.table()
    tgroup = docutils.nodes.tgroup(cols=len(header_row_texts))
    table += tgroup
    for rel_col_width in rel_col_widths:
        tgroup += docutils.nodes.colspec(colwidth=rel_col_width)
    thead = docutils.nodes.thead()
    tgroup += thead
    paragraphs = [docutils.nodes.paragraph(text=te) for te in header_row_texts]
    thead += table_row_from_paragraphs(paragraphs)
    tbody = docutils.nodes.tbody()

    tgroup += tbody
    for paragraphs in paragraphs_in_rows:
        tbody += table_row_from_paragraphs(paragraphs)

    return table


ModuleSummary = collections.namedtuple('ModuleSummary', [
    'description', 'definitions', 'usage_examples', 'tool_by_name', 'nontool_by_name'
])


ModuleInfo = collections.namedtuple('ModuleInfo', ['docname', 'id', 'tools', 'executables'])


# https://docutils.sourceforge.io/docs/howto/rst-directives.html
class PySubModule(sphinx.directives.SphinxDirective):
    """
    Directive to mark description of a submodule.

    The generated content is taken from the docstring of the module, __all__, and its first two blocks of
    consecutive lines starting with '#'.
    """

    required_arguments = 1

    option_spec = {
        'platform': lambda x: x,
        'noindex': docutils.parsers.rst.directives.flag,
        'deprecated': docutils.parsers.rst.directives.flag,
    }

    def get_info_from_module(self, fq_modname: str) -> Tuple[str, List[str], collections.OrderedDict]:
        try:
            module = importlib.import_module(fq_modname)
        except ModuleNotFoundError:
            raise self.error(f"module {fq_modname!r} not found") from None

        try:
            docstring = module.__doc__.strip()
        except AttributeError:
            raise self.error(f"module {fq_modname!r} does not contain '__doc__'") from None

        comment_blocks = []

        block_lines = []
        for line in inspect.getsource(module).splitlines():
            if line[:1] == '#':
                block_lines.append(line[1:].rstrip())
            elif block_lines:
                comment_blocks.append('\n'.join(block_lines))
                block_lines = []

        try:
            exported_object_names = tuple(module.__all__)
        except (AttributeError, TypeError):
            raise self.error(f"module {fq_modname!r} does not contain '__all__'") from None

        exported_object_by_name = collections.OrderedDict()
        for name in exported_object_names:
            try:
                exported_object_by_name[name] = getattr(module, name)
            except AttributeError:
                msg = f"module {fq_modname!r} does not contain object listed in  '__all__': {name!r}"
                raise self.error(msg) from None

        return docstring, comment_blocks, exported_object_by_name

    def get_summary_from_module(self, fq_modname: str) -> ModuleSummary:
        docstring, comment_blocks, exported_object_by_name = self.get_info_from_module(fq_modname)

        # normalize docstring
        docstring = '\n'.join(docstring.strip().splitlines())
        docstring = re.sub(r'\n[ \t\r\f\v]*(?=[^\n])', ' ', docstring)  # replace single line separator by ' '
        docstring = re.sub(r'\n\n+', '\n\n', docstring)

        m = DOCSTRING_REGEX.match(docstring)
        if not m:
            raise self.error(f"no proper '__doc__' in module {fq_modname!r}: {docstring!r}")
        description = m.group('summary')

        licenses = set()
        if comment_blocks:
            for line in comment_blocks[0].splitlines():
                m = LICENSE_REGEX.match(line)
                if m:
                    licenses.add(m.group('license'))
        if not licenses:
            raise self.error(f"no SPDX license defined in first comment block in module {fq_modname!r}")
        if len(licenses) > 1:
            lic_str = ', '.join(li for li in sorted(licenses))
            msg = f"different SPDX licenses defined in first comment block in module {fq_modname!r}: {lic_str}"
            raise self.error(msg)

        if len(comment_blocks) < 2:
            raise self.error(f"second comment block missing in module {fq_modname!r}")

        lines = comment_blocks[1].splitlines()

        definitions = collections.OrderedDict()
        for i, line in enumerate(lines):
            m = DEFINITION_REGEX.match(line)
            if m:
                name = m.group('name').strip()
                value = m.group('value').strip()
                definitions[name] = definitions.get(name, ()) + (value,)
            else:
                lines = lines[i:]
                break
        if 'License' in definitions:
            msg = f"second comment block in module {fq_modname!r} defines reserved definition 'License'"
            raise self.error(msg)
        definitions['License'] = tuple(licenses)

        executables = definitions.get('Executable')
        if executables:
            for executable in executables:
                import ast
                try:
                    s = ast.literal_eval(executable)
                    if not isinstance(s, str):
                        raise TypeError
                except (SyntaxError, TypeError, ValueError):
                    msg = (
                        f"definition 'Executable' in second comment block in module {fq_modname!r} "
                        f"is not a Python str: {executable!r}"
                    )
                    raise self.error(msg)

        dedented_usage_examples = []

        indentation = None
        dedented_usage_example = []

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            if line == ' Usage example:':
                if dedented_usage_example:
                    dedented_usage_examples.append('\n'.join(dedented_usage_example))
                    dedented_usage_example = []
                    indentation = None

                i += 1
                while i < len(lines):
                    line = lines[i].rstrip()
                    if line:
                        indentation = line[:len(line) - len(line.lstrip())]
                        break
                    i += 1
            else:
                if indentation is not None:
                    line = line.rstrip()
                    if line:
                        if line[:len(indentation)] != indentation:
                            raise self.error(
                                f"usage example in second comment block in module {fq_modname!r} "
                                f"not properly indented"
                            )
                        line = line[len(indentation):]
                    dedented_usage_example.append(line)
                i += 1

        if dedented_usage_example:
            dedented_usage_examples.append('\n'.join(dedented_usage_example))

        if not dedented_usage_examples:
            raise self.error(f"second comment block in module {fq_modname!r} contains no usage example")

        tool_by_name = collections.OrderedDict()
        nontool_by_name = collections.OrderedDict()
        for name, obj in exported_object_by_name.items():
            if isinstance(obj, type) and issubclass(obj, dlb.ex.Tool):
                tool_by_name[name] = obj
            elif not inspect.ismodule(obj):  # exclude modules since they would mess up the index
                nontool_by_name[name] = obj

        return ModuleSummary(
            description=description, definitions=definitions, usage_examples=dedented_usage_examples,
            tool_by_name=tool_by_name, nontool_by_name=nontool_by_name)

    def add_summary_content(self, fq_modname: str, summary: ModuleSummary) -> docutils.nodes.Element:
        contentnode = sphinx.addnodes.desc_content()
        contentnode.append(docutils.nodes.paragraph(text=summary.description))

        field_list = docutils.nodes.field_list()
        for name, values in summary.definitions.items():
            body = docutils.nodes.paragraph()
            for value in values:
                value_paragraph = docutils.nodes.paragraph()
                if name == 'License':
                    url = f'https://spdx.org/licenses/{value}.html#licenseText'
                    reference = docutils.nodes.reference('', docutils.nodes.Text(value), refuri=url, nolinkurl=True)
                    value_paragraph += reference
                elif name == 'Executable':
                    value_paragraph += docutils.nodes.literal(value, value)
                else:
                    value_paragraph += text_and_reference_nodes_from_plaintext(value)
                body += value_paragraph

            field_name = docutils.nodes.field_name(name, name)
            field_body = docutils.nodes.field_body()
            field_body += body

            fieldnode = docutils.nodes.field()
            fieldnode += [field_name, field_body]
            field_list += fieldnode

        contentnode += field_list

        resolve_function = self.get_resolve_function()
        if summary.tool_by_name:
            contentnode += docutils.nodes.paragraph(text='Provided tools:')
            contentnode += bullet_list_with_source_link(summary.tool_by_name, fq_modname, resolve_function)
        if summary.nontool_by_name:
            title = 'Other objects:' if summary.tool_by_name else 'Provided objects:'
            contentnode += docutils.nodes.paragraph(text=title)
            contentnode += bullet_list_with_source_link(summary.nontool_by_name, fq_modname, resolve_function)

        # like sphinx.directives.code.CodeBlock
        if summary.usage_examples:
            n = len(summary.usage_examples)
            contentnode += docutils.nodes.paragraph(text='Usage example:' if n == 1 else 'Usage examples:')
            for usage_example in summary.usage_examples:
                contentnode += docutils.nodes.literal_block(usage_example, usage_example)
        return contentnode

    def get_resolve_function(self) -> Callable:
        try:
            resolve_function = self.env.config.dlbcontrib_resolve
            if not callable(resolve_function):
                raise AttributeError
        except AttributeError:
            raise self.error("function 'dlbcontrib_resolve' not given in 'conf.py'") from None
        return resolve_function

    def add_signature(self, modname: str, parent_modname: str) -> docutils.nodes.TextElement:
        signode = sphinx.addnodes.desc_signature(modname, '')
        signode['first'] = False

        sig_components = modname.split('.')
        name = sig_components[-1]
        name_prefix = '.'.join(sig_components[:-1])
        fq_modname = (parent_modname and parent_modname + '.' or '') + modname

        sig_prefix = self.objtype + ' '
        signode += sphinx.addnodes.desc_annotation(sig_prefix, sig_prefix)
        if name_prefix:
            name_prefix += '.'
            signode += sphinx.addnodes.desc_addname(name_prefix, name_prefix)
        elif self.env.config.add_module_names:
            nodetext = parent_modname + '.'
            signode += sphinx.addnodes.desc_addname(nodetext, nodetext)
        signode += sphinx.addnodes.desc_name(name, name)

        resolve_function = self.get_resolve_function()
        uri = resolve_function(fq_modname, None)
        if uri:
            # like sphinx.ext.linkcode:
            onlynode = sphinx.addnodes.only(expr='html')
            onlynode += docutils.nodes.reference('', '', internal=False, refuri=uri)
            onlynode[0] += docutils.nodes.inline('', _('[source]'), classes=['viewcode-link'])
            signode += onlynode

        return signode

    def run(self) -> List[docutils.nodes.Node]:
        parent_modname = self.env.ref_context.get('py:module')
        if not parent_modname:
            raise self.error("containing module must be defined before with ':py:module:'")

        classname = self.env.ref_context.get('py:class')
        if classname:
            raise self.error(f'must no be nested inside class (but is in {classname!r})')

        modname = self.arguments[0].strip()
        fq_modname = (parent_modname and parent_modname + '.' or '') + modname

        fq_modname_regex = re.compile(r'^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$')
        if not fq_modname_regex.match(fq_modname):
            raise self.error(f'invalid module name: {fq_modname!r}')

        if ':' in self.name:
            self.domain, self.objtype = self.name.split(':', 1)
        else:
            self.domain, self.objtype = '', self.name
        self.indexnode = sphinx.addnodes.index(entries=[])

        node = sphinx.addnodes.desc()
        node.document = self.state.document
        node['domain'] = self.domain
        # 'desctype' is a backwards compatible attribute
        node['objtype'] = node['desctype'] = self.objtype
        node['noindex'] = 'noindex' in self.options

        # add a signature node for each signature in the current unit
        # and add a reference target for it
        signode = self.add_signature(modname, parent_modname)
        node.append(signode)

        summary = self.get_summary_from_module(fq_modname)
        node.append(self.add_summary_content(fq_modname, summary))
        nodes = [self.indexnode, node]

        if 'noindex' not in self.options:
            synopsis = summary.description.rstrip('.')
            platform = ''  # shown in module index
            module_id = 'module-' + fq_modname

            self.env.domaindata['py']['modules'][fq_modname] = (
                self.env.docname,
                module_id,
                synopsis,
                platform,
                'deprecated' in self.options,
            )

            # make a duplicate entry in 'objects' to facilitate searching for the module in PythonDomain.find_obj()
            self.env.domaindata['py']['objects'][fq_modname] = (self.env.docname, module_id, 'module')

            signode['names'].append(fq_modname)
            signode['ids'].append(module_id)
            signode['first'] = False

            indextext = _('%s (module)') % fq_modname
            self.indexnode['entries'].append(('single', indextext, module_id, '', None))

            resolve_function = self.get_resolve_function()
            tool_reference_paragraphs = [
                paragraph_for_object_definition(name, tool, fq_modname, resolve_function)
                for name, tool in summary.tool_by_name.items()
            ]
            executable_paragraphs = []
            for ex in summary.definitions.get('Executable', []):
                p = docutils.nodes.paragraph()
                p += docutils.nodes.literal(ex, ex)
                executable_paragraphs.append(p)

            moduleinfo_by_modname = \
                self.env.domaindata[DOMAIN_NAME].get('moduleinfo_by_modname', collections.OrderedDict())
            if fq_modname not in moduleinfo_by_modname:
                moduleinfo_by_modname[fq_modname] = ModuleInfo(
                    docname=self.env.docname,
                    id=module_id,
                    tools=tool_reference_paragraphs,
                    executables=executable_paragraphs
                )
            self.env.domaindata[DOMAIN_NAME]['moduleinfo_by_modname'] = moduleinfo_by_modname

            for name, tool in summary.tool_by_name.items():
                # from PyClasslike.get_index_text() andPyObject.add_target_and_index()
                # in sphinx.domains.python
                indextext = _(f'{name} (class in {fq_modname})')
                fullname = (fq_modname and fq_modname + '.' or '') + name
                node_id = sphinx.util.nodes.make_id(self.env, self.state.document, '', fullname)

                # add tool class to index
                self.indexnode['entries'].append(('single', indextext, fullname, '', None))

                # make tool class a cross-reference target (:class:`xxx`)
                objects = self.env.domaindata['py']['objects']
                objects[fullname] = (self.env.docname, node_id, 'class')

                # use this module as link target for tool class
                signode['ids'].append(fullname)

        return nodes


# necessary to detect elements to replace
class moduleindex(docutils.nodes.General, docutils.nodes.Element):
    pass


def purge_dlbcontrib_module_list(app, env, docname):
    moduleinfo_by_modname = env.domaindata[DOMAIN_NAME].get('moduleinfo_by_modname', {})
    env.domaindata[DOMAIN_NAME]['moduleinfo_by_modname'] = \
        collections.OrderedDict((k, v) for k, v in moduleinfo_by_modname.items() if v.docname != docname)


def process_moduleindex_nodes(app, doctree, fromdocname):
    # Replace all *moduleindex* nodes (created empty) with the actual index.

    moduleinfo_by_modname = app.builder.env.domaindata[DOMAIN_NAME].get('moduleinfo_by_modname')
    if not moduleinfo_by_modname:
        return

    for node in doctree.traverse(moduleindex):
        content = []

        paragraphs_in_rows: List[List[docutils.nodes.table]] = []  # all table rows except the header
        for fq_modname, module_info in moduleinfo_by_modname.items():
            tools = docutils.nodes.paragraph()
            if module_info.tools:
                tools += module_info.tools
            executables = docutils.nodes.paragraph()
            if module_info.executables:
                executables += module_info.executables

            # create a table row for module_info
            paragraphs_in_row: List[docutils.nodes.table] = []  # a single table row

            # link to module
            paragraph = docutils.nodes.paragraph()
            literalreference = docutils.nodes.literal(fq_modname, fq_modname, classes=['xref', 'py', 'py-mod'])
            try:
                url = '{}#{}'.format(app.builder.get_relative_uri(fromdocname, module_info.docname), module_info.id)
            except sphinx.environment.NoUri:
                url = None
            if url is None:
                paragraph += literalreference
            else:
                reference = docutils.nodes.reference('', '', internal=False, refuri=url)
                reference += literalreference
                paragraph += reference
            paragraphs_in_row += [paragraph, executables, tools]

            paragraphs_in_rows.append(paragraphs_in_row)

        content.append(table_from_header_texts_and_rows_of_paragraphs(
            header_row_texts=['Module', 'Executables (dynamic helpers)', 'Tool classes'],
            paragraphs_in_rows=paragraphs_in_rows,
            rel_col_widths=[3, 2, 3]
        ))

        node.replace_self(content)


# https://www.sphinx-doc.org/en/master/development/tutorials/todo.html
class PySubModuleIndex(sphinx.directives.SphinxDirective):
    def run(self) -> List[docutils.nodes.Node]:
        return [moduleindex('')]  # will be replaced by process_moduleindex_nodes()


class PySrcDomain(sphinx.domains.Domain):
    name = DOMAIN_NAME
    label = 'Python submodules for documentation style of dlb_contrib package'
    directives = {
        'module': PySubModule,
        'moduleindex': PySubModuleIndex
    }


def setup(app):
    app.add_config_value('dlbcontrib_resolve', None, 'html')
    app.add_domain(PySrcDomain)

    app.add_node(moduleindex)
    app.connect('doctree-resolved', process_moduleindex_nodes)
    app.connect('env-purge-doc', purge_dlbcontrib_module_list)

    return {
        'version': '1.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
