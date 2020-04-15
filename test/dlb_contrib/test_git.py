# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.git
import dlb_contrib.sh
import os.path
import re
import unittest


class PrepareGitRepo(dlb_contrib.sh.ShScriptlet):
    SCRIPTLET = """
        git init
        git config user.email "dlu-ch@users.noreply.github.com"
        git config user.name "dlu-ch"
                
        git add .dlbroot/o
        echo .dlbroot/ > .gitignore
        
        echo x > x
        git add x .gitignore
        git commit -m 'Initial commit'
        
        echo x >> x
        git commit -a -m 'Enlarge x'
        git tag -a v1.2.3c4 -m 'Release'
        echo x >> x
        git commit -a -m 'Enlarge x even further'
        
        mkdir d
        echo y > d/y
        git add d/y
        echo z > d/z
        git add d/z
        echo a > 'a -> b'
        git add 'a -> b'
        
        git commit -m 'Add files'
        git mv x 'y -> z'
        git mv 'a -> b' c        
        git mv d e
        git mv e/y why
        echo u > e/u
        """


# each annotated tag starting with 'v' followed by a decimal digit must match this (after 'v'):
VERSION_REGEX = re.compile(
    r'^'
    r'(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<micro>0|[1-9][0-9]*)'
    r'((?P<post>[abc])(?P<post_number>0|[1-9][0-9]*))?'
    r'$')


class ModificationsFromStatusTest(unittest.TestCase):

    def test_branch_header(self):
        lines = [
            '# branch.oid b5fb8c02a485f9f7a5d4aee95848bf9c9d2b0f7f',
            '# branch.head "äüä"',
            '# branch.upstream origin/master',
            '# branch.ab +12 -3'
        ]
        _, _, branch_refname, upstream_branch_refname, before_upstream, behind_upstream = \
            dlb_contrib.git.modifications_from_status(lines)
        self.assertEqual('refs/heads/"äüä"', branch_refname)
        self.assertEqual('refs/remotes/origin/master', upstream_branch_refname)
        self.assertEqual((12, 3), (before_upstream, behind_upstream))

        lines = [
            '# branch.oid b5fb8c02a485f9f7a5d4aee95848bf9c9d2b0f7f',
            '# branch.head (detached)'
        ]
        _, _, branch_refname, upstream_branch_refname, before_upstream, behind_upstream = \
            dlb_contrib.git.modifications_from_status(lines)
        self.assertEqual('refs/heads/(detached)', branch_refname)  # is ambiguous
        self.assertIsNone(upstream_branch_refname)
        self.assertIsNone(before_upstream)
        self.assertIsNone(behind_upstream)

    def test_single_non_header_line(self):
        line = (
            '1 .M N... 100644 100644 100644 '
            'd8755f8b2ede3dc58822895fa85e0e51c8f20dda d8755f8b2ede3dc58822895fa85e0e51c8f20dda jöö/herzig'
        )
        self.assertEqual({dlb.fs.Path('jöö/herzig'): (' M', None)},
                         dlb_contrib.git.modifications_from_status([line])[0])
        line = (
            '1 A. N... 000000 100644 100644 '
            '0000000000000000000000000000000000000000 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 "a\\tb\\nc\\"\'d "'
        )
        self.assertEqual({dlb.fs.Path('a\tb\nc"\'d '): ('A ', None)},
                         dlb_contrib.git.modifications_from_status([line])[0])

        line = (
            '2 R. N... 100644 100644 100644 '
            'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 R100 a\tb'
        )
        self.assertEqual({dlb.fs.Path('b'): ('R ', dlb.fs.Path('a'))},
                         dlb_contrib.git.modifications_from_status([line])[0])
        line = (
            '2 R. N... 100644 100644 100644 '
            'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 R100 "a\\"b"\ta -> b'
        )
        self.assertEqual({dlb.fs.Path('a -> b'): ('R ', dlb.fs.Path('a"b'))},
                         dlb_contrib.git.modifications_from_status([line])[0])
        line = (
            '2 R. N... 100644 100644 100644 '
            'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 R100 '
            'a\t"a\\tb\\nc\\"\'d "'
        )
        self.assertEqual({dlb.fs.Path('a\tb\nc"\'d '): ('R ', dlb.fs.Path('a'))},
                         dlb_contrib.git.modifications_from_status([line])[0])

        self.assertEqual({dlb.fs.Path('a')},
                         dlb_contrib.git.modifications_from_status(['? a'])[1])
        self.assertEqual({dlb.fs.Path('a\tb\nc"\'d ')},
                         dlb_contrib.git.modifications_from_status(['? "a\\tb\\nc\\"\'d "'])[1])

    def test_fails_on_invalid_line(self):
        with self.assertRaises(ValueError):
            dlb_contrib.git.modifications_from_status(['# branch.ab +0'])
        with self.assertRaises(ValueError):
            dlb_contrib.git.modifications_from_status(['1 A.'])
        with self.assertRaises(ValueError):
            dlb_contrib.git.modifications_from_status(['2 R.'])


