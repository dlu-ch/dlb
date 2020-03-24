# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@userd.noreply.github.com>

"""Abstraction of run-database.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = ('DatabaseError',)

import os.path
import enum
import time
import stat
import dataclasses
import datetime
import marshal  # very fast, reasonably secure, round-trip loss-less (see comment below)
import sqlite3
from typing import Optional, Union, Dict, List, Tuple
from .. import ut
from .. import fs
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


@dataclasses.dataclass
class FilesystemStatSummary:
    mode: int
    size: int
    mtime_ns: int
    uid: int
    gid: int


@dataclasses.dataclass
class FilesystemObjectMemo:
    stat: Optional[FilesystemStatSummary] = None
    symlink_target: Optional[str] = None


# unique identification of run-database schema among all versions (with a Git tag) of dlb declared as stable
SCHEMA_VERSION = (0, 1)


# note: without trailing 'Z'
# reason: comparable with different number of decimal places
_DATETIME_FORMAT = '%Y%m%dT%H%M%S.%f'


def is_encoded_path(encoded_path: str) -> bool:
    if not isinstance(encoded_path, str):
        return False
    if not encoded_path:
        return True
    return encoded_path[-1] == '/' and not encoded_path.startswith('./')


def encode_path(path: fs.Path) -> str:
    if not isinstance(path, fs.Path):
        raise TypeError
    if path.is_absolute() or not path.is_normalized():
        raise ValueError
    encoded_path = path.as_string()
    if encoded_path[-1:] != '/':
        encoded_path = encoded_path + '/'  # to enable efficient search for path prefixes in SQL
    if encoded_path[:2] == './':
        encoded_path = encoded_path[2:]
    return encoded_path


def decode_encoded_path_as_str(encoded_path: str) -> str:
    if not encoded_path:
        return '.'
    p = '/' + encoded_path
    if encoded_path[-1] != '/' or any(s in p for s in ('//', '/../', '/./')):
        raise ValueError
    return encoded_path


def decode_encoded_path(encoded_path: str, is_dir: bool = False) -> fs.Path:
    # must be fast
    s = decode_encoded_path_as_str(encoded_path)
    return fs.Path(s, is_dir=is_dir or s == '.')  # path from string is faster than from components


def encode_datetime(utc: datetime.datetime) -> str:
    s = utc.strftime(_DATETIME_FORMAT)
    while s[-1] == '0' and s[-2] != '.':
        s = s[:-1]  # remove trailing '0'
    return s


def decode_datetime(encoded_utc: str) -> datetime.datetime:
    return datetime.datetime.strptime(encoded_utc, _DATETIME_FORMAT)


def encode_fsobject_memo(memo: FilesystemObjectMemo) -> bytes:
    # Return a representation of *memo* as marshal-encoded tuple.

    if not isinstance(memo, FilesystemObjectMemo):
        raise TypeError

    if memo.stat is None:  # filesystem object did not exist
        return marshal.dumps(())  # != b''

    t = dataclasses.astuple(memo.stat)
    if not all(isinstance(f, int) for f in t):
        raise TypeError

    if not stat.S_ISLNK(memo.stat.mode) and memo.symlink_target is not None:
        raise ValueError

    if stat.S_ISLNK(memo.stat.mode) and not isinstance(memo.symlink_target, str):
        raise TypeError

    return marshal.dumps((
        memo.stat.mode, memo.stat.size, memo.stat.mtime_ns, memo.stat.uid, memo.stat.gid,
        memo.symlink_target))


def decode_encoded_fsobject_memo(encoded_memo: bytes) -> FilesystemObjectMemo:
    if not isinstance(encoded_memo, bytes):
        raise TypeError

    t = marshal.loads(encoded_memo)
    if not isinstance(t, tuple):
        raise ValueError

    if not t:
        return FilesystemObjectMemo()

    mode, size, mtime_ns, uid, gid, symlink_target = t  # ValueError if number does not match
    if not all(isinstance(f, int) for f in t[:5]):
        raise ValueError

    if not stat.S_ISLNK(mode) and symlink_target is not None:
        raise ValueError

    if stat.S_ISLNK(mode) and not isinstance(symlink_target, str):
        raise ValueError

    return FilesystemObjectMemo(
        stat=FilesystemStatSummary(mode=mode, size=size, mtime_ns=mtime_ns, uid=uid, gid=gid),
        symlink_target=symlink_target)


def compare_fsobject_memo_to_encoded_from_last_redo(memo: FilesystemObjectMemo, last_encoded_memo: Optional[bytes],
                                                    is_explicit: bool) -> Optional[str]:
    # Compares the present *memo* if a filesystem object in the managed tree that is an input dependency with its
    # last known encoded state *last_encoded_memo*, if any.
    #
    # Returns ``None`` if no redo is necessary due to the difference of *memo* and *last_encoded_memo* and
    # a short line describing the reason otherwise.

    if last_encoded_memo is None:
        if is_explicit:
            return 'output dependency of a tool instance potentially changed by a redo'
        return 'was a new dependency or was potentially changed by a redo'

    try:
        last_memo = decode_encoded_fsobject_memo(last_encoded_memo)
    except ValueError:
        return 'state before last successful redo is unknown'

    if is_explicit:
        assert memo.stat is not None
        if last_memo.stat is None:
            return 'filesystem object did not exist'
    elif (memo.stat is None) != (last_memo.stat is None):
        return 'existence has changed'
    elif memo.stat is None:
        # non-explicit dependency of a filesystem object that does not exist and did not exist before the
        # last successful redo
        return None

    assert memo.stat is not None
    assert last_memo.stat is not None

    if stat.S_IFMT(memo.stat.mode) != stat.S_IFMT(last_memo.stat.mode):
        return 'type of filesystem object has changed'

    if stat.S_ISLNK(memo.stat.mode) and memo.symlink_target != last_memo.symlink_target:
        return 'symbolic link target has changed'

    if memo.stat.size != last_memo.stat.size:
        return 'size has changed'

    if memo.stat.mtime_ns != last_memo.stat.mtime_ns:
        return 'mtime has changed'

    if (memo.stat.mode, memo.stat.uid, memo.stat.gid) != \
            (last_memo.stat.mode, last_memo.stat.uid, last_memo.stat.gid):
        return 'permissions or owner have changed'


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
                lines.append(f"{self._summary_message_line}")
            lines.append(ut.exception_to_line(exc_val, True))
            if self._solution_message_line:
                lines.append(self._solution_message_line)

            msg = '\n  | '.join(lines)
            raise DatabaseError(msg) from None


@enum.unique
class Domain(enum.Enum):
    EXECUTION_PARAMETERS = 'execparam'
    ENVIRONMENT_VARIABLES = 'envvar'

    # redo request of last successful redo
    # if present and not empty: redo
    REDO_REQUEST = 'request'


class Database:

    def __init__(self, rundb_path: Union[str, os.PathLike], suggestion_if_database_error: str = ''):
        # Open or create the database with path *rundb_path*.
        #
        # *suggestion_if_database_error* should be a non-empty line suggesting a recovery solution for database errors.
        #
        # Until :meth:`close()' is called on this object, no other process must construct an object with the same
        # *rundb_path*.

        self._suggestion_if_database_error = str(suggestion_if_database_error)

        try:
            connection = sqlite3.connect(rundb_path, isolation_level='DEFERRED')  # raises sqlite3.Error on error
        except sqlite3.Error as e:
            exists = os.path.isfile(rundb_path)  # does not raise OSError
            state_msg = 'existing' if exists else 'non-existent'
            reason = ut.exception_to_line(e, True)
            msg = (
                f"could not open {state_msg} run-database: {rundb_path!r}\n"
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
                "CREATE TABLE IF NOT EXISTS Run("
                    "run_dbid INTEGER NOT NULL, "   # unique id of dlb run among dlb run with this run-database
                    "start_time TEXT NOT NULL, "    # start UTC date/time of dlb run in ISO 8601 basic format 
                                                    # like this "20200318T153032.001Z"
                    "duration_ns INTEGER, "         # duration since start (clipped at 2**63 - 1) or
                                                    # NULL if not successful
                    "nonredo_count INTEGER, "       # number of non-redo runs of any tool instance
                                                    # (clipped at 2**63 - 1) or NULL if not successful
                    "redo_count INTEGER, "          # number of redo runs of any tool instance 
                                                    # (clipped at 2**63 - 1) or NULL if not successful
                    "PRIMARY KEY(run_dbid)"         # makes run_dbid an AUTOINCREMENT field
                "); "

                "CREATE TABLE IF NOT EXISTS ToolInst("
                    "tool_inst_dbid INTEGER NOT NULL, "   # unique id of tool instance across dlb run and platforms
                                                          # (until next cleanup)

                    "pl_platform_id BLOB NOT NULL, "      # permanent local platform id
                    "pl_tool_id BLOB NOT NULL, "          # permanent local tool id (unique among all tool with
                                                          # same pl_platform_id)
                    "pl_tool_inst_fp BLOB NOT NULL, "     # permanent local tool instance fingerprint
                                                          # ("almost unique" among all tool instances with
                                                          # same pl_platform_id and pl_tool_id)

                    "PRIMARY KEY(tool_inst_dbid)"         # makes tool_inst_dbid an AUTOINCREMENT field
                    "UNIQUE(pl_platform_id, pl_tool_id, pl_tool_inst_fp)"
                "); "

                "CREATE TABLE IF NOT EXISTS ToolInstFsInput("
                    "tool_inst_dbid INTEGER, "         # tool instance
                    "path TEXT NOT NULL, "             # path of filesystem object in managed tree,
                                                       # encoded by encode_path
                    "is_explicit INTEGER NOT NULL, "   # 0 for implicit, 1 for explicit dependency of tool instance
                    "memo_before BLOB, "               # memo of filesystem object before last redo of tool instance,
                                                       # encoded by encode_fsobject_memo(), or NULL if
                                                       # filesystem object was modified since last redo
                    "run_dbid INTEGER, "               # run_dbid of last update
                    "PRIMARY KEY(tool_inst_dbid, path), "
                    "FOREIGN KEY(tool_inst_dbid) REFERENCES ToolInst(tool_inst_dbid), "
                    "FOREIGN KEY(run_dbid) REFERENCES Run(run_dbid)"
                "); "

                "CREATE TABLE IF NOT EXISTS ToolInstDomainInput("
                    "tool_inst_dbid INTEGER, "             # tool instance
                    "domain TEXT NOT NULL, "               # name of domain (one of Domain)
                    "memo_digest_before BLOB NOT NULL, "   # memo of filesystem object before last redo of tool instance
                    "run_dbid INTEGER, "                   # run_dbid of last update
                    "PRIMARY KEY(tool_inst_dbid, domain), "
                    "FOREIGN KEY(tool_inst_dbid) REFERENCES ToolInst(tool_inst_dbid), "
                    "FOREIGN KEY(run_dbid) REFERENCES Run(run_dbid)"
                "); "

                "CREATE TRIGGER IF NOT EXISTS delete_obsolete_toolinst "
                    "AFTER DELETE ON Run FOR EACH ROW BEGIN "
                        "DELETE FROM ToolInstFsInput WHERE run_dbid = OLD.run_dbid; "
                        "DELETE FROM ToolInstDomainInput WHERE run_dbid = OLD.run_dbid; "
                    "END; "

                # https://sqlite.org/pragma.html
                "PRAGMA locking_mode = EXCLUSIVE; "    # https://blog.devart.com/increasing-sqlite-performance.html
                "PRAGMA foreign_keys = ON;"            # https://www.sqlite.org/foreignkeys.html
            )

            # assign tool_inst_dbid by AUTOINCREMENT:
            self._start_datetime = datetime.datetime.utcnow()
            cursor.execute("INSERT INTO Run VALUES (NULL, ?, NULL, NULL, NULL)",
                           (encode_datetime(self._start_datetime),))
            cursor.execute("SELECT last_insert_rowid()")  # https://www.sqlite.org/c3ref/last_insert_rowid.html
            self._run_dbid = cursor.fetchone()[0]
            self._start_time_ns = time.monotonic_ns()  # since Python 3.7

            connection.commit()

        self._connection = connection

    @property
    def run_dbid(self) -> int:
        return self._run_dbid

    @property
    def start_datetime(self) -> datetime.datetime:
        return self._start_datetime

    def get_and_register_tool_instance_dbid(self, permanent_local_tool_id: bytes,
                                            permanent_local_tool_instance_fingerprint: bytes) -> int:
        # Return a tool instance dbid *tool_instance_dbid* for a tool instance identified by
        # *permanent_local_tool_id* and *permanent_local_tool_instance_fingerprint* on the current platform.
        #
        # *tool_instance_dbid* is unique in the run-database until the next :meth:`cleanup()` on this object.
        #
        # When called more than one before the next cleanup() on this object, this always returns the same value.

        t = (platform.PERMANENT_PLATFORM_ID, permanent_local_tool_id, permanent_local_tool_instance_fingerprint)
        with self._cursor_with_exception_mapping() as cursor:
            # assign tool_inst_dbid by AUTOINCREMENT:
            cursor.execute("INSERT OR IGNORE INTO ToolInst VALUES (NULL, ?, ?, ?)", t)
            cursor.execute("SELECT tool_inst_dbid FROM ToolInst WHERE "
                           "pl_platform_id = ? AND pl_tool_id = ? AND pl_tool_inst_fp = ?", t)
            tool_instance_dbid = cursor.fetchone()[0]

        return tool_instance_dbid

    def get_tool_instance_dbid_count(self) -> int:
        # Returns the number of (different) registered *tool_instance_dbid* for the current platform.

        with self._cursor_with_exception_mapping() as cursor:
            n = cursor.execute(
                "SELECT COUNT(*) FROM ToolInst WHERE pl_platform_id = ?",
                (platform.PERMANENT_PLATFORM_ID,)
            ).fetchall()[0][0]

        return n

    def update_fsobject_input(self, tool_instance_dbid: int, encoded_path: str, is_explicit: bool,
                              encoded_memo_before: Optional[bytes]):
        # Add or replace the description of a filesystem object in the managed tree that is an input dependency
        # of the tool instance *tool_instance_dbid* by ``(is_explicit, encoded_memo_before``).
        #
        # *tool_instance_dbid* must be the value returned by call of :meth:`get_and_register_tool_instance_dbid()` since
        # not before the last :meth:`cleanup()` (if any).
        #
        # *encoded_path* must be the return value of :func:`encode_path()`.

        if not is_encoded_path(encoded_path):
            raise ValueError(f"not a valid 'encoded_path': {encoded_path!r}")

        if encoded_memo_before is not None and not isinstance(encoded_memo_before, bytes):
            raise TypeError(f"not a valid 'encoded_memo_before': {encoded_memo_before!r}")

        with self._cursor_with_exception_mapping() as cursor:
            cursor.execute("INSERT OR REPLACE INTO ToolInstFsInput VALUES (?, ?, ?, ?, ?)", (
                tool_instance_dbid, encoded_path, 1 if is_explicit else 0, encoded_memo_before, self.run_dbid))

    def replace_fsobject_inputs(self, tool_instance_dbid: int,
                                info_by_by_fsobject_dbid: Dict[str, Tuple[bool, bytes]]):
        # Replace all information on filesystem object input dependencies for a tool instance *tool_instance_dbid* by
        # *info_by_by_fsobject_dbid*.
        #
        # Includes a :meth:`commit()` at the start.
        # In case of an exception, the information on input dependencies in the run-database remains unchanged.

        with self._cursor_with_exception_mapping() as cursor:
            try:
                self._connection.commit()
                cursor.execute("BEGIN")
                cursor.execute("DELETE FROM ToolInstFsInput WHERE tool_inst_dbid == ?", (tool_instance_dbid,))
                for encoded_path, info in info_by_by_fsobject_dbid.items():
                    is_explicit, encoded_memo_before = info
                    self.update_fsobject_input(tool_instance_dbid, encoded_path, is_explicit, encoded_memo_before)
            except:
                self._connection.rollback()
                raise

    def get_fsobject_inputs(self, tool_instance_dbid: int, is_explicit_filter: Optional[bool] = None) \
            -> Dict[str, Tuple[bool, Optional[bytes]]]:
        # Return the *encoded_path* and the optional encoded memo of all filesystem objects in the managed tree that are
        # input dependencies of the tool instance *tool_instance_dbid*.
        #
        # If *is_explicit_filter* is not ``None``, only the dependencies with *is_explicit* = *is_explicit_filter* are
        # returned.
        #
        # *tool_instance_dbid* must be the value returned by call of :meth:`get_and_register_tool_instance_dbid()` since
        # the last :meth:`cleanup()` (if any).

        with self._cursor_with_exception_mapping() as cursor:

            if is_explicit_filter is None:
                rows = cursor.execute(
                    "SELECT path, is_explicit, memo_before FROM ToolInstFsInput WHERE tool_inst_dbid == ?",
                    (tool_instance_dbid,)).fetchall()
            else:
                rows = cursor.execute(
                    "SELECT path, is_explicit, memo_before FROM ToolInstFsInput "
                    "WHERE tool_inst_dbid == ? AND is_explicit == ?",
                    (tool_instance_dbid, 1 if is_explicit_filter else 0)).fetchall()

        return {
            encoded_path: (bool(is_explicit), encoded_memo_before)
            for encoded_path, is_explicit, encoded_memo_before in rows
        }

    def declare_fsobject_input_as_modified(self, modified_encoded_path: str):
        # Declare the filesystem objects in the managed tree that are input dependencies (of any tool instance) as
        # modified if
        #
        #   - their *encoded_path* = *modified_encoded_path* or
        #   - their managed tree path is a prefix of the path of the filesystem object identified
        #     by *modified_encoded_path*
        #
        # In case of an exception, the information on input dependencies in the run-database remains unchanged.
        #
        # Note: call :meth:`commit()` before the filesystem object is actually modified.

        if not is_encoded_path(modified_encoded_path):
            raise ValueError(f"not a valid 'encoded_path': {modified_encoded_path!r}")

        with self._cursor_with_exception_mapping() as cursor:
            # replace the 'memo_before' all non-explicit dependencies (of all tool instances) whose
            # 'encoded_path' have 'modified_encoded_path' as a prefix by NULL
            cursor.execute(
                "UPDATE ToolInstFsInput SET memo_before = NULL WHERE instr(path, ?) == 1",
                (modified_encoded_path,))

    def get_domain_inputs(self, tool_instance_dbid: int) -> Dict[str, bytes]:
        # Return the *domain* and the memo digest of all domain input dependencies of the tool
        # instance *tool_instance_dbid*.
        #
        # *tool_instance_dbid* must be the value returned by call of :meth:`get_and_register_tool_instance_dbid()` since
        # the last :meth:`cleanup()` (if any).
        with self._cursor_with_exception_mapping() as cursor:
            rows = cursor.execute(
                "SELECT domain, memo_digest_before FROM ToolInstDomainInput WHERE tool_inst_dbid == ?",
                (tool_instance_dbid,)).fetchall()
        return {domain: memo_digest_before for domain, memo_digest_before in rows}

    def replace_domain_inputs(self, tool_instance_dbid: int,
                              memo_digest_before_by_domain: Dict[str, Optional[bytes]]):
        # Replace all information on domain input dependencies for a tool instance *tool_instance_dbid* by
        # *memo_digest_before_by_domain*.
        #
        # Includes a :meth:`commit()` at the start.
        # In case of an exception, the information on input dependencies in the run-database remains unchanged.

        with self._cursor_with_exception_mapping() as cursor:
            try:
                self._connection.commit()
                cursor.execute("BEGIN")
                cursor.execute("DELETE FROM ToolInstDomainInput WHERE tool_inst_dbid == ?", (tool_instance_dbid,))
                for domain, memo_digest_before in memo_digest_before_by_domain.items():
                    if memo_digest_before is not None:
                        cursor.execute("INSERT OR REPLACE INTO ToolInstDomainInput VALUES (?, ?, ?, ?)",
                                       (tool_instance_dbid, domain, memo_digest_before, self.run_dbid))
            except:
                self._connection.rollback()
                raise

    def get_latest_successful_run_summaries(self, max_count: int) -> List[Tuple[datetime.datetime, int, int, int]]:
        # Without the run that opened this run-database.
        # Note: There is no guaranteed that all the datetimes differ.

        max_count = max(0, int(max_count))

        summaries = []
        with self._cursor_with_exception_mapping() as cursor:
            for start_time, duration_ns, nonredo_count, redo_count in cursor.execute(
                    "SELECT start_time, duration_ns, nonredo_count, redo_count FROM Run "
                    "WHERE run_dbid != ? AND duration_ns >= 0 AND nonredo_count >= 0 AND redo_count >= 0 "
                    "ORDER BY start_time DESC LIMIT ?", (self.run_dbid, max_count)).fetchall():
                summaries.append((decode_datetime(start_time), duration_ns, nonredo_count + redo_count, redo_count))

        summaries.reverse()
        return summaries

    def update_run_summary(self, successful_nonredo_run_count: int, successful_redo_run_count: int) -> \
            Tuple[datetime.datetime, int, int, int]:
        # Consider the dlb run as successfully completed.

        duration_ns = time.monotonic_ns() - self._start_time_ns  # since Python 3.7
        duration_ns = max(0, min(2**63 - 1, duration_ns))
        successful_nonredo_run_count = max(0, min(2**63 - 1, successful_nonredo_run_count))
        successful_redo_run_count = max(0, min(2**63 - 1, successful_redo_run_count))

        with self._cursor_with_exception_mapping() as cursor:
            # https://www.sqlite.org/datatype3.html
            cursor.execute(
                "UPDATE Run SET duration_ns = ?, nonredo_count = ?, redo_count = ? WHERE run_dbid = ?",
                (duration_ns, successful_nonredo_run_count, successful_redo_run_count, self.run_dbid))

        return self._start_datetime, duration_ns, \
               successful_nonredo_run_count + successful_redo_run_count, successful_redo_run_count  # TODO test

    def forget_runs_before(self, utc: datetime.datetime):
        # Remove information on run started before *utc* an all dependency information last updated by such
        # a run.
        encoded_utc = encode_datetime(utc)
        with self._cursor_with_exception_mapping() as cursor:
            cursor.execute("DELETE FROM Run WHERE start_time < ?", (encoded_utc,))

    def commit(self):
        with self._cursor_with_exception_mapping('commit failed'):
            self._connection.commit()

    def cleanup(self):
        with self._cursor_with_exception_mapping('clean-up failed') as cursor:
            # remove unused tool dbids
            cursor.execute(
                "DELETE FROM ToolInst WHERE tool_inst_dbid IN ("
                    "SELECT ti.tool_inst_dbid FROM ToolInst AS ti "
                        "LEFT OUTER JOIN ToolInstFsInput AS fs ON ti.tool_inst_dbid = fs.tool_inst_dbid "
                        "LEFT OUTER JOIN ToolInstDomainInput AS do ON ti.tool_inst_dbid = do.tool_inst_dbid "
                    "WHERE fs.tool_inst_dbid IS NULL AND do.tool_inst_dbid IS NULL"
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


ut.set_module_name_to_parent_by_name(vars(), __all__)
