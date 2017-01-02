Similar Tools
=============

There is a plethora of build tools.

See for example

  - https://en.wikipedia.org/wiki/List_of_build_automation_software
  - https://pypi.python.org/pypi?:action=browse&show=all&c=405&c=408


Tools based on declared dependency rules
----------------------------------------

Most of them implement the functionality of Make in a more readable descriptive language
and improve the modularity and the ability to split large projects into smaller ones.

Examples are:

    - `Make <https://en.wikipedia.org/wiki/Make_%28software%29>`_
    - `Apache Ant <http://ant.apache.org/>`_ (XML, Java-centric)
    - `SCons <http://scons.org/>`_ (Python, based on the Perl-script `Cons <https://www.gnu.org/software/cons/stable/cons.html>`_)
    - https://pypi.python.org/pypi/doit/ (Python)
    - https://pypi.python.org/pypi/faff/ (Python, "An input file similar to a Makefile defines rules")
    - https://pypi.python.org/pypi/Aap/ (Python)
    - https://pypi.python.org/pypi/pyb/ (Python, "Modelled after Ant")
    - https://pypi.python.org/pypi/csbuild/ (Python, for fast incremental building of C(++) projects)
    - https://pypi.python.org/pypi/mkcode/ (Python)
    - https://pypi.python.org/pypi/bold/ (Python, C-centric)
    - https://pypi.python.org/pypi/buildit/ (Python, .ini-file syntax to describe rules)
    - `Bruce Eckel's builder.py <http://www.artima.com/weblogs/viewpost.jsp?thread=241209>`_ (Python)

Of these, SCons and doit are closest to goals of this project.


Tools based on directory structure
----------------------------------

Some build tools are specialized in organizing large projects, fetching files from different
sources, packaging and publish the build products.
They usually do so by imposing a certain directory structure and assign files a give meaning
based on this structure.

Examples are:

    - `Apache Maven <https://maven.apache.org/>`_ (XML, Java-centric)
    - http://www.pantsbuild.org/
    - http://www.buildout.org/
