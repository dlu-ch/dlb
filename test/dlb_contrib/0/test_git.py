# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.git
import dlb_contrib.sh
import os.path
import tempfile
import subprocess
import re
import unittest


class PrepareGitRepo(dlb_contrib.sh.ShScriptlet):
    # About name of default branch created by 'git init':
    # As of Git 2.28, the command line option '--initial-branch' <branch-name> exists and a warning is issued
    # if not given and configuration option 'init.DefaultBranch' not set.
    # Setting this configuration option for Git 2.28 as well as for earlier versions and suppresses the warning.
    SCRIPTLET = """
        git -c init.DefaultBranch=master init
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
    r'(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<micro>0|[1-9]\d*)'
    r'((?P<post>[abc])(?P<post_number>0|[1-9]\d*))?'
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


class CheckRefNameTest(unittest.TestCase):

    def test_empty_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('')
        self.assertEqual(str(cm.exception), 'refname component must not be empty')

    def test_single_slashes_are_valid(self):
        dlb_contrib.git.check_refname('a/b/c')

    def test_consecutive_slashes_are_valid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a//b')
        self.assertEqual(str(cm.exception), 'refname component must not be empty')

    def test_single_dot_in_the_middle_is_valid(self):
        dlb_contrib.git.check_refname('a/b.c')

    def test_at_at_certain_position_is_valid(self):
        dlb_contrib.git.check_refname('a/{@}/b')

    def test_nonascii_is_valid(self):
        dlb_contrib.git.check_refname('äuä')

    def test_leading_dash_is_valid(self):
        dlb_contrib.git.check_refname('-master')

    def test_head_is_valid(self):
        dlb_contrib.git.check_refname('HEAD')

    def test_single_at_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a/@/b')
        self.assertEqual(str(cm.exception), "refname component must not be '@'")

    def test_at_followed_by_brace_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a@{b')
        self.assertEqual(str(cm.exception), "refname component must not contain '@{'")

    def test_double_dot_in_the_middle_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a/b..c')
        self.assertEqual(str(cm.exception), "refname component must not contain '..'")

    def test_control_character_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a\0b')
        self.assertEqual(str(cm.exception), "refname component must not contain ASCII control character")

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a\nb')
        self.assertEqual(str(cm.exception), "refname component must not contain ASCII control character")

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_refname('a\x7Fb')
        self.assertEqual(str(cm.exception), "refname component must not contain ASCII control character")


class CheckBranchNameTest(unittest.TestCase):

    def test_typical_is_valid(self):
        dlb_contrib.git.check_branch_name('master')
        dlb_contrib.git.check_branch_name('wip/develop-old')

    def test_leading_dash_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_branch_name('-master')
        self.assertEqual(str(cm.exception), "must not start with '-'")

    def test_head_is_invalid(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.git.check_branch_name('HEAD')
        self.assertEqual(str(cm.exception), 'reserved')


class DescribeWorkingDirectory(dlb_contrib.git.GitDescribeWorkingDirectory):
    SHORTENED_COMMIT_HASH_LENGTH = 8  # number of characters of the SHA1 commit hash in the *wd_version*

    # working directory version
    # examples: '1.2.3', '1.2.3c4-dev5+deadbeef?'
    wd_version = dlb.ex.output.Object(explicit=False)

    # tuple of the version according to the version tag
    version_components = dlb.ex.output.Object(explicit=False)

    async def redo(self, result, context):
        await super().redo(result, context)

        if len(result.latest_commit_hash) != 40:
            raise ValueError('repository not configured for SHA-1 as its (output) object format')

        shortened_commit_hash_length = min(40, max(1, int(self.SHORTENED_COMMIT_HASH_LENGTH)))

        version = result.tag_name[1:]
        m = VERSION_REGEX.fullmatch(version)
        if not m:
            raise ValueError(f'annotated tag is not a valid version number: {result.tag_name!r}')

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


@unittest.skipUnless(testenv.has_executable_in_path('git'), 'requires git in $PATH')
@unittest.skipUnless(testenv.has_executable_in_path('sh'), 'requires sh in $PATH')
class GitDescribeWorkingDirectoryTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_line_output(self):
        with dlb.ex.Context():
            class AddLightWeightTag(dlb_contrib.sh.ShScriptlet):
                SCRIPTLET = 'git tag v2'  # light-weight tag does not affect 'git describe'

            PrepareGitRepo().start().complete()
            AddLightWeightTag().start().complete()
            result = DescribeWorkingDirectory().start()

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

            CommitGitRepo().start()
            result = DescribeWorkingDirectory().start()

        self.assertEqual({}, result.modification_by_file)
        self.assertEqual({dlb.fs.Path('e/u')}, result.untracked_files)
        self.assertEqual((1, 2, 3, 'c', 4), result.version_components)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev3\+[0-9a-f]{8}$')

        with dlb.ex.Context():
            class CheckoutBranch(dlb_contrib.sh.ShScriptlet):
                SCRIPTLET = 'git checkout -f -b "(detached)"'

            CheckoutBranch().start()
            result = DescribeWorkingDirectory().start()

        self.assertEqual('refs/heads/(detached)', result.branch_refname)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev3\+[0-9a-f]{8}$')

        with dlb.ex.Context():
            class CheckoutDetached(dlb_contrib.sh.ShScriptlet):
                SCRIPTLET = 'git checkout --detach'

            CheckoutDetached().start()
            result = DescribeWorkingDirectory().start()

        self.assertIsNone(result.branch_refname)
        self.assertRegex(result.wd_version, r'1\.2\.3c4-dev3\+[0-9a-f]{8}$')

    def test_sha256_object_format_is_supported(self):
        with dlb.ex.Context():
            git_version = dlb_contrib.generic.VersionQuery(
                VERSION_PARAMETERS_BY_EXECUTABLE={
                    DescribeWorkingDirectory.EXECUTABLE: DescribeWorkingDirectory.VERSION_PARAMETERS
                }
            ).start().version_by_path[dlb.ex.Context.active.helper[DescribeWorkingDirectory.EXECUTABLE]]

            git_version_info = tuple(int(c, 10) for c in git_version.split('.')[:2])
            if git_version_info < (2, 27):
                raise unittest.SkipTest('requires git >= 2.27.0')

        class PrepareRepoWithSha256(dlb_contrib.sh.ShScriptlet):
            SCRIPTLET = """
                git -c init.DefaultBranch=master init --object-format=sha256 
                git config user.email "dlu-ch@users.noreply.github.com"
                git config user.name "dlu-ch"

                echo x > x
                git add x
                git commit -m 'Initial commit'
                git tag -a v0.0.0 -m 'Initial tag'        
                """

        with dlb.ex.Context():
            PrepareRepoWithSha256().start().complete()

            with self.assertRaises(ValueError) as cm:
                DescribeWorkingDirectory().start().complete()
            self.assertEqual('repository not configured for SHA-1 as its (output) object format', str(cm.exception))

            result = dlb_contrib.git.GitDescribeWorkingDirectory().start()

        self.assertEqual(64, len(result.latest_commit_hash))

    def test_gitignore_can_hide_every_modification(self):
        class PrepareRepoWithHiddenModifications(dlb_contrib.sh.ShScriptlet):
            SCRIPTLET = """
                git -c init.DefaultBranch=master init
                git config user.email "dlu-ch@users.noreply.github.com"
                git config user.name "dlu-ch"
                
                echo x > x
                git add x
                git commit -m 'Initial commit'
                git tag -a v0.0.0 -m 'Initial tag'
                
                echo .gitignore > .gitignore
                echo .dlbroot >> .gitignore                
                echo ignored >> .gitignore
                touch ignored                 
                """

        with dlb.ex.Context():
            PrepareRepoWithHiddenModifications().start().complete()
            result = DescribeWorkingDirectory().start()

        self.assertEqual({}, result.modification_by_file)


class DefaultVersionTagTest(unittest.TestCase):
    REGEX = re.compile(dlb_contrib.git.GitCheckTags.ANNOTATED_TAG_NAME_REGEX)

    def test_fails_for_empty(self):
        self.assertFalse(self.REGEX.fullmatch(''))

    def test_fails_for_missing_v(self):
        self.assertFalse(self.REGEX.fullmatch('1.2.3'))

    def test_fails_for_leading_zero(self):
        self.assertFalse(self.REGEX.fullmatch('v01.2.3'))
        self.assertFalse(self.REGEX.fullmatch('v1.02.3'))
        self.assertFalse(self.REGEX.fullmatch('v1.02.03'))

    def test_matches_dotted_integers(self):
        self.assertTrue(self.REGEX.fullmatch('v1'))
        self.assertTrue(self.REGEX.fullmatch('v1.2'))
        self.assertTrue(self.REGEX.fullmatch('v1.2.3'))
        self.assertTrue(self.REGEX.fullmatch('v1.20.345.6789'))
        self.assertTrue(self.REGEX.fullmatch('v0.0.0'))

    def test_fails_without_trailing_decimal_digit(self):
        self.assertFalse(self.REGEX.fullmatch('v1.2.3pre'))

    def test_matches_dotted_integers_with_suffix(self):
        self.assertTrue(self.REGEX.fullmatch('v1.2.3a4'))
        self.assertTrue(self.REGEX.fullmatch('v1.2.3rc0'))
        self.assertTrue(self.REGEX.fullmatch('v1.2.3patch747'))


@unittest.skipUnless(testenv.has_executable_in_path('git'), 'requires git in $PATH')
@unittest.skipUnless(testenv.has_executable_in_path('sh'), 'requires sh in $PATH')
class GitCheckTagsTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_local_only(self):
        class GitCheckTags(dlb_contrib.git.GitCheckTags):
            REMOTE_NAME_TO_SYNC_CHECK = ''

        class GitCheckTags2(GitCheckTags):
            LIGHTWEIGHT_TAG_NAME_REGEX = 'latest_.*'

        with dlb.ex.Context():
            PrepareGitRepo().start().complete()
            subprocess.check_output(['git', 'tag', '-a', 'v2.0.0', '-m', 'Release'])
            subprocess.check_output(['git', 'tag', 'vw'])
            result = GitCheckTags().start()

        self.assertEqual({'v1.2.3c4', 'v2.0.0'}, set(result.commit_by_annotated_tag_name))
        self.assertEqual({'vw'}, set(result.commit_by_lightweight_tag_name))

        with dlb.ex.Context():
            output = subprocess.check_output(['git', 'rev-parse', 'v1.2.3c4^{}', 'v2.0.0^{}', 'vw'])
            commit_hashes = output.decode().splitlines()

            self.assertEqual({
                'v1.2.3c4': commit_hashes[0],
                'v2.0.0': commit_hashes[1]
            }, result.commit_by_annotated_tag_name)

            self.assertEqual({
                'vw': commit_hashes[2]
            }, result.commit_by_lightweight_tag_name)

        with dlb.ex.Context():
            subprocess.check_output(['git', 'tag', 'v2'])
            with self.assertRaises(ValueError) as cm:
                GitCheckTags().start().complete()
            msg = "name of lightweight tag does match 'ANNOTATED_TAG_NAME_REGEX': 'v2'"
            self.assertEqual(msg, str(cm.exception))

        with dlb.ex.Context():
            subprocess.check_output(['git', 'tag', '-d', 'v2'])
            subprocess.check_output(['git', 'tag', '-a', 'v_3.0', '-m', 'Release'])
            with self.assertRaises(ValueError) as cm:
                GitCheckTags().start().complete()
            msg = "name of annotated tag does not match 'ANNOTATED_TAG_NAME_REGEX': 'v_3.0'"
            self.assertEqual(msg, str(cm.exception))

        with dlb.ex.Context():
            subprocess.check_output(['git', 'tag', '-d', 'v_3.0'])
            with self.assertRaises(ValueError) as cm:
                GitCheckTags2().start().complete()
            msg = "name of lightweight tag does not match 'LIGHTWEIGHT_TAG_NAME_REGEX': 'vw'"
            self.assertEqual(msg, str(cm.exception))

    def test_remote_too(self):
        class GitCheckTags(dlb_contrib.git.GitCheckTags):
            pass

        class GitCheckTags2(GitCheckTags):
            DO_SYNC_CHECK_LIGHTWEIGHT_TAGS = True

        origin_repo_dir = os.path.realpath(tempfile.mkdtemp())
        with testenv.DirectoryChanger(origin_repo_dir):
            subprocess.check_output(['git', '-c', 'init.DefaultBranch=master', 'init'])
            subprocess.check_output(['git', 'config', 'user.email', 'dlu-ch@users.noreply.github.com'])
            subprocess.check_output(['git', 'config', 'user.name', 'dlu-ch'])
            subprocess.check_output(['touch', 'x'])
            subprocess.check_output(['git', 'add', 'x'])
            subprocess.check_output(['git', 'commit', '-m', 'Initial commit'])
            subprocess.check_output(['git', 'tag', '-a', 'v1.2.3c4', '-m', 'Release'])
            subprocess.check_output(['touch', 'y'])
            subprocess.check_output(['git', 'add', 'y'])
            subprocess.check_output(['git', 'commit', '-m', 'Add y'])
            subprocess.check_output(['git', 'tag', '-a', 'v2.0.0', '-m', 'Release'])
            subprocess.check_output(['git', 'tag', '-a', 'v2.0.1', '-m', 'Release'])
            subprocess.check_output(['git', 'tag', 'vm'])
            subprocess.check_output(['git', 'tag', 'v'])
            subprocess.check_output(['git', 'tag', 'w'])

        subprocess.check_output(['git', '-c', 'init.DefaultBranch=master', 'init'])
        subprocess.check_output(['git', 'config', 'user.email', 'dlu-ch@users.noreply.github.com'])
        subprocess.check_output(['git', 'config', 'user.name', 'dlu-ch-alias'])
        subprocess.check_output(['touch', 'x'])
        subprocess.check_output(['git', 'add', 'x'])
        subprocess.check_output(['git', 'commit', '-m', 'Initial commit'])
        subprocess.check_output(['git', 'remote', 'add', 'origin', origin_repo_dir])
        subprocess.check_output(['git', 'fetch'])
        subprocess.check_output(['git', 'fetch', '--tags'])

        with dlb.ex.Context():
            GitCheckTags().start()

        with dlb.ex.Context():
            subprocess.check_output(['git', 'tag', '-d', 'vm'])
            subprocess.check_output(['git', 'tag', '-d', 'v'])
            GitCheckTags().start()  # do not sync lightweight tags by default

            with self.assertRaises(ValueError) as cm:
                GitCheckTags2().start().complete()
            msg = "remote tags missing locally: 'v', 'vm'"
            self.assertEqual(msg, str(cm.exception))

            subprocess.check_output(['git', 'tag', '-d', 'v1.2.3c4'])
            subprocess.check_output(['git', 'tag', '-d', 'v2.0.1'])
            with self.assertRaises(ValueError) as cm:
                GitCheckTags().start().complete()
            msg = "remote tags missing locally: 'v1.2.3c4', 'v2.0.1'"
            self.assertEqual(msg, str(cm.exception))

            subprocess.check_output(['git', 'tag', '-a', 'v1.2.3c4', '-m', 'Release'])  # different commit
            subprocess.check_output(['git', 'tag', '-a', 'v2.0.1', '-m', 'Release'])  # different commit
            with self.assertRaises(ValueError) as cm:
                GitCheckTags().start().complete()
            msg = "tags for different commits locally and remotely: 'v1.2.3c4', 'v2.0.1'"
            self.assertEqual(msg, str(cm.exception))

            subprocess.check_output(['git', 'tag', '-a', 'v3.0.0', '-m', 'Release'])
            subprocess.check_output(['git', 'tag', '-a', 'v3.0.1', '-m', 'Release'])
            with self.assertRaises(ValueError) as cm:
                GitCheckTags().start().complete()
            msg = "local tags missing on remotely: 'v3.0.0', 'v3.0.1'"
            self.assertEqual(msg, str(cm.exception))

    def test_example(self):
        origin_repo_dir = os.path.realpath(tempfile.mkdtemp())
        with testenv.DirectoryChanger(origin_repo_dir):
            subprocess.check_output(['git', '-c', 'init.DefaultBranch=master', 'init'])
            subprocess.check_output(['git', 'config', 'user.email', 'dlu-ch@users.noreply.github.com'])
            subprocess.check_output(['git', 'config', 'user.name', 'dlu-ch'])
            subprocess.check_output(['touch', 'x'])
            subprocess.check_output(['git', 'add', 'x'])
            subprocess.check_output(['git', 'commit', '-m', 'Initial commit'])
            subprocess.check_output(['git', 'tag', '-a', 'v1.2.3', '-m', 'Release'])

        subprocess.check_output(['git', '-c', 'init.DefaultBranch=master', 'init'])
        subprocess.check_output(['git', 'remote', 'add', 'origin', origin_repo_dir])
        subprocess.check_output(['git', 'fetch'])
        subprocess.check_output(['git', 'fetch', '--tags'])

        with dlb.ex.Context():
            class GitCheckTags(dlb_contrib.git.GitCheckTags):
                ANNOTATED_TAG_NAME_REGEX = r'v(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}'  # e.g. 'v1.23.0'
            version_tag_names = set(GitCheckTags().start().commit_by_annotated_tag_name)
            self.assertEqual({'v1.2.3'}, version_tag_names)


@unittest.skipUnless(testenv.has_executable_in_path('git'), 'requires git in $PATH')
class VersionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_version_is_string_with_dot(self):
        # noinspection PyPep8Naming
        Tools = [
            dlb_contrib.git.GitDescribeWorkingDirectory,
            dlb_contrib.git.GitCheckTags
        ]

        class QueryVersion(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {
                Tool.EXECUTABLE: Tool.VERSION_PARAMETERS
                for Tool in Tools
            }

        with dlb.ex.Context():
            version_by_path = QueryVersion().start().version_by_path
            self.assertEqual(len(QueryVersion.VERSION_PARAMETERS_BY_EXECUTABLE), len(version_by_path))
            for Tool in Tools:
                path = dlb.ex.Context.active.helper[Tool.EXECUTABLE]
                version = version_by_path[path]
                self.assertIsInstance(version, str)
                self.assertGreaterEqual(version.count('.'), 2)
