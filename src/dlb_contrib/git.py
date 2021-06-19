# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Access a working directory managed by Git - the stupid content tracker."""

# Git: <https://git-scm.com/>
# Tested with: git 2.20.1
# Executable: 'git'
#
# Usage example:
#
#   import dlb.di
#   import dlb.ex
#   import dlb_contrib.git
#
#   with dlb.ex.Context():
#       result = dlb_contrib.git.GitDescribeWorkingDirectory().start()
#
#       ... = result.tag_name  # e.g. 'v1.2.3'
#       ... = result.branch_refname  # 'refs/heads/master'
#
#       if result.untracked_files:
#           s = ','.join(repr(p.as_string()) for p in result.untracked_files)
#           dlb.di.inform(f'repository contains {len(result.untracked_files)} '
#                         f'untracked file(s): {s}', level=dlb.di.WARNING)
#
# Usage example:
#
#   # Check the syntax of all tag names and that local annotated tags match with annoated tags in remote 'origin'.
#
#   import dlb.ex
#   import dlb_contrib.git
#
#   with dlb.ex.Context():
#       class GitCheckTags(dlb_contrib.git.GitCheckTags):
#           ANNOTATED_TAG_NAME_REGEX = r'v(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}'  # e.g. 'v1.23.0'
#       version_tag_names = set(GitCheckTags().start().commit_by_annotated_tag_name)

__all__ = [
    'GIT_DESCRIPTION_REGEX',
    'modifications_from_status', 'check_refname',
    'GitDescribeWorkingDirectory', 'GitCheckTags'
]

import sys
import re
from typing import Dict, Iterable, Optional, Set, Tuple

import dlb.fs
import dlb.ex
import dlb_contrib.backslashescape

assert sys.version_info >= (3, 7)


GIT_DESCRIPTION_REGEX = re.compile(
    r'^(?P<tag>.+)-(?P<commit_number>0|[1-9][0-9]*)-g(?P<latest_commit_hash>[0-9a-f]{40})(?P<dirty>\??)$')
assert GIT_DESCRIPTION_REGEX.match('v1.2.3-0-ge08663af738857fcb4448d0fc00b95334bbfd500?')

C_ESCAPED_PATH_REGEX = re.compile(r'^"([^"\\]|\\.)*"$')

STATUS_UPSTREAM_BRANCH_COMPARE_REGEX = re.compile(r'^\+(?P<ahead_count>[0-9]+) -(?P<behind_count>[0-9]+)$')

# <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>
ORDINARY_TRACKED_REGEX = re.compile(
    r'^(?P<change>[A-Z.]{2}) (?P<sub>[A-Z.]{4}) ([0-7]+ ){3}([0-9a-f]+ ){2}(?P<path>.+)$')

# <XY> <sub> <mH> <mI> <mW> <hH> <hI> <X><score> <path><sep><origPath>
MOVED_TRACKED_REGEX = re.compile(
    r'^(?P<change>[A-Z.]{2}) (?P<sub>[A-Z.]{4}) ([0-7]+ ){3}([0-9a-f]+ ){2}[RC][0-9]+ '
    r'(?P<path_before>.+)\t(?P<path>.+)$')


def _without_prefix(s, prefix):
    if s.startswith(prefix):
        return s[len(prefix):]


def _unquote_path(optionally_quoted_path):
    # https://github.com/git/git/blob/v2.20.1/wt-status.c#L250
    # https://github.com/git/git/blob/v2.20.1/quote.c#L333
    # https://github.com/git/git/blob/v2.20.1/quote.c#L258
    # https://github.com/git/git/blob/v2.20.1/quote.c#L184
    # https://github.com/git/git/blob/v2.20.1/config.c#L1115

    # Characters < U+0020: quoted as octal, except these: '\a', '\b', '\t', '\n', '\v', '\f', '\r'.
    # Characters '"' and '\\' are quoted as '\"' and '\\', respectively.
    # Characters >= U+0080: quoted as octal if and only if 'core.quotepath' is true (default).

    m = C_ESCAPED_PATH_REGEX.match(optionally_quoted_path)
    if not m:
        return optionally_quoted_path
    return dlb_contrib.backslashescape.unquote(m.group(0))


