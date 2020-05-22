# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Sequencing of a limited number of coroutines.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = []

import time
import asyncio
from typing import Any, Callable, Coroutine, Dict, Hashable, Optional, Set


class IdError(ValueError):
    pass


class LimitingCoroutineSequencer:
    # Runs coroutines in a common 'asyncio' loop and limits the number of pending coroutines started by
    # 'wait_then_start()'.
    # All public methods are normal synchronous methods, so this class acts as an intermediary between synchronous code
    # and coroutines.

    def __init__(self, asyncio_loop: Optional[asyncio.AbstractEventLoop] = None):
        if asyncio_loop is None:
            asyncio_loop = asyncio.get_event_loop()
        self._asyncio_loop = asyncio_loop
        self._tid_by_pending_task: Dict[asyncio.Task, int] = {}
        self._pending_task_by_tid: Dict[int, asyncio.Task] = {}
        self._next_tid = 0
        self._result_by_tid: Dict[int, Any] = {}
        self._exception_by_tid: Dict[int, BaseException] = {}

    def wait_then_start(self, _max_count: int, _timeout: Optional[float],
                        coro: Callable[[Any], Coroutine], *args, **kwargs) -> int:
        # Wait until no more than *_max_count* - 1 coroutines started by 'wait_then_run()' are pending, then
        # run 'coro(*args, **kwargs)'.
        #
        # Returns a non-negative integer as the task ID for the started task. The task ID is unique among all tasks
        # started by 'wait_then_start()' of this instance in the past and in the future.
        #
        # Does not wait until *coro* is done. Use 'complete()' to get the return value of *coro*.

        self._wait_for_pending_sync(max_count=int(_max_count) - 1, timeout=_timeout)

        # noinspection PyCallingNonCallable
        tid, self._next_tid = self._next_tid, self._next_tid + 1  # reserve task id unique for self
        task: asyncio.Task = self._asyncio_loop.create_task(coro(*args, **kwargs))  # is also a Future
        self._tid_by_pending_task[task] = tid
        self._pending_task_by_tid[tid] = task

        return tid

    def complete(self, tid: int, *, timeout: Optional[float]):
        # Wait until there is no pending task with task ID *tid*.
        # Use consume(tid) to consume the result.
        if tid in self._pending_task_by_tid:
            self._wait_for_pending_sync(max_count=0, tid_filter={tid}, timeout=timeout)

    def complete_all(self, *, timeout: Optional[float]):
        # Wait until all pending coroutines are done or cancelled.
        self._wait_for_pending_sync(max_count=0, timeout=timeout)

    def cancel_all(self, *, timeout: Optional[float]):
        for t in self._tid_by_pending_task:
            t.cancel()
        self.complete_all(timeout=timeout)

    def consume(self, tid: int):
        # Wait until the task with task ID *tid* is completed and return its result.

        result = self._result_by_tid.get(tid)
        if result is not None:
            del self._result_by_tid[tid]
            return result

        exception = self._exception_by_tid.get(tid)
        if exception is not None:
            del self._exception_by_tid[tid]
            raise exception

        raise IdError('nothing to consume for tid')

    def consume_all(self):
        results = self._result_by_tid
        exceptions = self._exception_by_tid

        self._result_by_tid = {}
        self._exception_by_tid = {}

        return results, exceptions

    async def _wait_until_number_of_pending(self, *, max_count: int, tid_filter: Optional[Set[int]],
                                            timeout_ns: int):
        max_count = max(0, max_count)

        t0 = time.monotonic_ns()
        while True:
            if tid_filter is None:
                tasks_to_wait_for = self._tid_by_pending_task.keys()
            else:
                tasks_to_wait_for = [t for t, tid in self._tid_by_pending_task.items() if tid in tid_filter]
            if len(tasks_to_wait_for) <= max_count:
                break

            if timeout_ns is None:
                timeout = None
            else:
                timeout = (timeout_ns - (time.monotonic_ns() - t0)) / 1e9
                if timeout <= 0.0:
                    raise TimeoutError

            done_tasks: Set[asyncio.Task]
            done_tasks, pending = await asyncio.wait(tasks_to_wait_for, return_when=asyncio.FIRST_COMPLETED,
                                                     timeout=timeout)  # does _not_ raise TimeoutError or CancelledError

            for task in done_tasks:  # "consume" all futures that are done
                tid = self._tid_by_pending_task.get(task)

                # tid is None: only seen when tasks were cancelled after KeyboardInterrupt (Python 3.7.3) under this
                # circumstances or RuntimeError('This event loop is already running').
                # pending is empty in this cases.

                if tid is not None:
                    del self._tid_by_pending_task[task]
                    del self._pending_task_by_tid[tid]

                try:
                    r = task.result()
                    if tid is not None:
                        self._result_by_tid[tid] = r
                except BaseException as e:  # asyncio.CancelledError if task.cancelled()
                    # Python 3.7: asyncio.CancelledError is a subclass of Exception
                    # Python 3.8: asyncio.CancelledError is _not_ a subclass of Exception
                    if tid is not None:
                        self._exception_by_tid[tid] = e

    def _wait_for_pending_sync(self, *, max_count: int, timeout: Optional[float],
                               tid_filter: Optional[Set[int]] = None):
        timeout_ns = None if timeout is None else max(0, int(timeout * 1e9))
        task = self._asyncio_loop.create_task(self._wait_until_number_of_pending(
            max_count=max_count, tid_filter=tid_filter, timeout_ns=timeout_ns))
        self._asyncio_loop.run_until_complete(task)


