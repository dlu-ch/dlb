.. _dlb-di:

:mod:`dlb.di` --- Line-oriented hierarchical diagnostic messages
================================================================

.. module:: dlb.di
   :synopsis: Line-oriented hierarchical diagnostic messages

In contrast to the :mod:`python:logging` module, this module focuses on hierarchical structure and unambiguity.
Absolute time information (date and time of day) is not output in favour of high-resolution relative times.
The output is compact, line-oriented, and well readable for humans.

.. _dlb-di-levels:

Each *message* has an associated *level*, e.g. :attr:`WARNING`, with the same meaning and numerical value as in the
:mod:`python:logging` module. The higher the associated numeric value, the more important the message is considered:

    +-------------------+---------------+
    | Level             | Numeric value |
    +===================+===============+
    | :data:`CRITICAL`  | 50            |
    +-------------------+---------------+
    | :data:`ERROR`     | 40            |
    +-------------------+---------------+
    | :data:`WARNING`   | 30            |
    +-------------------+---------------+
    | :data:`INFO`      | 20            |
    +-------------------+---------------+
    | :data:`DEBUG`     | 10            |
    +-------------------+---------------+

Messages below a global *message threshold* are not output. The message threshold can be changed any time.
It is initialised to :data:`INFO` if :data:`sys.flags.verbose <python:sys.flags>` is ``False`` and 1 otherwise.

Messages can be *nested* with *message clusters*. In the output, the nesting level of a message is expressed by the
indentation of its lines.