def modifications_from_status(lines: Iterable[str]) \
        -> Tuple[Dict[dlb.fs.Path, Tuple[str, Optional[dlb.fs.Path]]], Set[dlb.fs.Path],
                 Optional[str], Optional[str], Optional[int], Optional[int]]:
    # Parse the output lines *lines* of 'git status --porcelain=v2 --untracked-files --branch'

    branch_refname = None
    upstream_branch_refname = None
    before_upstream = None
    behind_upstream = None

    # key is a relative path in the Git index or HEAD affected by a modification,
    # value is a tuple (c, p) where c is two-character string like ' M' and *p* is None or a relative path involved in
    # the modification
    modification_by_file: Dict[dlb.fs.Path, Tuple[str, Optional[dlb.fs.Path]]] = {}
    untracked_files = set()

    for line in lines:
        # https://github.com/git/git/blob/0d0ac3826a3bbb9247e39e12623bbcfdd722f24c/Documentation/git-status.txt#L279
        branch_header = _without_prefix(line, '# branch.')
        if branch_header:
            if _without_prefix(branch_header, 'head '):
                branch_refname = 'refs/heads/' + _without_prefix(branch_header, 'head ')
                # in detached state, *branch_refname' will be 'refs/heads/(detached)';
                # '(detached)' is also a valid branch name -> cannot determine if in detached state
            elif _without_prefix(branch_header, 'upstream '):
                upstream_branch_refname = 'refs/remotes/' + _without_prefix(branch_header, 'upstream ')
            elif _without_prefix(branch_header, 'ab '):
                m = STATUS_UPSTREAM_BRANCH_COMPARE_REGEX.match(_without_prefix(branch_header, 'ab '))
                if not m:
                    raise ValueError(f'invalid branch header line: {line!r}')
                before_upstream = int(m.group('ahead_count'), 10)
                behind_upstream = int(m.group('behind_count'), 10)
            continue

        # https://github.com/git/git/blob/v2.20.1/Documentation/git-status.txt#L301
        # https://github.com/git/git/blob/v2.20.1/wt-status.c#L2074

        ordinary_tracked = _without_prefix(line, '1 ')
        if ordinary_tracked:
            m = ORDINARY_TRACKED_REGEX.match(ordinary_tracked)
            if not m:
                raise ValueError(f'invalid non-header line: {line!r}')
            change = m.group('change').replace('.', ' ')
            path = dlb.fs.Path(_unquote_path(m.group('path')))
            modification_by_file[path] = (change, None)
            continue

        moved_tracked = _without_prefix(line, '2 ')
        if moved_tracked:
            m = MOVED_TRACKED_REGEX.match(moved_tracked)
            if not m:
                raise ValueError(f'invalid non-header line: {line!r}')
            change = m.group('change').replace('.', ' ')
            path = dlb.fs.Path(_unquote_path(m.group('path')))
            modification_by_file[path] = (change, dlb.fs.Path(_unquote_path(m.group('path_before'))))
            continue

        untracked = _without_prefix(line, '? ')
        if untracked:
            untracked_files.add(dlb.fs.Path(_unquote_path(untracked)))
            continue

    return (
        modification_by_file, untracked_files,
        branch_refname, upstream_branch_refname,
        before_upstream, behind_upstream
    )


