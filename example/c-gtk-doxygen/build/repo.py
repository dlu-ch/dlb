# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import re
import dlb.ex
import dlb_contrib.git


# each annotated tag starting with 'v' followed by a decimal digit must match this (after 'v'):
VERSION_REGEX = re.compile(
    r'^'
    r'(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<micro>0|[1-9][0-9]*)'
    r'((?P<post>[abc])(?P<post_number>0|[1-9][0-9]*))?'
    r'$')


class VersionQuery(dlb_contrib.git.GitDescribeWorkingDirectory):
    SHORTENED_COMMIT_HASH_LENGTH = 8  # number of characters of the SHA1 commit hash in the *wd_version*

    # working directory version
    # examples: '1.2.3', '1.2.3c4-dev5+deadbeef@'
    wd_version = dlb.ex.output.Object(explicit=False)

    # tuple of the version according to the version tag
    version_components = dlb.ex.output.Object(explicit=False)

    async def redo(self, result, context):
        await super().redo(result, context)

        shortened_commit_hash_length = min(40, max(1, int(self.SHORTENED_COMMIT_HASH_LENGTH)))

        version = result.tag_name[1:]
        m = VERSION_REGEX.fullmatch(version)
        if not m:
            raise ValueError(f'annotated tag is not a valid version number: {result.tag_name!r}')

        wd_version = version
        if result.commit_number_from_tag_to_latest_commit:
            wd_version += f'-dev{result.commit_number_from_tag_to_latest_commit}' \
                          f'+{result.latest_commit_hash[:shortened_commit_hash_length]}'
        if result.has_changes_in_tracked_files or result.untracked_files:
            wd_version += '@'

        result.wd_version = wd_version
        result.version_components = (
            int(m.group('major')), int(m.group('minor')), int(m.group('micro')),
            m.group('post'), None if m.group('post_number') is None else int(m.group('post_number'))
        )

        return True
