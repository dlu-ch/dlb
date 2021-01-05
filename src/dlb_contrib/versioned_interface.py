# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Check if the hash in a (line-based) file describing an interface version matches the content hash of the files that
define the interface."""

# Usage example:
#
#   import dlb.fs
#   import dlb.ex
#   import dlb_contrib.versioned_interface
#
#   # content of file 'api-version.h':
#   #     ...
#   #     // last checked for header file hash c58a0b430264752dab68af5efccdd8b4da222995
#   #     // (use <none> for hash to disable check temporarily)
#   #     #define LIBX_API_VERSION 2
#   #     ...
#
#   with dlb.ex.Context():
#       source_directory = dlb.fs.Path('src/')
#
#       # compare hash of header files with hash in 'api-version.h'
#       dlb_contrib.versioned_interface.check_hash(
#           # everything that does not end in '.c':
#           files_to_hash=source_directory.iterdir(name_filter=r'(?!.+\.c$).+',
#                                                  recurse_name_filter=''),
#           hash_line_file=source_directory / 'api-version.h',
#           hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
#           warnonly_hash=b'<none>'
#       )
#
#   # This enforces an update of 'api-version.h' after each change of a .h file
#   # (which potentially requires an increase of LIBX_API_VERSION)

__all__ = ['check_hash']

import re
import hashlib
import warnings
from typing import Iterator, Optional

import dlb.fs


class HashLineFileError(Exception):
    pass


class HashMismatch(Exception):
    pass


def check_hash(*, files_to_hash: Iterator[dlb.fs.PathLike], hash_line_file: dlb.fs.PathLike,
               hash_line_regex: bytes, warnonly_hash: Optional[bytes] = None):
    # Calculate the SHA1 hash of each non-directory object yielded by *files_to_hash* and file *hash_line_file*
    # (expect the hash line). Then compare it to the hash in the hash line.
    #
    # If the hashes do not match and the hash in the hash line is not *hash_to_ignore*, a HashMismatch exception is
    # raised with the correct hash line in the exception message.
    # If the hashes do not match and the hash in the hash line is *hash_to_ignore*, a UserWarning is issued.
    #
    # If *hash_line_file* does not contain exactly one hash line - a line that matches *hash_line_regex* -,
    # a HashLineFileError exception is raised.
    #
    # Use this to avoid accidental changes of a versioned interface without updating the version information.

    hash_line_regex = re.compile(hash_line_regex)

    # calculate SHA1 hash over content of all non-.c file in *files_to_hash* other than *hash_line_file* ...
    content_hash = hashlib.sha1()
    for p in files_to_hash:
        p = dlb.fs.Path(p)
        if not p.is_dir() and p != hash_line_file:
            content_hash.update(p.native.raw.read_bytes())

    # ... and all non-hash lines in *hash_line_file*
    hash_line_file = dlb.fs.Path(hash_line_file)
    hash_line_parts = None
    for line in dlb.fs.Path(hash_line_file).native.raw.read_bytes().splitlines(keepends=True):
        m = hash_line_regex.fullmatch(line.rstrip())
        if m:
            if hash_line_parts is not None:
                raise HashLineFileError(f'{hash_line_file.as_string()!r} contains more than one hash line')
            hash_line_parts = m.string[:m.start(1)], m.group(1), m.string[m.end(1):]
        else:
            content_hash.update(line)
    if hash_line_parts is None:
        raise HashLineFileError(f'{hash_line_file.as_string()!r} contains no hash line')

    # if change: request confirmation of compatibility check by update of hash line
    new_hash_line_parts = hash_line_parts[0], content_hash.hexdigest().encode(), hash_line_parts[2]
    if new_hash_line_parts != hash_line_parts:
        if warnonly_hash is None or hash_line_parts[1] != warnonly_hash:
            hash_line_repr = repr(b''.join(hash_line_parts)).lstrip('b')
            new_hash_line_repr = repr(b''.join(new_hash_line_parts)).lstrip('b')
            msg = (
                f'check and update the version information or the hash line:\n'
                f'  | in {hash_line_file.as_string()!r}\n'
                f'  | replace the line {hash_line_repr}\n'
                f'  | by {new_hash_line_repr}'
            )
            raise HashMismatch(msg)
        warnings.warn('comparison of hash line disabled (do this only temporarily)')
