# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@userd.noreply.github.com>

"""Abstraction of run-database.
This is an implementation detail - do not import it unless you know what you are doing."""

import marshal  # very fast, reasonably secure, round-trip loss-less (see comment below)
import sqlite3


# Why 'marshal'?
#
# marshal.loads()
#
#   - Documentation states: "Never unmarshal data received from an untrusted or unauthenticated source."
#   - As of today, there is no know ways to exploit 'marshal.loads()'.
#   - `marshal` was designed to be fast and restricted.
#   - Security holes may due to bugs (since the code "has not been carefully analyzed against buffer overflows and
#     so on") but not by design.
#   - https://stackoverflow.com/questions/26931919/marshal-unserialization-not-secure:
#     "I think marshal.loads(s) is just as safe as unicode(s) or file.read()."
#
# json.loads():
#
#   - All value are represented as strings (e.g. binary floating point values)
#   - All dictionary key are interpreted as string
#   - It seems that a json.loads(json.dumps(o)) for int or float results always returns exactly o
#
# pickle.loads():
#
#   - Insecure by design
#   - Slow
#
# Experiments:
#
#   - A round-trip for typical data takes abound 5 to 10 as long with json as with marshal
#   - The serialized data is of about the same length; some data is a bit shorter with marshal, some a bit longer.


class Database:
    def __init__(self, rundb_path: str):
        self._connection = sqlite3.connect(rundb_path, isolation_level='DEFERRED')  # raises sqlite3.Error on error

    def cleanup(self):
        pass

    def close(self):
        # note: uncommitted changes are lost!
        if self._connection is not None:
            self._connection.close()
        self._connection = None