class _ResultProxy:

    def __init__(self, sequencer: 'LimitingResultSequencer', tid: int,
                 expected_class: type, timeout: Optional[float] = None):
        # Construct a ResultProxy for the result of a task of *sequencer* with task ID *tid*.
        # Each read access to an attribute not in this class waits for the task to complete and forwards the attribute
        # look-up to its return value.
        # Each "normal" write access to an attribute raises AttributeError.
        #
        # Instances should only be created by 'sequencer.create_result_proxy()'.

        object.__setattr__(self, '_sequencer', sequencer)
        object.__setattr__(self, '_tid', tid)
        object.__setattr__(self, '_expected_class', expected_class)
        object.__setattr__(self, '_timeout', timeout)
        object.__setattr__(self, '_result', None)
        object.__setattr__(self, '_exception', None)

    def __setattr__(self, key, value):
        raise AttributeError

    def __getattr__(self, item):
        return getattr(self._get_or_wait_for_result(), item)

    def __repr__(self) -> str:
        if self.iscomplete:
            return f"<proxy object for {self._result!r} result>"
        cls = self._expected_class
        if cls is None:
            return f"<proxy object for future result>"
        return f"<proxy object for future {cls!r} result>"

    @property
    def iscomplete(self) -> bool:
        return self._result is not None or self._exception is not None

    def _get_or_wait_for_result(self):
        if self._result is None:
            if self._exception is not None:
                raise self._exception
            self._sequencer.complete(self._tid, timeout=self._timeout)
            try:
                object.__setattr__(self, '_result', self._sequencer.consume(self._tid))
            except BaseException as e:
                object.__setattr__(self, '_exception', e)
                raise e from None
        return self._result


class LimitingResultSequencer(LimitingCoroutineSequencer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proxy_by_uid: Dict[Hashable, _ResultProxy] = {}
        self._proxy_uid_by_tid: Dict[int, Hashable] = {}

    def get_result_proxy(self, uid: Hashable) -> Optional[_ResultProxy]:
        return self._proxy_by_uid.get(uid, None)

    def consume(self, tid: int):
        uid = self._proxy_uid_by_tid.pop(tid, None)
        proxy = None if uid is None else self._proxy_by_uid.pop(uid, None)

        try:
            result = super().consume(tid)
            if proxy is not None:
                object.__setattr__(proxy, '_result', result)
        except BaseException as e:
            if proxy is not None:
                object.__setattr__(proxy, '_exception', e)
            raise

        return result

    def consume_all(self):
        results, exceptions = super().consume_all()

        for tid, r in results.items():
            uid = self._proxy_uid_by_tid.pop(tid, None)
            proxy = None if uid is None else self._proxy_by_uid.pop(uid, None)
            if proxy is not None:
                object.__setattr__(proxy, '_result', r)

        for tid, e in exceptions.items():
            uid = self._proxy_uid_by_tid.pop(tid, None)
            proxy = None if uid is None else self._proxy_by_uid.pop(uid, None)
            if proxy is not None:
                object.__setattr__(proxy, '_exception', e)

        return results, exceptions

    def create_result_proxy(self, tid: int, uid: Hashable, expected_class: Optional[type] = None) -> _ResultProxy:
        # Create a result proxy for the result of a task of this sequencer with task ID *tid* and assigned it
        # a unique *uid*.
        # Raises IdError if *tid* is not the task ID of a pending task with unconsumed result or if there already is
        # a result proxy with the same *tid* or 'id(uid)'.

        if not (tid in self._pending_task_by_tid or tid in self._result_by_tid or
                tid in self._exception_by_tid):
            raise IdError('nothing to consume for tid')

        if tid in self._proxy_uid_by_tid:
            raise IdError('tid is not unique')

        existing_proxy = self._proxy_by_uid.get(uid)
        if existing_proxy is not None:
            raise IdError('id(uid) is not unique')

        proxy = _ResultProxy(self, tid=tid, expected_class=expected_class)
        self._proxy_by_uid[uid] = proxy
        self._proxy_uid_by_tid[tid] = uid

        return proxy
