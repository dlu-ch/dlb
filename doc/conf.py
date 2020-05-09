#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Note: When readthedocs.org builds the documentation with the Sphinx, the directory containing
# this file is used as working directory.

import sys
import os.path
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(root_path, 'build'))
sys.path.insert(0, os.path.join(root_path, 'src'))
sys.path.insert(0, os.path.abspath('_ext'))
import version_from_repo

# -- Identification and external locations --------------------------------

project = 'dlb'
copyright = '2020, Daniel Lutz'
author = 'Daniel Lutz'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.

# The full version, including alpha/beta/rc tags.
release, version_info, commit_hash = version_from_repo.get_version()

# The short X.Y version.
version = '.'.join(str(c) for c in version_info)

read_the_doc_base_url = 'https://dlb.readthedocs.io/en/'
github_base_url = 'https://github.com/dlu-ch/dlb/'

github_tree_url = f'{github_base_url}tree/' + (f'v{version}/' if release == version else f'{commit_hash}/')
# GitHub URLs and redirection:
#  - https://github.com/dlu-ch/dlb/blob/<branch-or-tag>/... is redirected to
#    https://github.com/dlu-ch/dlb/tree/<branch-or-tag>/... for directory
#  - https://github.com/dlu-ch/dlb/tree/<branch-or-tag>/... is redirected to
#    https://github.com/dlu-ch/dlb/blob/<branch-or-tag>/... for regular file
#  - https://github.com/dlu-ch/dlb/tree/<branch-or-tag>/ does exist
#  - https://github.com/dlu-ch/dlb/blob/<branch-or-tag>/ does *not* exist

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.intersphinx',  # link to Python 3 documentation
    'sphinx.ext.extlinks',
    'sphinx.ext.mathjax',
    'sphinx.ext.graphviz',
    'sphinx.ext.inheritance_diagram',
    'dlbcontrib'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# Append to every source file
rst_epilog = ''

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The reST default role (used for this markup: `text`) to use for all
# documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'bizstyle'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = 'logo.png'

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
#html_static_path = ['_static']

# Add any extra paths that contain custom files (such as robots.txt or
# .htaccess) here, relative to this directory. These files are copied
# directly to the root of the documentation.
#html_extra_path = []

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Language to be used for generating the HTML full-text search index.
# Sphinx supports the following languages:
#   'da', 'de', 'en', 'es', 'fi', 'fr', 'h', 'it', 'ja'
#   'nl', 'no', 'pt', 'ro', 'r', 'sv', 'tr'
#html_search_language = 'en'

# A dictionary with options for the search language support, empty by default.
# Now only 'ja' uses this config value
#html_search_options = {'type': 'default'}

# The name of a javascript file (relative to the configuration directory) that
# implements a search results scorer. If empty, the default will be used.
#html_search_scorer = 'scorer.js'

# Output file base name for HTML help builder.
htmlhelp_basename = 'dlbdoc'

# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'dlb', 'dlb Documentation', [author], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False

# -- Options for sphinx.ext.intersphinx -----------------------------------

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}

# -- Options for sphinx.ext.extlinks --------------------------------------

extlinks = {
    'dlbrepo': (github_tree_url.replace('%', '%%') + '%s', '')  # usage: :dlbrepo:`example/`
}

# -- Options for sphinx.ext.graphviz --------------------------------------

# https://www.sphinx-doc.org/en/master/usage/extensions/graphviz.html

graphviz_output_format = 'svg'
graphviz_dot_args = [
    '-Nfontname=Helvetica',
    '-Nfontsize=10',
    '-Nshape=box',
    '-Nstyle="setlinewidth(0.5)"'
    '-Earrowhead=empty',
    '-Earrowsize=0.7',
    '-Estyle="setlinewidth(0.5)"'
]

# -- Options for _ext.dlbcontrib ------------------------------------------

def dlbcontrib_resolve(fq_module, lineno=None):
    filename = fq_module.replace('.', '/')

    file_url = f'{github_tree_url}src/{filename}.py'

    if lineno is None:
        url = file_url
    else:
        lineno = int(lineno)
        assert lineno > 0
        url = f'{file_url}#L{lineno}'

    return url


# -- Generation of files to by included -----------------------------------

def generate_dlbexe_help(file_path):
    import dlb.launcher
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(dlb.launcher.get_help())  # note: version not yet replaced (is '?')


generate_dlbexe_help(os.path.join(root_path, 'build', 'out', 'generateddoc', 'dlb-help.txt'))