A precise syntax in enforced to make the output suitable for incremental parsing (e.g. from a named pipe) with the help
of simple regular expressions. [#machinereadable]_
Any Unicode character except characters from the range U+0000 to U+001F (ASCII control characters) can be used in
messages as long as the syntax is not violated.

To output a message, call :func:`dlb.di.inform()` or enter a context manager instance of :class:`dlb.di.Cluster()`.

All messages are output to the *output file* assigned at the time the output occurs. When first imported,
:mod:`dlb.di` assigns the standard error :data:`sys.stderr`. It can be changed by calling
:func:`dlb.di.set_output_file()` at any time.

.. _dlb-di-message-example:

Example
-------

.. code-block:: python

   import dlb.di
   ...

   with dlb.di.Cluster(f"analyze memory usage\n    see {logfile.as_string()!r} for details", is_progress=True):
      ram, rom, emmc = ...

      dlb.di.inform(
          f"""
          in use:
              RAM:\t {ram}\b kB
              ROM (NOR flash):\t {rom}\b kB
              eMMC:\t {emmc}\b kB
          """)

      if rom > 0.8 * rom_max:
          dlb.di.inform("more than 80% of ROM used", dlb.di.WARNING)

This will generate the following output:

.. code-block:: text

   I analyze memory usage...
     | see 'out/linker.log' for details
     I in use:
       | RAM:              12 kB
       | ROM (NOR flash): 108 kB
       | eMMC:            512 kB
     W more than 80% of ROM used
     I done.


Syntax
------

Each *message* starts with a capital letter after indentation according to its nesting level (2 space characters per
level) and ends with a ``'\n'`` after a non-space character. It can consist of multiple lines: an *initial line*
followed by any number of *continuation lines* with the same indentation as the initial line.
The lines are separated by ``'␣\n'`` (``'␣'`` means the character U+0020):

.. productionlist:: diagmessage
   message: `single_line_message` | `multi_line_message`
   single_line_message: `initial_line` '\n'
   multi_line_message: `initial_line` '␣\n' (`continuation_line` '␣\n')* `continuation_line` '\n'

The initial line carries the essential information. Its first letter after the indentation denotes the *level* of the
message: the first letter of the standard names of the standard loglevels of the :mod:`python:logging` module.

.. productionlist:: diagmessage
   initial_line: `indentation` `level_indicator` '␣' `summary` `summary_suffix`
   indentation: '␣␣'*
   level_indicator: 'C' | 'D' | 'E' | 'I' | 'W'
   summary: `summary_first_character` [ `message_character`* `summary_last_character` ]
   summary_suffix: [ `progress_suffix` ] [ '␣' `relative_time_suffix` ]
   progress_suffix: '.' | '...'

The timing information is optional and can be enabled per message. It contains the time elapsed in seconds since the
first time a message with enabled timing information was output. Later outputs of timing information never show earlier
times. The number of decimal places is the same for all output timing information on a given platform and is at most 6.

.. productionlist:: diagmessage
   relative_time_suffix: '[+' `time_since_first_time_use` ']'
   time_since_first_time_use: `decimal_integer` [ '.' `decimal_digit` `decimal_digit`* ] 's'

.. productionlist:: diagmessage
   continuation_line: `indentation` `continuation_line_indicator` `message_character`*
   continuation_line_indicator: '␣␣|␣'

.. productionlist:: diagmessage
   summary_first_character: any `summary_last_character` except "'" (U+0027) and '|' (U+007C)
   summary_last_character: any `message_character` except '␣' (U+0020), '.' (U+002E) and ']' (U+005D)
   message_character: any Unicode character except from the range U+0000 to U+001F
   decimal_integer: `nonzero_decimal_digit` `decimal_digit`*
   nonzero_decimal_digit: '1' | ... | '9'
   decimal_digit: '0' | `nonzero_decimal_digit`


Module content
--------------

.. data:: DEBUG
.. data:: INFO
.. data:: WARNING
.. data:: ERROR
.. data:: CRITICAL

   Positive integer representing a :ref:`message level <dlb-di-levels>` of the same name.

   In contrast to :mod:`logging`, these attributes are *not* meant to be changed by the user.
   Use them to define your own positive integers representing levels like this::

      ... = dlb.di.INFO + 4  # a level more important than INFO but not yet a WARNING

.. function:: set_output_file(file)

   Set the output file for all future outputs of this module to *file* and return the previous output file.

   *file* is used by :mod:`dlb.di` exclusively like this: ``file.write(message)``. *message* is a (non-empty) string
   that can be produced by the production rule :token:`message`. Its first character is meant to represent the first
   character of a line.

   :param file: new output file
   :type file: an object with a ``write(string)`` method
   :return: the previous value, an object with a ``write`` attribute
   :raises TypeError: if *file* has no ``write`` attribute

.. function:: set_threshold_level(level)

   Set the level threshold for all future messages to *level*.

   Every message with a level below *level* will be suppressed.

   :param level: new (positive) level threshold
   :type level: int
   :raises TypeError: if *level* cannot be converted to an ``int``
   :raises ValueError: if *level* is not positive

.. function:: is_unsuppressed_level(level)

   Is a message of level *level* unsuppressed be the current level threshold?

   :param level: (positive) level
   :type level: int
   :rtype: bool

.. function:: get_level_indicator(level)

   Return a unique capital ASCII letter, representing the lowest standard level not lower than *level*.

   Example::

      >>> dlb.di.get_level_indicator(dlb.di.ERROR + 1)
      'E'

   :param level: level not lower that :attr:`DEBUG`
   :type level: int

.. function:: format_time_ns(time_ns)

   Return a string representation for a time in seconds, rounded towards 0 approximately to the resolution of
   :func:`python:time.monotonic_ns()`.

   The number of decimal places is fixed for all calls. It is a platform-dependent value in the range of 1 to 6.

   :param time_ns: time in nanoseconds
   :type time_ns: int
   :rtype: str

.. function:: format_message(message, level)

   Return a formatted message with aligned fields, assuming nesting level *level*.

   First, empty lines are removed from the beginning and the end of *message* and trailing white space characters is
   removed from each line.
   After that, the first line must not start with ``'␣'``, ``"'"``,  ``"|"``, ``'.'`` or ``"]"``.
   If must not end with ``"."`` or ``"]"``.
   Each non-empty line after the first line must start with at least 4 space characters after than the indentation of
   the first line. Example: If the first line is indented by 8 space characters, each following non-empty line must
   start with at least 12 space characters.

   *message* can contain fields. A field is declared by appending ``'\t'`` or ``'\b'``.
   A field whose declaration ends with ``'\t'`` is left aligned, one whose declaration ends with ``'\t'`` is right
   aligned over all lines of the message. In the return value the ``'\t'`` or ``'\b'`` are not present but their
   "positions" are aligned over all lines of the message.

   Examples::

      >>> dlb.di.format_message('\njust a moment! ', dlb.di.WARNING)
      'W just a moment!'

      >>> dlb.di.format_message(
      ...   """
      ...   summary:
      ...       detail: blah blah blah...
      ...       see also here
      ...   """, dlb.di.INFO)
      'I summary: \n  | detail: blah blah blah... \n  | suggestion'

      >>> m = ''.join(f"\n    {n}:\t {s} =\b {v}\b{u}" for n, s, v, u in metrics)
      >>> print(dlb.di.format_message('Halstead complexity measures:' + m, dlb.di.INFO))
      I Halstead complexity measures:
        | volume:               V =   1.7
        | programming required: T = 127.3 s
        | difficulty:           D =  12.8

   :param message: message (to be formatted)
   :type message: str
   :param level: (positive) level
   :type level: int
   :return: formatted message conforming to :token:`message` after appending a single ``'\n'``
   :rtype: str
   :raises ValueError: if *message* would violate :token:`message` or if *level* is invalid

.. function:: inform(message, *, level: int = INFO, with_time: bool = False)

   If level is not suppressed, output a message to the output file after the title messages of all
   parent :class:`Cluster` instances whose output was suppressed so far.

   *message* is formatted by :func:`format_message` and indented according the nesting level.
   If *with_time* is ``True``, a :token:`relative_time_suffix` for the current time is included.

.. class:: Cluster(message, *, level=INFO, is_progress=False, with_time=False)

   A message cluster with *message* as its title.

   When used as a context manager, this defines a inner message cluster with *message* as its title;
   entering means an increase of the nesting level by 1.

   With *is_progress* set to ``False``, the output when the context is entered is the same as the output of
   :meth:`inform` would be with the same parameters.

   With *is_progress* set to ``True``, a :token:`progress_suffix` ``'...'`` is included in the message when the context
   is entered. In addition, a message ``'done.`` or ``'failed with E.'`` is output when the context is exited without or
   with an exception, respectively.
   See :ref:`dlb-di-message-example`.