def check_refname(name: str):
    # Check if *name* is a valid refname according to https://git-scm.com/docs/git-check-ref-format.
    # Raises ValueError if not.

    components = name.split('/')
    if not components:
        raise ValueError('refname must not be empty')
    for c in components:
        if not c:
            raise ValueError('refname component must not be empty')
        if c.startswith('.') or c.endswith('.'):
            raise ValueError("refname component must not start or end with '.'")
        if c.endswith('.lock'):
            raise ValueError("refname component must not end with '.lock'")
        if c == '@':
            raise ValueError("refname component must not be '@'")
        if min(c) < ' ' or '\x7F' in c:
            raise ValueError('refname component must not contain ASCII control character')
        for s in ('..', '/', '\\', ' ', '~', '^', ':', '?', '*', '[', '@{'):
            if s in c:
                raise ValueError('refname component must not contain {}'.format(repr(s)))


class GitDescribeWorkingDirectory(dlb.ex.Tool):
    # Describe the state of the Git working directory at the working tree's root.
    # This includes tag, commit and changed files.
    # Fails if the Git working directory contains not annotated tag match *TAG_PATTERN*.

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'git'

    # Command line parameters for *EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('--version',)

    # Consider only annotated tags with a name that matches this glob(7) pattern.
    TAG_PATTERN = 'v[0-9]*'

    # Number of matching annotated tag reachable from commit *latest_commit_hash* to consider.
    MATCHING_TAG_CANDIDATE_COUNT = 10  # https://github.com/git/git/blob/v2.20.1/builtin/describe.c

    # Most recent annotated tag reachable from commit *latest_commit_hash* and matching *TAG_PATTERN*.
    tag_name = dlb.ex.output.Object(explicit=False)  # e.g. 'v1.2.3'

    # SHA-1 hash of the latest commit as a hex string of 40 characters ('0' - '9', 'a' - 'f').
    latest_commit_hash = dlb.ex.output.Object(explicit=False)  # e.g. '97db12cb0d88c1c157a371f48cf2e0884bf82ade'

    # Number of commits since the tag denoted by *tag_name* as a non-negative integer.
    commit_number_from_tag_to_latest_commit = dlb.ex.output.Object(explicit=False)

    # True if there are files in the Git index with uncommitted changes.
    has_changes_in_tracked_files = dlb.ex.output.Object(explicit=False)

    # Refname of the current branch (refs/heads/...) or None if in detached state.
    branch_refname = dlb.ex.output.Object(explicit=False, required=False)  # e.g. 'refs/heads/master'

    # Refname of the upstream branch (refs/remotes/...), if any.
    upstream_branch_refname = dlb.ex.output.Object(explicit=False, required=False)
    # e.g. 'refs/remotes/origin/master'

    # Dictionary of files that are in the Git index and have uncommited changes.
    # The keys are relative paths in the Git index as dlb.fs.Path objects.
    modification_by_file = dlb.ex.output.Object(explicit=False)

    # Set of relative paths of files not in the Git index and not to be ignored according to '.gitignore' in the
    # Git working directory as dlb.fs.Path objects.
    untracked_files = dlb.ex.output.Object(explicit=False)

    async def redo(self, result, context):
        arguments = [
            'describe',
            '--long', '--abbrev=41', '--dirty=?',
            f'--candidates={self.MATCHING_TAG_CANDIDATE_COUNT}', '--match', self.TAG_PATTERN
        ]
        _, stdout = await context.execute_helper_with_output(self.EXECUTABLE, arguments)
        # Note: untracked files in working directory do not make it dirty in terms of 'git describe'

        m = GIT_DESCRIPTION_REGEX.match(stdout.strip().decode())
        result.tag_name = m.group('tag')
        result.latest_commit_hash = m.group('latest_commit_hash')
        result.commit_number_from_tag_to_latest_commit = int(m.group('commit_number'), 10)

        # Does not include files covered by pattern in a .gitignore file (even if not committed),
        # in $GIT_DIR/info/exclude, or in the file specified by core.excludesFile
        # (if not set: $XDG_CONFIG_HOME/git/ignore or $HOME/.config/git/ignore is used).
        #
        # So, if an untracked .gitignore file is added that contains a rule to ignore itself, all untracked files
        # covered by a rule in this .gitignore file are silently ignored.
        arguments = ['-c', 'core.excludesFile=', 'status', '--porcelain=v2', '--untracked-files', '--branch']
        _, stdout = await context.execute_helper_with_output(self.EXECUTABLE, arguments)

        # https://github.com/git/git/blob/v2.20.1/Documentation/i18n.txt:
        # Path names are encoded in UTF-8 normalization form C
        (
            result.modification_by_file, result.untracked_files,
            potential_branch_refname, result.upstream_branch_refname,
            before_upstream, behind_upstream
        ) = modifications_from_status(line.decode() for line in stdout.strip().splitlines())

        result.has_changes_in_tracked_files = bool(m.group('dirty')) or bool(result.modification_by_file)

        if potential_branch_refname == 'refs/heads/(detached)':  # detached?
            returncode = \
                await context.execute_helper(self.EXECUTABLE, ['symbolic-ref', '-q', 'HEAD'],
                                             stdout_output=False, expected_returncodes=[0, 1])
            if returncode == 1:
                potential_branch_refname = None  # is detached

        result.branch_refname = potential_branch_refname

        return True


