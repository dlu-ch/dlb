Frequently asked questions
==========================

Why another build tool?
-----------------------

A common answer to a common question: Because none of the available tools met the requirements of the author,
especially for the development of embedded software with cross-compiler toolchains and generated code.

See :ref:`similar_tools` for an overview and the following questions for specific reasons.


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

   a. Every output dependency (Make: target) has to be generated
   b. No output dependency has to be generated (Make: no source is newer than its targets)

However, most :term:`runs of dlb <run of dlb>` or Make are something between - that is the whole idea behind a build
tool after all.
Apart from the delay to start Python, the performance of Make and dlb is comparable.
Since a typical dlb script describes the dependencies completely while a typical Makefile does not,
you won't so easily find yourself in the position with dlb where you have to remove all output dependencies and build
from scratch.
Make *requires* that each output dependency (target) changes when one of its input dependencies (sources) has changed.
Fixing a typo in a comment of a :file:`.c` file necessarily leads to the compilation and linking and all dependent
actions, whereas in dlb the cascade stops with the first file that does not change.

Compare :file:`example/c-minimal/` and :file:`example/c-minimal-gnumake/`.


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

   Make implementations like GNU Make allow addition characters and quoting to a certain degree, but treat paths
   differently on different platforms.
