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
from . import util
from . import platform


# Why 'marshal'?
#
# marshal.loads()
#
#   - Documentation states: "Never unmarshal data received from an untrusted or unauthenticated source."
#   - As of today, there is no know ways to exploit 'marshal.loads()'.
#   - 'marshal' was designed to be fast and restricted.
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


class DatabaseError(Exception):
    pass


class _CursorWithExceptionMapping:
    def __init__(self, connection: sqlite3.Connection, summary_message_line: str, solution_message_line: str):
        self._connection = connection
        self._summary_message_line = summary_message_line.strip()
        self._solution_message_line = solution_message_line.strip()

    def __enter__(self):
        return self._connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and isinstance(exc_val, sqlite3.Error):
            lines = []

            if self._summary_message_line:
                lines.append(f"reason: {self._summary_message_line}")
            lines.append(util.exception_to_line(exc_val, True))
            if self._solution_message_line:
                lines.append(self._solution_message_line)

            raise DatabaseError('\n  | '.join(lines)) from None


class Database:

    def __init__(self, rundb_path: str, suggestion_if_database_error: str = ''):
        """
        Open or create the database with path *rundb_path*.

        *suggestion_if_database_error* should be a non-empty line suggesting a recovery solution for database errors.

        Until :meth:`close()' is called on this object, no other process must construct an object with the same
        *rundb_path*.
        """

        self._suggestion_if_database_error = str(suggestion_if_database_error)

        rundb_abs_path = os.path.abspath(rundb_path)
        try:
            connection = sqlite3.connect(rundb_abs_path, isolation_level='DEFERRED')  # raises sqlite3.Error on error
        except sqlite3.Error as e:
            exists = False
            try:
                exists = os.path.isfile(rundb_abs_path)
            except OSError:
                pass

            state_msg = 'existing' if exists else 'non-existing'
            reason = util.exception_to_line(e, True)
            msg = (
                f"could not open {state_msg} run-database: {rundb_abs_path!r}\n"
                f"  | reason: {reason}\n"
                f"  | check access permissions"
            )
            raise DatabaseError(msg) from None

        cursor_with_exception_mapping = _CursorWithExceptionMapping(
            connection,
            'could not setup run-database',
            self._suggestion_if_database_error
        )
        with cursor_with_exception_mapping as cursor:
            cursor.executescript(  # includes a "BEGIN" according to the 'isolation_level'
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

        self._connection = connection

    def get_and_register_tool_instance_dbid(self, permanent_local_tool_id: bytes,
                                            permanent_local_tool_instance_fingerprint: bytes) -> int:
        """
        Return a tool instance dbid *tool_instance_dbid* for a tool instance identified by
        *permanent_local_tool_id* and *permanent_local_tool_instance_fingerprint* on the current platform.

        *tool_instance_dbid* is unique in the run-database until the next :meth:`cleanup()` on this object.

        When called more than one before the next cleanup() on this object, this always returns the same value."""

        t = (platform.PERMANENT_PLATFORM_ID, permanent_local_tool_id, permanent_local_tool_instance_fingerprint)
        with self._cursor_with_exception_mapping() as cursor:
            # assign tool_inst_dbid by AUTOINCREMENT:
            cursor.execute("INSERT OR IGNORE INTO ToolInst VALUES (NULL, ?, ?, ?)", t)
            cursor.execute("SELECT tool_inst_dbid FROM ToolInst WHERE "
                           "pl_platform_id = ? AND pl_tool_id = ? AND pl_tool_inst_fp = ?", t)
            tool_instance_dbid = cursor.fetchone()[0]

        return tool_instance_dbid

    def get_tool_instance_dbid_count(self) -> int:
        """
        Return the number of (different) registered *tool_instance_dbid* for the current platform.
        """

        with self._cursor_with_exception_mapping() as cursor:
            n = cursor.execute(
                "SELECT COUNT(*) FROM ToolInst WHERE pl_platform_id = ?",
                (platform.PERMANENT_PLATFORM_ID,)
            ).fetchall()[0][0]

        return n

    def update_fsobject_input(self, tool_instance_dbid: int, fsobject_dbid: str, is_explicit: bool,
                              memo_before: typing.Optional[bytes]):
        """
        Add or replace the description of a filesystem object in the managed tree that is an input dependency
        of the tool instance *tool_instance_dbid* by ``(is_explicit, memo_before``).

        *tool_instance_dbid* must be the value returned by call of :meth:`get_and_register_tool_instance_dbid()` since
        not before the last :meth:`cleanup()` (if any).

        *fsobject_dbid* must be the return value of :func:`build_fsobject_dbid()`.
        """

        if not is_fsobject_dbid(fsobject_dbid):
            raise ValueError(f"not a valid 'fsobject_dbid': {fsobject_dbid!r}")

        if memo_before is not None and not isinstance(memo_before, bytes):
            raise ValueError(f"not a valid 'memo_before': {memo_before!r}")

        with self._cursor_with_exception_mapping() as cursor:
            cursor.execute("INSERT OR REPLACE INTO ToolInstFsInput VALUES (?, ?, ?, ?)",
                           (tool_instance_dbid, fsobject_dbid, 1 if is_explicit else 0, memo_before))

    def replace_fsobject_inputs(self, tool_instance_dbid: int,
                                info_by_by_fsobject_dbid: typing.Dict[str, typing.Tuple[bool, bytes]]):
        """
        Replace all information on input dependencies for a tool instance *tool_instance_dbid* by
        *info_by_by_fsobject_dbid*.

        Includes a :meth:`commit()` at the start.
        In case of an exception, the information on input dependencies in the run-database remains unchanged.
        """
        with self._cursor_with_exception_mapping() as cursor:
            try:
                self._connection.commit()
                cursor.execute("BEGIN")
                cursor.execute("DELETE FROM ToolInstFsInput WHERE tool_inst_dbid == ?", (tool_instance_dbid,))
                for fsobject_dbid, info in info_by_by_fsobject_dbid.items():
                    is_explicit, memo_before = info
                    self.update_fsobject_input(tool_instance_dbid, fsobject_dbid, is_explicit, memo_before)
            except:
                self._connection.rollback()
                raise

    def get_fsobject_inputs(self, tool_instance_dbid: int, is_explicit_filter: typing.Optional[bool] = None) \
            -> typing.Dict[str, typing.Tuple[bool, bytes]]:
        """
        Return the *fsobject_dbid* and the optional memo of all filesystem objects in the managed tree that are
        input dependencies of the tool instance *tool_instance_dbid*.

        If *is_explicit_filter* is not ``None``, only the dependencies with *is_explicit* = *is_explicit_filter* are
        returned.

        *tool_instance_dbid* must be the value returned by call of :meth:`get_and_register_tool_instance_dbid()` since
        the last :meth:`cleanup()` (if any).
        """

        with self._cursor_with_exception_mapping() as cursor:

            if is_explicit_filter is None:
                rows = cursor.execute(
                    "SELECT fsobject_dbid, is_explicit, memo_before FROM ToolInstFsInput WHERE tool_inst_dbid == ?",
                    (tool_instance_dbid,)).fetchall()
            else:
                rows = cursor.execute(
                    "SELECT fsobject_dbid, is_explicit, memo_before FROM ToolInstFsInput "
                    "WHERE tool_inst_dbid == ? AND is_explicit == ?",
                    (tool_instance_dbid, 1 if is_explicit_filter else 0)).fetchall()

        return {fsobject_dbid: (bool(is_explicit), memo_before) for fsobject_dbid, is_explicit, memo_before in rows}

    def declare_fsobject_input_as_modified(self, modified_fsobject_dbid: str):
        """
        Declare the filesystem objects in the managed tree that are input dependencies (of any tool instance) as
        modified if

          - their *fsobject_dbid* = *modified_fsobject_dbid* or
          - their managed tree path is a prefix of the path of the filesystem object identified
            by *modified_fsobject_dbid*

        Includes a :meth:`commit()` at the start.
        In case of an exception, the information on input dependencies in the run-database remains unchanged.

        Note: call :meth:`commit()` before the filesystem object is actually modified.
        """
        if not is_fsobject_dbid(modified_fsobject_dbid):
            raise ValueError(f"not a valid 'fsobject_dbid': {modified_fsobject_dbid!r}")

        with self._cursor_with_exception_mapping() as cursor:
            try:
                self._connection.commit()
                cursor.execute("BEGIN")

                # remove all explicit dependencies (of all tool instances) whose '`'fsobject_dbid' have
                # 'modified_fsobject_dbid' as a prefix
                cursor.execute(
                    "DELETE FROM ToolInstFsInput WHERE is_explicit == 1 AND instr(fsobject_dbid,?) == 1",
                    (modified_fsobject_dbid,))

                # replace the 'memo_before' all non-explicit dependencies (of all tool instances) whose
                # 'fsobject_dbid' have 'modified_fsobject_dbid' as a prefix by NULL
                cursor.execute(
                    "UPDATE ToolInstFsInput SET memo_before = NULL WHERE is_explicit == 0 "
                    "AND instr(fsobject_dbid,?) == 1",
                    (modified_fsobject_dbid,))

                self._connection.commit()
            except:
                self._connection.rollback()
                raise

    def commit(self):
        with self._cursor_with_exception_mapping('commit failed'):
            self._connection.commit()

    def cleanup(self):
        with self._cursor_with_exception_mapping('clean-up failed') as cursor:
            # remove unused tool dbids
            cursor.execute(
                "DELETE FROM ToolInst WHERE tool_inst_dbid IN ("
                    "SELECT ToolInst.tool_inst_dbid FROM ToolInst LEFT OUTER JOIN ToolInstFsInput "
                    "ON ToolInst.tool_inst_dbid = ToolInstFsInput.tool_inst_dbid "
                    "WHERE ToolInstFsInput.tool_inst_dbid IS NULL"
                ")")

    def close(self):
        # note: uncommitted changes are lost!
        with self._cursor_with_exception_mapping('closing failed'):
            self._connection.close()
        self._connection = None

    def _cursor_with_exception_mapping(self, summary_message_line: str = 'run-database access failed'):
        return _CursorWithExceptionMapping(
            self._connection,
            summary_message_line,
            self._suggestion_if_database_error
        )