class DescribeWorkingDirectory(dlb_contrib.git.GitDescribeWorkingDirectory):
    SHORTENED_COMMIT_HASH_LENGTH = 8  # number of characters of the SHA1 commit hash in the *wd_version*

    # working directory version
    # examples: '1.2.3', '1.2.3c4-dev5+deadbeef?'
    wd_version = dlb.ex.Tool.Output.Object(explicit=False)

    # tuple of the version according to the version tag
    version_components = dlb.ex.Tool.Output.Object(explicit=False)

    async def redo(self, result, context):
        await super().redo(result, context)

        shortened_commit_hash_length = min(40, max(1, int(self.SHORTENED_COMMIT_HASH_LENGTH)))

        version = result.tag[1:]
        m = VERSION_REGEX.fullmatch(version)
        if not m:
            raise ValueError(f'annotated tag is not a valid version number: {result.tag!r}')

        wd_version = version
        if result.commit_number_from_tag_to_latest_commit:
            wd_version += f'-dev{result.commit_number_from_tag_to_latest_commit}' \
                          f'+{result.latest_commit_hash[:shortened_commit_hash_length]}'
        if result.has_changes_in_tracked_files:
            wd_version += '?'

        result.wd_version = wd_version
        result.version_components = (
            int(m.group('major')), int(m.group('minor')), int(m.group('micro')),
            m.group('post'), None if m.group('post_number') is None else int(m.group('post_number'))
        )

        return True


@unittest.skipIf(not (os.path.isfile('/bin/sh') and os.path.isfile('/usr/bin/git')), 'requires sh and Git')
class GitTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_line_output(self):
        with dlb.ex.Context():
            PrepareGitRepo().run()
            result = DescribeWorkingDirectory().run()

        dlb.di.inform(f"version: {result.version_components!r}, wd version: {result.wd_version!r}")
        dlb.di.inform(f"changed: {result.modification_by_file.keys()!r}")
        self.assertEqual({
            dlb.fs.Path('a -> b'): ('R ', dlb.fs.Path('c')),
            dlb.fs.Path('d/y'): ('R ', dlb.fs.Path('why')),
            dlb.fs.Path('d/z'): ('R ', dlb.fs.Path('e/z')),
            dlb.fs.Path('x'): ('R ', dlb.fs.Path('y -> z'))
        }, result.modification_by_file)
        self.assertEqual({dlb.fs.Path('e/u')}, result.untracked_files)

        self.assertEqual((1, 2, 3, 'c', 4), result.version_components)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev2\+[0-9a-f]{8}\?$')
        self.assertEqual('refs/heads/master', result.branch_refname)

        with dlb.ex.Context():
            class CommitGitRepo(dlb_contrib.sh.ShScriptlet):
                SCRIPTLET = 'git commit -a -m 0'

            CommitGitRepo().run()
            result = DescribeWorkingDirectory().run()

        self.assertEqual({}, result.modification_by_file)
        self.assertEqual({dlb.fs.Path('e/u')}, result.untracked_files)
        self.assertEqual((1, 2, 3, 'c', 4), result.version_components)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev3\+[0-9a-f]{8}$')

        with dlb.ex.Context():
            class CheckoutBranch(dlb_contrib.sh.ShScriptlet):
                SCRIPTLET = 'git checkout -f -b "(detached)"'

            CheckoutBranch().run()
            result = DescribeWorkingDirectory().run()

        self.assertEqual('refs/heads/(detached)', result.branch_refname)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev3\+[0-9a-f]{8}$')

        with dlb.ex.Context():
            class CheckoutDetached(dlb_contrib.sh.ShScriptlet):
                SCRIPTLET = 'git checkout --detach'

            CheckoutDetached().run()
            result = DescribeWorkingDirectory().run()

        self.assertIsNone(result.branch_refname)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev3\+[0-9a-f]{8}$')
