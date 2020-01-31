Similar Tools
=============

There is a plethora of build tools.

See for example

  - https://en.wikipedia.org/wiki/List_of_build_automation_software
  - https://pypi.org/search/?c=Topic+%3A%3A+Software+Development+%3A%3A+Build+Tools


Tools based on declared dependency rules
----------------------------------------

Most of them implement the functionality of Make in a more readable descriptive language
and improve the modularity and the ability to split large projects into smaller ones.

Examples are:

    - `Make <https://en.wikipedia.org/wiki/Make_%28software%29>`_
    - `Apache Ant <http://ant.apache.org/>`_ (XML, Java-centric)
    - `SCons <https://scons.org/>`_ (Python, based on the Perl-script `Cons <https://www.gnu.org/software/cons/stable/cons.html>`_)
    - https://pypi.org/project/doit/ (Python)
    - https://mesonbuild.com/ (Python)
    - https://pypi.org/project/faff/ (Python, "An input file similar to a Makefile defines rules")
    - https://pypi.org/project/Aap/ (Python)
    - https://pypi.org/project/pyb/ (Python, "Modelled after Ant")
    - https://pypi.org/project/csbuild/ (Python, for fast incremental building of C(++) projects)
    - https://pypi.org/project/mkcode/ (Python)
    - https://pypi.org/project/bold/ (Python, C-centric)
    - https://pypi.org/project/buildit/ (Python, .ini-file syntax to describe rules)
    - `Bruce Eckel's builder.py <https://www.artima.com/weblogs/viewpost.jsp?thread=241209>`_ (Python)

Of these, SCons and doit are closest to the goals of this project.


Tools based on directory structure
----------------------------------

Some build tools are specialized in organizing large projects, fetching files from different
sources, packaging and publish the build products.
They usually do so by imposing a certain directory structure and assign files a give meaning
based on this structure.

Examples are:

    - `Apache Maven <https://maven.apache.org/>`_ (XML, Java-centric)
    - https://www.pantsbuild.org/
    - http://www.buildout.org/


Why explicit is better than implicit
------------------------------------

`Some argue <https://taint.org/2011/02/18/001527a.html>`_, that restricting the expressiveness and power of the
language used to describe a build process is a good thing. I disagree.

A tailored DSL is a good thing exactly as long as you use it as foreseen by its creators.
A two-line example may be impressive as a demonstration, but real-live projects look different.

If a certain task is repetitive enough to be described by static content (e.g. an XML file), there's nothing wrong in
doing so. But this situation does not call for a restriction of the language - it calls for an (optional) easy way
to interpret the static content.

In restricting the language instead, you usually lose first:

 - The possibility to *debug* the build process with powerful tools
 - The possibility to *extend* the build tool by aspects not anticipated by its creators
 - The possibility to *adapt* a certain behaviour of the build tool without replacing large parts of it
