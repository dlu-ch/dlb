# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Output text to a terminal or terminal emulator that supports a Select Graphic Rendition Control Sequence (SGR)
compliant with ISO/IEC 6429 (ECMA-48, ANSI X3.64).
Of such terminals the DEC VT-100 (although monochrome) is best known."""

# ISO/IEC 6429: <https://www.iso.org/standard/12782.html>
# ECMA-48: <https://www.ecma-international.org/publications-and-standards/standards/ecma-48/>
# DEC VT-100: <https://www.vt100.net/docs/vt100-ug/contents.html>
# ANSI escape code: <https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences>
# Tested with: console of Linux 4.19
# Tested with: tilix 1.8.9
# Tested with: Terminal of PyCharm 2020.1.1 (Community Edition)
#
# Examples of terminals and terminal emulators with a Select Graphic Rendition Control Sequence (SGR)
# compliant with ISO/IEC 6429:
#
#  - DEC VT-100
#  - Linux console <https://man7.org/linux/man-pages/man4/console_codes.4.html>
#  - xterm (emulates DEC VT-100)
#  - Terminal emulators based on the GTK widget VteTerminal <https://developer.gnome.org/vte/>
#    (tilix, GNOME Terminal, ...)
#  - MS DOS with ansi.sys
#  - Windows 10 console (since build 16257) if enabled (e.g. by HKEY_CURRENT_USER\Console\VirtualTerminalLevel = 1):
#     - <https://devblogs.microsoft.com/commandline/updating-the-windows-console-colors/>
#     - <https://devblogs.microsoft.com/commandline/understanding-windows-console-host-settings/>
#
# Usage example:
#
#   import sys
#   import dl.di
#   import dlb_contrib.iso6429
#
#   if sys.stderr.isatty():
#       dlb.di.set_output_file(dlb_contrib.iso6429.MessageColorator(sys.stderr))

__all__ = [
    'MessageColorator',
    'Color', 'Style',
    'CSI',
    'sgr_display_color', 'sgr_background_color', 'sgr_control_sequence'
]

import re
import enum
from typing import Iterable, Optional

CSI = '\x1B['  # Control Sequence Introducer (7 bit mode)


@enum.unique
class Color(enum.Enum):  # see ECMA-48, "8.3.117 SGR - SELECT GRAPHIC RENDITION"
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7


@enum.unique
class Style(enum.Enum):  # see ECMA-48, "8.3.117 SGR - SELECT GRAPHIC RENDITION"
    BOLD = 1
    FAINT = 2


def sgr_display_color(color: Color) -> str:
    return str(color.value + 30)  # see ECMA-48, "8.3.117 SGR - SELECT GRAPHIC RENDITION"


def sgr_background_color(color: Color) -> str:
    return str(color.value + 40)  # see ECMA-48, "8.3.117 SGR - SELECT GRAPHIC RENDITION"


def sgr_control_sequence(display_color: Optional[Color] = None, background_color: Optional[Color] = None,
                         styles: Iterable[Style] = ()) -> str:
    # Return Select Graphic Rendition (SGR) is Control Sequence CSI ... 'm',
    # 'm' beeing the Final Byte.

    parameters = []

    if display_color is not None:
        parameters.append(sgr_display_color(display_color))
    if background_color is not None:
        parameters.append(sgr_background_color(background_color))
    parameters += sorted(set(str(s.value) for s in styles))

    return f"{CSI}{';'.join(parameters)}m"


class MessageColorator:
    # File-like object suitable as output file in dlb.di.set_output_file() that colors diagnostic messages and
    # writes them to a given file-like object.
    #
    # A call of MessageColorator(f).write(message) results in a call of f.write(formatted_message). The latter is
    # expected to finally write *formatted_message* to a terminal (emulator) compliant with ISO/IEC 6429.
    #
    # *formatted_message* is colored line-by-line based on the first level indicator in *message* by inserting
    # ISO/IEC 6429 Control Sequences. If a line in *message* ends with ' ' the corresponding line in *formatted_message*
    # also ends in ' '. The last line remains unchanged if it does not end with a line separator.
    # Each line separator is replaced by '\n'.
    #
    # Overwrite *SGR_BY_LEVEL_INDICATOR* in a subclass to change the colors.

    LEVEL_REGEX = re.compile('^ *([A-Z]) ')

    SGR_BY_LEVEL_INDICATOR = {
        'D': sgr_control_sequence(display_color=Color.GREEN, styles=[Style.FAINT]),
        'I': sgr_control_sequence(display_color=Color.GREEN),
        'W': sgr_control_sequence(display_color=Color.YELLOW),
        'E': sgr_control_sequence(display_color=Color.RED),
        'C': sgr_control_sequence(display_color=Color.RED)
    }

    def __init__(self, output_file):  # output_file must have a file-like write() method
        self._output_file = output_file

    @property
    def output_file(self):
        return self._output_file

    @classmethod
    def format_line(cls, line: str, level_indicator=None):
        sgr = cls.SGR_BY_LEVEL_INDICATOR.get(level_indicator)
        if not sgr:
            return line
        sgr_reset = sgr_control_sequence()
        if line[-1:] != ' ':
            return f'{sgr}{line}{sgr_reset}'
        return f'{sgr}{line[:-1]}{sgr_reset} '

    def write(self, message: str):
        m = self.LEVEL_REGEX.match(message)
        level_indicator = m.group(1) if m else None
        lines = (message + '\n').splitlines()
        formatted_lines = [self.format_line(li, level_indicator) for li in lines[:-1]] + lines[-1:]
        return self._output_file.write('\n'.join(formatted_lines))
