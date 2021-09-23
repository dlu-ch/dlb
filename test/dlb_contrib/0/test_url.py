# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2021 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb_contrib.url
import unittest


class RegexTest(unittest.TestCase):

    def test_usage_example_is_correct(self):
        import re
        import dlb_contrib.url

        url_regex = re.compile(
            '(?i:https)://{host}(:{port}?)?{path}'.format(
                host=dlb_contrib.url.DNS_HOST_DOMAIN_NAME_REGEX.pattern,
                port=dlb_contrib.url.PORT_REGEX.pattern,
                path=dlb_contrib.url.AUTHORITY_NORMALIZED_PATH_REGEX.pattern))

        m = url_regex.fullmatch('https://tools.ietf.org/html/rfc3986')
        self.assertEqual(
            {
                'dns_domain': 'tools.ietf.org',
                'port': None,
                'authority_path': '/html/rfc3986'
            },
            m.groupdict())


class MapByPatternTest(unittest.TestCase):

    def test_fails_for_unbalanced_braces(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('}a{x}b', '{x:utf8}', {'x': r'.*'})
        self.assertEqual("single '}' encountered in pattern: '}a{x}b'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x}b}', '{x:utf8}', {'x': r'.*'})
        self.assertEqual("single '}' encountered in pattern: 'a{x}b}'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('{a{x}', '{x:utf8}', {'x': r'.*'})
        self.assertEqual("single '{' encountered in pattern: '{a{x}'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x}b{', 'https://{x:utf8}', {'x': r'.*'})
        self.assertEqual("single '{' encountered in pattern: 'a{x}b{'", str(cm.exception))

    def test_fails_for_missing_placeholder(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('', 'https://{x:utf8}', {'x': r'.*'})
        self.assertEqual("placeholder missing in pattern: ''", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('{}', 'https://{x:utf8}', {'x': r'.*'})
        self.assertEqual("placeholder missing in pattern: '{}'", str(cm.exception))

    def test_fails_for_invalid_placeholder_in_id(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x:ascii}b', 'https://{x:utf8}', {'x': r'.*'})
        self.assertEqual("encoding not permitted for placeholder in pattern: 'a{x:ascii}b'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x:}b', 'https://{x:utf8}', {'x': r'.*'})
        self.assertEqual("invalid placeholder expression 'x:' in pattern: 'a{x:}b'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{ - }b', 'https://{x:utf8}', {'x': r'.*'})
        self.assertEqual("invalid placeholder expression ' - ' in pattern: 'a{ - }b'", str(cm.exception))

    def test_fails_for_invalid_placeholder_in_url(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x}b', 'https://{x}', {'x': r'.*'})
        self.assertEqual("encoding missing for placeholder 'x' in pattern: 'https://{x}'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x}b', 'https://{x:uiuiui}', {'x': r'.*'})
        self.assertEqual("unknown text encoding 'uiuiui' for placeholder 'x' in pattern: 'https://{x:uiuiui}'",
                         str(cm.exception))

    def test_fails_for_missing_regex(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x}b', 'https://{y:utf8}', {'y': r'.*'})
        self.assertEqual("missing regex for placeholder: 'x'", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('a{x}b', 'https://{y:utf8}', {'x': r'.*'})
        self.assertEqual("missing regex for placeholder: 'y'", str(cm.exception))

    def test_succeeds_for_unused_regex(self):
        dlb_contrib.url.MapByPattern('a{x}b', 'https://{x:utf8}', {'x': r'.*', 'y': r'.*', 'z': r'.*'})

    def test_succeeds_for_duplicate_placeholder(self):
        dlb_contrib.url.MapByPattern('a{x}b{x}y', 'https://{x:utf8}', {'x': r'.*'})

    def test_typical_is_correct(self):
        p = dlb_contrib.url.MapByPattern(
                'lw/1/comp/{x}/{y}', 'https://x.y.z/{y:utf8}/comp/{x:utf8}',
                {'x': r'0|[1-9][0-9]*', 'y': r'0|[1-9][0-9]*'})
        self.assertEqual('https://x.y.z/123/comp/42', p.map('lw/1/comp/42/123'))
        self.assertEqual('lw/1/comp/42/123', p.map('https://x.y.z/123/comp/42', reverse=True))

        self.assertIsNone(p.map('lw/1/comp/42/77/'))
        self.assertIsNone(p.map('https://x.y.z/123/comp/42/', reverse=True))

    def test_return_none_for_none(self):
        p = dlb_contrib.url.MapByPattern(
                'lw/1/comp/{x}/{x}', 'https://x.y.z/{x:utf8}/comp/{x:utf8}',
                {'x': r'0|[1-9][0-9]*'})
        self.assertIsNone(p.map(None))

    def test_multiple_placeholder_is_correct(self):
        p = dlb_contrib.url.MapByPattern(
                'lw/1/comp/{x}/{x}', 'https://x.y.z/{x:utf8}/comp/{x:utf8}',
                {'x': r'0|[1-9][0-9]*'})
        self.assertEqual('https://x.y.z/42/comp/42', p.map('lw/1/comp/42/42'))
        self.assertEqual('lw/1/comp/42/42', p.map('https://x.y.z/42/comp/42', reverse=True))

        self.assertIsNone(p.map('lw/1/comp/42/77'))
        self.assertIsNone(p.map('https://x.y.z/77/comp/42', reverse=True))

    def test_fails_for_different_encodings_for_same_placeholder(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('{x}', '{x:utf-8}/{x:utf-16-be}', {'x': r'.+'})
        self.assertEqual("same placeholder 'x' with different encodings in pattern: '{x:utf-8}/{x:utf-16-be}'",
                         str(cm.exception))

    def test_fails_for_different_placeholders(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.MapByPattern('{x}', '{y:utf-8}', {'x': r'.+', 'y': r'.+'})
        self.assertEqual("placeholders not in both pattern: 'x', 'y'", str(cm.exception))

    def test_encoding_is_correct(self):
        p = dlb_contrib.url.MapByPattern('{x}/{y}', '{x:utf-8}/{y:utf-16-be}', {'x': r'.+', 'y': r'.+'})
        self.assertEqual('a%C3%A4%C3%BC%C3%A4%20schoo/%00a%00%E4%00%FC%00%E4%00%20%00s%00c%00h%00o%00o',
                         p.map('aäüä schoo/aäüä schoo'))
        self.assertEqual('aäüä schoo/aäüä schoo',
                         p.map('a%C3%A4%C3%BC%C3%A4%20schoo/%00a%00%E4%00%FC%00%E4%00%20%00s%00c%00h%00o%00o',
                               reverse=True))

    def test_fails_for_encoding_error(self):
        p = dlb_contrib.url.MapByPattern('{x}', '{x:ascii}', {'x': r'.+'})
        with self.assertRaises(ValueError) as cm:
            p.map('ö')
        self.assertEqual("invalid value of placeholder 'x': 'ö'\n"
                         "  | reason: 'ascii' codec can't encode character '\\xf6' in position 0: "
                         "ordinal not in range(128)",
                         str(cm.exception))

    def test_fails_for_placeholder_that_is_posix_filename(self):
        p = dlb_contrib.url.MapByPattern('{x}', '{x:utf-8}', {'x': r'.*'})

        with self.assertRaises(ValueError) as cm:
            p.map('')
        self.assertEqual("invalid value of placeholder 'x': ''\n"
                         "  | reason: no valid POSIX file name (you may want to fix the regex)",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            p.map('.')
        self.assertEqual("invalid value of placeholder 'x': '.'\n"
                         "  | reason: no valid POSIX file name (you may want to fix the regex)",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            p.map('..')
        self.assertEqual("invalid value of placeholder 'x': '..'\n"
                         "  | reason: no valid POSIX file name (you may want to fix the regex)",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            p.map('a/b')
        self.assertEqual("invalid value of placeholder 'x': 'a/b'\n"
                         "  | reason: no valid POSIX file name (you may want to fix the regex)",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            p.map('a\0b')
        self.assertEqual("invalid value of placeholder 'x': 'a\\x00b'\n"
                         "  | reason: no valid POSIX file name (you may want to fix the regex)",
                         str(cm.exception))

    def test_can_use_flags_in_regex(self):
        p = dlb_contrib.url.MapByPattern('{x}', '{x:utf8}', {'x': r'.+'})
        self.assertIsNone(p.map('a\nb'))  # does not match multiline value

        p = dlb_contrib.url.MapByPattern('{x}', '{x:utf8}', {'x': r'(?s:[^/]+)'})
        self.assertEqual('a%0Ab', p.map('a\nb'))
        self.assertEqual('a\nb', p.map('a%0Ab', reverse=True))

    def test_has_properties_for_patterns(self):
        p = dlb_contrib.url.MapByPattern('a{i}b{{', 'https://example.org/{i:utf8}', {'i': r'[1-9][0-9]*'})
        self.assertEqual('a{i}b{{', p.id_pattern)
        self.assertEqual('https://example.org/{i:utf8}', p.url_pattern)


class IdToUrlMapTest(unittest.TestCase):

    def test_typical_is_correct(self):
        id_to_url_map = dlb_contrib.url.IdToUrlMap(
            {
                # id pattern:         URL pattern
                'ex-1-comp-{compid}': 'https://gitlab.dev.example.org/ex-1-comp-{compid:utf8}.git',
                'gh:{user}:{repo}':   'https://github/{user:utf8}/{repo:utf8}.git'
            }, {
                # placeholder name    regex
                'compid': r'0|[1-9][0-9]*',
                'user': r'[^/:]+',
                'repo': r'[^/:]+'
            }
        )

        self.assertEqual('https://gitlab.dev.example.org/ex-1-comp-42.git', id_to_url_map.map('ex-1-comp-42'))
        self.assertEqual('gh:dlu-ch:dlb', id_to_url_map.map('https://github/dlu-ch/dlb.git', reverse=True))

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('ex-1-comp-042')
        self.assertEqual("no id pattern matches 'ex-1-comp-042'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('https://github/dlu:ch/dlb.git', reverse=True)
        self.assertEqual("no URL pattern matches 'https://github/dlu:ch/dlb.git'", str(cm.exception))

    def test_fails_for_unused_regex(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.url.IdToUrlMap(
                {'{x}': '{x:utf8}', '{y}': '{y:utf8}'},
                {'x': r'.*', 'y': r'.*', 'u': r'.*', 'v': r'.*'})
        self.assertEqual("unused placeholders: 'u', 'v'", str(cm.exception))

    def test_fails_for_nonstring(self):
        id_to_url_map = dlb_contrib.url.IdToUrlMap({'{x}': '{x:utf8}'}, {'x': r'.*'})

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            id_to_url_map.map(None)
        self.assertEqual("'value' must be str", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            id_to_url_map.map(b'')
        self.assertEqual("'value' must be str", str(cm.exception))

    def test_fails_when_id_ambiguous(self):
        id_to_url_map = dlb_contrib.url.IdToUrlMap({'{x}': 'http://{x:utf8}', 'a{x}': 'https://{x:utf8}'}, {'x': r'.*'})

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('aa')
        self.assertEqual("ambiguous id patterns: 'a{x}', '{x}'\n"
                         "  | reason: they all match 'aa'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('https://a', reverse=True)
        self.assertEqual("ambiguous id patterns: 'a{x}', '{x}'\n"
                         "  | reason: they all match 'aa'",
                         str(cm.exception))

    def test_fails_when_url_ambiguous(self):
        id_to_url_map = dlb_contrib.url.IdToUrlMap({'_{x}': 'http://{x:utf8}', '!{x}': 'http://{x:utf8}'}, {'x': r'.+'})

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('http://aa', reverse=True)
        self.assertEqual("ambiguous URL patterns: 'http://{x:utf8}', 'http://{x:utf8}'\n"
                         "  | reason: they all match 'http://aa'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('_a')
        self.assertEqual("ambiguous URL patterns: 'http://{x:utf8}', 'http://{x:utf8}'\n"
                         "  | reason: they all match 'http://a'",
                         str(cm.exception))

    def test_fails_for_invalid_url(self):
        id_to_url_map = dlb_contrib.url.IdToUrlMap({'{x}': '_{x:utf8}'}, {'x': r'.*'})

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('a', reverse=False)
        self.assertEqual("does not start like an URL: '_a'\n  | reason: URL pattern invalid: '_{x:utf8}'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            id_to_url_map.map('_a', reverse=True)
        self.assertEqual("does not start like an URL: '_a'\n  | reason: URL pattern invalid: '_{x:utf8}'",
                         str(cm.exception))


class IdToUrlMapInContectTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_usage_example_correct(self):
        import os
        os.environ['URL_PATTERN_EX_1_COMP'] = 'https://gitlab.dev.example.org/ex-1-comp-{compid:utf8}.git'

        import dlb.ex
        import dlb_contrib.url

        with dlb.ex.Context():
            # Bijectively map all repository URLs to identifier strings at a single place and
            # configurable by environment variables.
            #
            # Idea: When the URLs change (e.g. due to a build in a different environment) only
            # the environment variables have to be adapted, not the dlb script.

            dlb.ex.Context.active.env.import_from_outer(
                'URL_PATTERN_EX_1_COMP',
                pattern='https://.+',
                example='https://gitlab.dev.example.org/ex-1-comp-{compid:utf8}.git')
            dlb.ex.Context.active.env['URL_PATTERN_EX_1_COMP'] = os.environ['URL_PATTERN_EX_1_COMP']

            url_map = dlb_contrib.url.IdToUrlMap({
                # id pattern:         URL pattern
                'ex-1-comp-{compid}': dlb.ex.Context.active.env['URL_PATTERN_EX_1_COMP'],
                'gh:{user}:{repo}':   'https://github/{user:utf8}/{repo:utf8}.git'
            }, {
                # placeholder name:   regex for placeholder's value
                'compid':             r'0|[1-9][0-9]*',
                'user':               r'[^/:]+',
                'repo':               r'[^/:]+'
            })

            # 'git clone' repositories to directories names after their id:
            for repo_id in ['ex-1-comp-42', 'ex-1-comp-747', 'gh:dlu-ch:dlb']:
                # 'git clone' from these URLs to f"build/out/{repo_id}/":
                _ = url_map.get_url_for(repo_id)

            # identify repository from its cloned URLs:
            cloned_url = 'https://gitlab.dev.example.org/ex-1-comp-42.git'   # 'git config --get remote.origin.url'
            _ = url_map.get_id_for(cloned_url)