class GitCheckTags(dlb.ex.Tool):
    # Query and check tags of the Git working directory at the working tree's root and optionally one of its remotes.
    # Fails if a tag violates the rules expressed by *ANNOTATED_TAG_NAME_REGEX* and *LIGHTWEIGHT_TAG_NAME_REGEX*.

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'git'

    # Command line parameters for *EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('--version',)

    # Regular expression that every annotated tag name must match and no lightweight tag name must match.
    ANNOTATED_TAG_NAME_REGEX = \
        r'v(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*([a-z]+(0|[1-9][0-9]*))?'
    # default: dotted integers without leading zeros and optional letter-only suffix (always ends in decimal digit)
    # e.g. 'v0.2' or 'v1.2.3pre47'

    # Regular expression that every lightweight tag name must match.
    LIGHTWEIGHT_TAG_NAME_REGEX = r'(?!v[0-9]).+'  # exclude names that would match `git describe --match "v[0-9]*"'

    # Optional remote whos tags must match the local tags in name and tagged commit.
    # Must be None (for local tags) or a valid refname that names a remote.
    # If empty, no remote repository is accessed.
    REMOTE_NAME_TO_SYNC_CHECK = 'origin'

    # If False, do not sync lightweight tags with remote *REMOTE_NAME_TO_SYNC_CHECK*.
    # Ignored if *REMOTE_NAME_TO_SYNC_CHECK* is empty.
    DO_SYNC_CHECK_LIGHTWEIGHT_TAGS = False

    # Dictionary of tagged commits.
    # Keys: name of annotated tag.
    # Values: SHA-1 hash of the tagged commit as a hex string of 40 characters ('0' - '9', 'a' - 'f').
    commit_by_annotated_tag_name = dlb.ex.output.Object(explicit=False)  # e.g. {'v1.2.3': 'deadbeef1234...'}

    # Dictionary of tagged commits.
    # Keys: name of lightweight tag.
    # Values: SHA-1 hash of the tagged commit as a hex string of 40 characters ('0' - '9', 'a' - 'f').
    commit_by_lightweight_tag_name = dlb.ex.output.Object(explicit=False)  # e.g. {'vw': '1234adee...'}

    async def get_tagged_commits(self, context, remote_or_url_or_path: str):
        arguments = ['ls-remote', '--tags', '--quiet', remote_or_url_or_path]
        # if *remote_or_url_or_path* is an existing remote and an existing path, the remote takes precedence
        # (which means: always start paths with '.' or '/')

        _, stdout = await context.execute_helper_with_output(self.EXECUTABLE, arguments)

        commit_by_annotated_tag_name = {}
        commit_by_lightweight_tag_name = {}

        line_regex = re.compile(rb'(?P<commit>[a-f0-9]{40})\trefs/tags/(?P<tag>[^ ^]+)(?P<peeled>\^{})?')
        for line in stdout.splitlines():
            m = line_regex.fullmatch(line)
            commit_hash = m.group('commit').decode()
            tag_name = m.group('tag').decode()
            d = commit_by_lightweight_tag_name if m.group('peeled') is None else commit_by_annotated_tag_name
            d[tag_name] = commit_hash

        for tag_name in commit_by_annotated_tag_name:
            del commit_by_lightweight_tag_name[tag_name]

        return commit_by_annotated_tag_name, commit_by_lightweight_tag_name

    async def redo(self, result, context):
        annotated_tag_regex = re.compile(self.ANNOTATED_TAG_NAME_REGEX)
        lightweight_tag_regex = re.compile(self.LIGHTWEIGHT_TAG_NAME_REGEX)
        if self.REMOTE_NAME_TO_SYNC_CHECK:
            check_refname(self.REMOTE_NAME_TO_SYNC_CHECK)

        commit_by_annotated_tag_name, commit_by_lightweight_tag_name = await self.get_tagged_commits(context, '.')
        if self.REMOTE_NAME_TO_SYNC_CHECK:
            remote_commit_by_annotated_tag_name, remote_commit_by_lightweight_tag_name = \
                await self.get_tagged_commits(context, self.REMOTE_NAME_TO_SYNC_CHECK)

            remote_commit_by_tag_name = remote_commit_by_annotated_tag_name
            commit_by_tag_name = commit_by_annotated_tag_name
            if self.DO_SYNC_CHECK_LIGHTWEIGHT_TAGS \
                    and remote_commit_by_lightweight_tag_name != commit_by_lightweight_tag_name:
                remote_commit_by_tag_name.update(remote_commit_by_lightweight_tag_name)
                commit_by_tag_name.update(commit_by_lightweight_tag_name)

            if remote_commit_by_tag_name != commit_by_tag_name:
                local_tags = set(commit_by_tag_name)
                remote_tags = set(remote_commit_by_tag_name)
                tags_only_in_local = local_tags - remote_tags
                tags_only_in_remote = remote_tags - local_tags

                def tag_list_str_for(tags):
                    return ', '.join(repr(t) for t in sorted(tags))

                if tags_only_in_local:
                    raise ValueError('local tags missing on remotely: {}'.format(tag_list_str_for(tags_only_in_local)))
                if tags_only_in_remote:
                    raise ValueError('remote tags missing locally: {}'.format(tag_list_str_for(tags_only_in_remote)))

                tags_with_different_commits = set(
                    n for n, c in commit_by_tag_name.items()
                    if remote_commit_by_tag_name[n] != c
                )
                if tags_with_different_commits:
                    raise ValueError('tags for different commits locally and remotely: {}'.format(
                        tag_list_str_for(tags_with_different_commits)))

        for tag_name in commit_by_annotated_tag_name:
            if not annotated_tag_regex.fullmatch(tag_name):
                raise ValueError(f"name of annotated tag does not match 'ANNOTATED_TAG_NAME_REGEX': {tag_name!r}")

        for tag_name in commit_by_lightweight_tag_name:
            if annotated_tag_regex.fullmatch(tag_name):
                raise ValueError(f"name of lightweight tag does match 'ANNOTATED_TAG_NAME_REGEX': {tag_name!r}")
            if not lightweight_tag_regex.fullmatch(tag_name):
                raise ValueError(f"name of lightweight tag does not match 'LIGHTWEIGHT_TAG_NAME_REGEX': {tag_name!r}")

        result.commit_by_annotated_tag_name = commit_by_annotated_tag_name
        result.commit_by_lightweight_tag_name = commit_by_lightweight_tag_name

        return True
