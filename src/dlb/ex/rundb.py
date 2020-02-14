# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@userd.noreply.github.com>

"""Abstraction of run-database.
This is an implementation detail - do not import it unless you know what you are doing."""

import os.path
import marshal  # very fast, reasonably secure, round-trip loss-less (see comment below)
import sqlite3
import typing
from .. import fs
from . import platform


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


def is_fsobject_dbid(fsobject_dbid: str) -> bool:
    if not isinstance(fsobject_dbid, str):
        return False
    if not fsobject_dbid:
        return True
    return fsobject_dbid[-1] == '/' and not fsobject_dbid.startswith('./')


def build_fsobject_dbid(managed_tree_path: fs.Path) -> str:
    if managed_tree_path.is_absolute():
        raise ValueError
    fsobject_dbid = managed_tree_path.as_string()
    if fsobject_dbid[-1:] != '/':
        fsobject_dbid = fsobject_dbid + '/'  # to enable efficient search for path prefixes in SQL
    if fsobject_dbid[:2] == './':
        fsobject_dbid = fsobject_dbid[2:]
    return fsobject_dbid


class Database:

    def __init__(self, rundb_path: str):
        """
        Open or create the database with path 'rundb_path'.

        Until `close()' is called on this object, no other process must construct an object with the same 'rundb_path'.
        """

        rundb_abs_path = os.path.abspath(rundb_path)
        connection = sqlite3.connect(rundb_abs_path, isolation_level='DEFERRED')  # raises sqlite3.Error on error

        try:
            connection.executescript(  # raises sqlite3.OperationalError if a table already exists
                "CREATE TABLE IF NOT EXISTS ToolInst("
                    "tool_inst_dbid INTEGER NOT NULL, "   # unique id of tool instance across dlb run and platforms
                                                          # (until next cleanup)
        
                    "pl_platform_id BLOB NOT NULL, "      # permanent local platform id
                    "pl_tool_id BLOB NOT NULL, "          # permanent local tool id (unique among all tool with
                                                          # same pl_platform_id)
                    "pl_tool_inst_fp BLOB NOT NULL, "     # permanent local tool instance fingerprint
                                                          # ("almost unique" among all tool instances with
                                                          # same pl_platform_id and pl_tool_id)
        
                    "PRIMARY KEY(tool_inst_dbid)"         # makes 'tool_inst_dbid an AUTOINCREMENT field
                    "UNIQUE(pl_platform_id, pl_tool_id, pl_tool_inst_fp)"
                ");"
                                
                "CREATE TABLE IF NOT EXISTS ToolInstFsInput("
                    "tool_inst_dbid INTEGER, "            # tool instance
                    "fsobject_dbid TEXT NOT NULL, "       # path of filesystem object in managed tree in a special form
                    "is_explicit INTEGER NOT NULL, "      # 0 for implicit, 1 for explicit dependency of tool instance
                    "memo_before BLOB, "                  # memo of filesystem object before last redo of tool instance,
                                                          # NULL if filesystem object was modified since last redo
                    "PRIMARY KEY(tool_inst_dbid, fsobject_dbid), "
                    "FOREIGN KEY(tool_inst_dbid) REFERENCES ToolInst(tool_inst_dbid)"
                ");"
        
                "PRAGMA foreign_keys = ON;"               # https://www.sqlite.org/foreignkeys.html
            )
            connection.commit()
        except:
            connection.rollback()
            raise

        self._connection = connection

    def get_and_register_tool_instance_dbid(self, permanent_local_tool_id: bytes,
                                            permanent_local_tool_instance_fingerprint: bytes) -> int:
        """
        Return a a tool instance dbid `tool_instance_dbid` for a tool instance identified by
        `permanent_local_tool_id` and `permanent_local_tool_instance_fingerprint` on the current platform.

        `tool_instance_dbid` is unique in the run-database until the next cleanup() on this object.

        When called more than one before the next cleanup() on this object, this always returns the same value."""

        cursor = self._connection.cursor()
        t = (platform.PERMANENT_PLATFORM_ID, permanent_local_tool_id, permanent_local_tool_instance_fingerprint)

        # assign tool_inst_dbid by AUTOINCREMENT:
        cursor.execute("INSERT OR IGNORE INTO ToolInst VALUES (NULL, ?, ?, ?)", t)
        cursor.execute("SELECT tool_inst_dbid FROM ToolInst WHERE "
                       "pl_platform_id = ? AND pl_tool_id = ? AND pl_tool_inst_fp = ?", t)

        return cursor.fetchone()[0]

    def get_tool_instance_dbid_count(self) -> int:
        """
        Return the number of (different) registered `tool_instance_dbid` for the current platform.
        """
        return self._connection.execute(
            "SELECT COUNT(*) FROM ToolInst WHERE pl_platform_id = ?",
            (platform.PERMANENT_PLATFORM_ID,)
        ).fetchall()[0][0]

    def update_fsobject_input(self, tool_instance_dbid: int, fsobject_dbid: str, is_explicit: bool,
                              memo_before: typing.Optional[bytes]):
        """
        Add or replace the `memo` of a filesystem object in the managed tree that is an input dependency
        of the tool instance `tool_instance_dbid`.

        `tool_instance_dbid` must be the value returned by call of `get_and_register_tool_instance_dbid()` since
        not before the last `cleanup()` (if any).

        `fsobject_dbid` must be the return value of `build_fsobject_dbid()`.
        """

        if not is_fsobject_dbid(fsobject_dbid):
            raise ValueError(f"not a valid 'fsobject_dbid': {fsobject_dbid!r}")

        self._connection.execute("INSERT OR REPLACE INTO ToolInstFsInput VALUES (?, ?, ?, ?)",
                                 (tool_instance_dbid, fsobject_dbid, 1 if is_explicit else 0, memo_before))

    def get_fsobject_inputs(self, tool_instance_dbid: int, is_explicit_filter: typing.Optional[bool] = None) \
            -> typing.Dict[str, typing.Optional[bytes]]:
        """
        Return the `fsobject_dbid` and the optional memo of all filesystem objects in the managed tree that are
        input dependencies of the tool instance `tool_instance_dbid`.

        If `is_explicit_filter` is not None, only the dependencies with `is_explicit` = `is_explicit_filter` are
        returned.

        `tool_instance_dbid` must be the value returned by call of `get_and_register_tool_instance_dbid()` since
        not before the last `cleanup()` (if any).
        """

        if is_explicit_filter is None:
            rows = self._connection.execute(
                "SELECT fsobject_dbid, is_explicit, memo_before FROM ToolInstFsInput WHERE tool_inst_dbid == ?",
                (tool_instance_dbid,)).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT fsobject_dbid, is_explicit, memo_before FROM ToolInstFsInput "
                "WHERE tool_inst_dbid == ? AND is_explicit == ?",
                (tool_instance_dbid, 1 if is_explicit_filter else 0)).fetchall()

        return {fsobject_dbid: (bool(is_explicit), memo_before) for fsobject_dbid, is_explicit, memo_before in rows}

    def declare_fsobject_input_as_modified(self, modified_fsobject_dbid: str):
        """
        Declare the filesystem objects in the managed tree that are input dependencies (of any tool instance) as
        modified if

          - their `fsobject_dbid` = `modified_fsobject_dbid` or
          - their managed tree path is a prefix of the path of the filesystem object identified
            by `modified_fsobject_dbid`

        Note: Call `commit()` before the filesystem object is actually modified.
        """
        if not is_fsobject_dbid(modified_fsobject_dbid):
            raise ValueError(f"not a valid 'fsobject_dbid': {modified_fsobject_dbid!r}")

        # remove all explicit dependencies (of all tool instances) whose `fsobject_dbid` have
        # `modified_fsobject_dbid` as a prefix
        cursor = self._connection.cursor()
        cursor.execute(
            "DELETE FROM ToolInstFsInput WHERE is_explicit == 1 AND instr(fsobject_dbid,?) == 1",
            (modified_fsobject_dbid,))

        # replace the `memo_before` all non-explicit dependencies (of all tool instances) whose `fsobject_dbid` have
        # `modified_fsobject_dbid` as a prefix by NULL
        # ...
        cursor.execute(
            "UPDATE ToolInstFsInput SET memo_before = NULL WHERE is_explicit == 0 AND instr(fsobject_dbid,?) == 1",
            (modified_fsobject_dbid,))

    def commit(self):
        self._connection.commit()

    def cleanup(self):
        # remove unused tool dbids
        self._connection.execute(
            "DELETE FROM ToolInst WHERE tool_inst_dbid IN ("
                "SELECT ToolInst.tool_inst_dbid FROM ToolInst LEFT OUTER JOIN ToolInstFsInput "
                "ON ToolInst.tool_inst_dbid = ToolInstFsInput.tool_inst_dbid "
                "WHERE ToolInstFsInput.tool_inst_dbid IS NULL"
            ")")

    def close(self):
        # note: uncommitted changes are lost!
        self._connection.close()
        self._connection = None
