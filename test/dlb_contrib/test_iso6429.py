# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb_contrib.iso6429
import io
import unittest


class ColorTest(unittest.TestCase):

    def test_display_color_is_correct(self):
        self.assertEqual('30', dlb_contrib.iso6429.sgr_display_color(dlb_contrib.iso6429.Color.BLACK))
        self.assertEqual('31', dlb_contrib.iso6429.sgr_display_color(dlb_contrib.iso6429.Color.RED))

    def test_background_color_is_correct(self):
        self.assertEqual('40', dlb_contrib.iso6429.sgr_background_color(dlb_contrib.iso6429.Color.BLACK))
        self.assertEqual('41', dlb_contrib.iso6429.sgr_background_color(dlb_contrib.iso6429.Color.RED))


class SgrControlSequenceTest(unittest.TestCase):

    def test_no_parameter(self):
        self.assertEqual(f'{dlb_contrib.iso6429.CSI}m', dlb_contrib.iso6429.sgr_control_sequence())

    def test_only_display_color(self):
        self.assertEqual(f'{dlb_contrib.iso6429.CSI}31m',
                         dlb_contrib.iso6429.sgr_control_sequence(display_color=dlb_contrib.iso6429.Color.RED))

    def test_only_background_color(self):
        self.assertEqual(f'{dlb_contrib.iso6429.CSI}41m',
                         dlb_contrib.iso6429.sgr_control_sequence(background_color=dlb_contrib.iso6429.Color.RED))

    def test_only_style(self):
        self.assertEqual(f'{dlb_contrib.iso6429.CSI}1m',
                         dlb_contrib.iso6429.sgr_control_sequence(styles=[dlb_contrib.iso6429.Style.BOLD,
                                                                          dlb_contrib.iso6429.Style.BOLD]))

    def test_all(self):
        s = dlb_contrib.iso6429.sgr_control_sequence(
            display_color=dlb_contrib.iso6429.Color.BLUE,
            background_color=dlb_contrib.iso6429.Color.WHITE,
            styles=[dlb_contrib.iso6429.Style.FAINT])
        self.assertEqual(f'{dlb_contrib.iso6429.CSI}34;47;2m', s)


class MessageColorator(unittest.TestCase):

    def test_output_file_is_correct(self):
        output_file = io.StringIO()
        m = dlb_contrib.iso6429.MessageColorator(output_file)
        self.assertIs(m.output_file, output_file)

    def test_empty_is_unchanged(self):
        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        m.write('\n')
        self.assertEqual('\n', m.output_file.getvalue())

    def test_nonmessage_is_unchanged(self):
        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        msg = 'hello there!\n'
        m.write(msg)
        self.assertEqual(msg, m.output_file.getvalue())

        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        msg = 'Z hello there!\n'
        m.write(msg)
        self.assertEqual(msg, m.output_file.getvalue())

    def test_line_without_lineseparator_is_unchanged(self):
        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        m.write('')
        self.assertEqual('', m.output_file.getvalue())

        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        msg = 'I hello there!'
        m.write(msg)
        self.assertEqual(msg, m.output_file.getvalue())

    def test_returns_value_from_output_file(self):
        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        msg = 'hello there!'
        self.assertEqual(len(msg), m.write(msg))

    def test_first_level_indicator_is_used_for_all_lines(self):
        m = dlb_contrib.iso6429.MessageColorator(io.StringIO())
        msg = (
            'W test\n'
            '  I hello \n'
            '    |  there!\n'
        )
        m.write(msg)

        pre = m.SGR_BY_LEVEL_INDICATOR['W']
        post = dlb_contrib.iso6429.sgr_control_sequence()
        formatted_msg = (
            f'{pre}W test{post}\n'
            f'{pre}  I hello{post} \n'  
            f'{pre}    |  there!{post}\n'
        )
        self.assertEqual(formatted_msg, m.output_file.getvalue())
