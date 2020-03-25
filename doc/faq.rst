Frequently asked questions
==========================

Why another build tool?
-----------------------

A common answer to a common question: Because none of the available tools met the requirements of the author,
especially for the development of embedded software with cross-compiler toolchains and generated code.

   +----------------------------+---------------+---------------+---------------+
   | Desirable property         | dlb           | Make          | SCons         |
   +============================+===============+===============+===============+
   | Speed of full build        | |plusplus|    | |plusplus|    | |plus|        |
   +----------------------------+---------------+---------------+---------------+
   | Speed of partial build,    | |plus|        | |avg|         | |avg|         |
   | avoidance of unnecessary   |               |               |               |
   | actions                    |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Speed of "empty" build     | |avg|         | |plusplus|    | |minusminus|  |
   +----------------------------+---------------+---------------+---------------+
   | Expressiveness             | |plusplus|    | |minusminus|  | |avg|         |
   | of build description       |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Portability                | |plusplus|    | |minusminus|  | |avg|         |
   | of build description       |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Modularity                 | |plusplus|    | |minusminus|  | |minusminus|  |
   +----------------------------+---------------+---------------+---------------+
   | Robustness to              | |plus|        | |minusminus|  | |plusplus|    |
   | system time jumps          |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Robustness to              | |plusplus|    | |minusminus|  | |plusplus|    |
   | changes during build       |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Reproducibility of builds  | |plusplus|    | |minusminus|  | |minusminus|  |
   +----------------------------+---------------+---------------+---------------+
   | Fine-grained control       | |plusplus|    | |minusminus|  | |minusminus|  |
   | of parallel execution      |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Abstraction of tools       | |plusplus|    | |minusminus|  | |minus|       |
   +----------------------------+---------------+---------------+---------------+
   | Self-containedness         | |plusplus|    | |minusminus|  | |plusplus|    |
   +----------------------------+---------------+---------------+---------------+
   | Possibility to step        | |plusplus|    | |minusminus|  | |minus|       |
   | through build with         |               |               |               |
   | debugger                   |               |               |               |
   +----------------------------+---------------+---------------+---------------+
   | Core objects               | contexts,     | strings       | strings,      |
   |                            | tools, paths  |               | string lists  |
   +----------------------------+---------------+---------------+---------------+

.. |plus| replace:: ⊕

.. |plusplus| replace:: ⊕⊕

.. |minus| replace:: ⊖

.. |minusminus| replace:: ⊖⊖

.. |avg| replace:: ⊙

See :ref:`here <similar_tools>` for an overview and the following questions for specific reasons.

Note that there is a lot of controversy in comparing the speed of build tools in general and
`SCons in particular <https://github.com/SCons/scons/wiki/WhySconsIsNotSlow>`_.
In my opinion, raw speed for a single build in an ideal environment is not the most important benchmark for
productivity; the necessary effort to develop and maintain a correct and complete build description is more relevant.
Spending hours to find subtle flaws in the build process and doing complete rebuilds out of mistrust in the completeness
of the dependency information costs more than a few seconds per - otherwise perfect - partial build.


How does dlb compare to Make?
-----------------------------

The concept of Make originates from an era when running an interpreter like Python was too slow to be productive.
Its authors sacrificed readability and correctness to speed.

It is very easy to write extremely fast, incomplete, unreproducible and unportable Makefiles.
It is very hard to write *complete* (all dependencies are covered) and *reproducible* (the output is the same
for the same input) Makefiles.
It is impossible to write *portable* Makefiles. [#makeportability1]_
It is possible but time-consuming to write Makefiles that clearly describe and check their requisites and assumptions.

There is a reason why there are so many flavours of Make and so many utilities that generate Makefiles.

In contrast, it is very easy to write fast, complete, reproducible and portable :term:`dlb scripts <script>`.
dlb does not guess or assume, but requires the explicit statement of information to be used by external tools
(the expected content of environment variables, for example). This results in readable and self-documenting dlb scripts
that concisely describe their requisites and assumptions.

The available Make implementations have been carefully optimized for speed over the years.
dlb is executed by an instance of a Python interpreter; starting a Python interpreter and importing some modules
typically takes approximately 70 ms.
Therefore, dlb cannot compete with the efficiency of Make in the following situations:

   a. Full build: every output dependency (Make: target) has to be generated
   b. "Empty" build: No output dependency has to be generated (Make: no source is newer than its targets)

However, most :term:`runs of dlb <run of dlb>` or Make are something between - that is the whole idea behind a build
tool after all.
Apart from the delay to start Python, the performance of Make and dlb is comparable.
Since a typical dlb script describes the dependencies completely while a typical Makefile does not,
you won't so easily find yourself in the position with dlb where you have to remove all output dependencies and build
from scratch.
Make *requires* that each output dependency (target) changes when one of its input dependencies (sources) has changed.
Fixing a typo in a comment of a :file:`.c` file necessarily leads to the compilation and linking and all dependent
actions, whereas in dlb the cascade stops with the first file that does not change.

Compare `example/c-minimal/ <https://github.com/dlu-ch/dlb/tree/master/example/c-minimal>`_ and
`example/c-minimal-gnumake/ <https://github.com/dlu-ch/dlb/tree/master/example/c-minimal-gnumake>`_.


How does dlb compare to SCons?
------------------------------

SCons shares some goals with dlb.
However, it approaches them differently.

SCons is monolithic, string-oriented and describes dependencies by (implicit) rules; the order of the rules does not
reflect the order of the actions.
dlb is modular, object-oriented and describes dependencies by explicit statements.
SCons contains a lot of predefined roles for typical tasks and environments and does a lot of guessing
(e.g. it tries to detect toolchains). This makes SCons quite slow and intricate to extend in some aspects.

dlb is faster [#speedofscons1]_ and is designed for easy extension.


Why Python?
-----------

Building software with the help of external tools typically requires a lot of  "glue logic" for generating files and
manipulating files and program output. Python and its libraries are very well suited for this task.
The language is clean and expressive and the community takes pride in elegance and simplicity.


Why is explicit better than implicit?
-------------------------------------

`Some argue <https://taint.org/2011/02/18/001527a.html>`_ that restricting the expressiveness and power of the
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


.. [#makeportability1]
   POSIX (ISO 1003.1-2008) `states <https://pubs.opengroup.org/onlinepubs/009695399/utilities/make.html>`_:

      Applications shall select target names from the set of characters consisting solely of periods,
      underscores, digits, and alphabetics from the portable character set [...].
      Implementations may allow other characters in target names as extensions.
      The interpretation of targets containing the characters '%' and '"' is implementation-defined.

   Make implementations like GNU Make allow additional characters and limited quoting, but treat paths
   differently on different platforms.

.. [#speedofscons1]
   This statement is based only on small set of data and the remembered experience with earlier versions of SCons.
   It has to be confirmed.