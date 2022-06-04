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

   with dlb.di.Cluster(f"analyze memory usage\n  see {logfile.as_string()!r} for details", is_progress=True):
      ram, rom, emmc = ...

      dlb.di.inform(
          f"""
          in use:
            RAM:\t {ram}\b kB
            ROM (NOR flash):\t {rom}\b kB
            eMMC:\t {emmc}\b kB
          """)

      if rom > 0.8 * rom_max:
          dlb.di.inform("more than 80% of ROM used", level=dlb.di.WARNING)

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
level) and ends with a ``'\n'`` (character U+000A) after a non-space character. It can consist of multiple lines:
an *initial line* followed by any number of *continuation lines* with the same indentation as the initial line.
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

   *file* is used by :mod:`dlb.di` exclusively like this: ``file.write(message)`` where *message* is a (non-empty)
   string can be produced by the production rule :token:`message <diagmessage:message>`
   (so *message* can contain any Unicode character except U+0000 to U+0009 and U+000B to U+001F).
   The first character of *message* is meant to represent the first  character of a line.

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

.. function:: format_message(message, *data, level)

   Return a normalized and formatted message with aligned fields that satisfies the production rule
   :token:`message <diagmessage:message>`, assuming nesting level *level*, defining the initial line and an arbitrary
   number of continuation lines.

   *message* is unindented, its fields (delimited by ``'\t'`` or ``'\b'``) expanded, then normalized.

   All lines of *data* - or `repr(...)` if not of type `str` - are normalized and appended as continuation lines with
   all ASCII control character other than ``'\r'`` and ``'\n'`` replaced by ``'␣'``.

   Unindenting of *message* means:

   - Remove all empty and white space-only lines at the beginning if *message*; then
   - remove the sequence of white space characters leading the first line from the beginning of
     each line that is not empty and not white space-only.

   After unindenting *message*, its first line must not start with ``'␣'``, ``"'"``,  ``"|"``, ``'.'``, ``"]"``,
   or ``"\b"``. It must not end with ``"."``, ``"]"``, or ``"\b"``.
   Each following line that is not non-empty and not white space-only must start with at least 2 space characters
   (will be replace by ``'|␣'``)

   *message* can contain fields.
   Field are by separated ``'\t'`` and ``'\b'`` and the beginning and end of the line.
   Expansion of fields means removing ``'\t'`` and ``'\b'`` and inserting the minimum required number of space
   characters just before or after the fields such that the "positions" are aligned over all lines.

   - A field followed by ``'\t'`` is left aligned (space characters are appended as necessary)
   - A field followed by ``'\t'`` is right aligned (space characters are prepended as necessary).

   Normalization means:

   - Remove all trailing white space from all lines; and
   - replace each run of consecutive empty or white space-only lines by a single empty line; and
   - replace each line separator by ``'\n'``.

   Examples::

      >>> dlb.di.format_message('\njust a moment! ', level=dlb.di.WARNING)
      'W just a moment!'

      >>> dlb.di.format_message(
      ...   """
      ...   summary:
      ...     detail: blah blah blah...
      ...     see also here
      ...   """,
      ...   level=dlb.di.INFO
      ... )
      'I summary: \n  | detail: blah blah blah... \n  | suggestion'

      >>> missing_paths = [dlb.fs.Path('src/'), dlb.fs.Path('build/out/src/generated/')]
      >>> dlb.di.format_message('missing:', *missing_paths, level=dlb.di.ERROR)
      "E missing: \n  | Path('src/') \n  | Path('build/out/src/generated/')"

   :param message: message (to be formatted)
   :type message: str
   :param data: data lines to be appended to formatted message after permissive normalization
   :type data: iterable of str or objects *o* where `repr(o)` is a str
   :param level: (positive) level
   :type level: int
   :return:
      formatted message conforming to production rule :token:`messsage <diagmessage:message>` after appending a
      single ``'\n'``
   :rtype: str

   :raises ValueError:
      if normalized *message* contains only empty lines, or contains an ASCII control character other then white space
      and ``'\b'``, or its first line that is not empty start or ends with a reserved character, or its lines are not
      properly indented
   :raises ValueError: if *level* is invalid

.. function:: inform(message, *data, level: int = INFO, with_time: bool = False)

   If level is not suppressed, output a message to the output file after the title messages of all
   parent :class:`Cluster` instances whose output was suppressed so far.

   *message* is formatted by :func:`format_message` and indented according to the nesting level.
   If *with_time* is ``True``, a :token:`relative_time_suffix <diagmessage:relative_time_suffix>` for the current time
   is included.

   Examples::

      >>> dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')
      I size: 147176 B

      >>> metrics = [
      ...     ('volume', 'V', 1.7, ''),
      ...     ('programming required', 'T', 127.3, ' s'),
      ...     ('difficulty', 'D', 12.8, '')
      ... ]
      >>> dlb.di.inform('\n'.join(
      ...     [f'Halstead complexity measures:'] +
      ...     [f'  {n}:\t {s} =\b {v}\b{u}' for n, s, v, u in metrics]
      ... ))
      I Halstead complexity measures:
        | volume:               V =   1.7
        | programming required: T = 127.3 s
        | difficulty:           D =  12.8

      >>> dlb.di.inform('summary:', 1, 'multi-\nline\x1Ftext', [{2}, False, '?'],
      ...               level=dlb.di.ERROR, with_time=True)
      E summary: [+0.000000s]
        | 1
        | multi-
        | line text
        | [{2}, False, '?']

.. class:: Cluster(message, *, level=INFO, is_progress=False, with_time=False)

   A message cluster with *message* as its title.

   When used as a context manager, this defines a inner message cluster with *message* as its title;
   entering means an increase of the nesting level by 1.

   With *is_progress* set to ``False``, the output when the context is entered is the same as the output of
   :meth:`inform` would be with the same parameters.

   With *is_progress* set to ``True``, a :token:`progress_suffix <diagmessage:progress_suffix>` ``'...'`` is included in
   the message when the context is entered. In addition, a message ``'done.`` or ``'failed with E.'`` is output when the
   context is exited without or with an exception, respectively.
   See :ref:`dlb-di-message-example`.
