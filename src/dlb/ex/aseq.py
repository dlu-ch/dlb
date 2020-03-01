# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Sequencing of a limited number of coroutines."""

import sys
import time
import asyncio
from typing import Optional, Any, List, Tuple, Dict, Callable, Coroutine, Set

assert sys.version_info >= (3, 7)


class LimitingCoroutineSequencer:
    # Runs coroutines in a common 'asyncio' loop and limits the number of pending coroutines started by
    # 'wait_then_start()'.
    # All public methods are normal synchronous methods, so this class acts as an intermediary between synchronous code
    # and coroutines.

    def __init__(self, asyncio_loop: asyncio.AbstractEventLoop):
        self._asyncio_loop = asyncio_loop
        self._tid_by_pending_task: Dict[asyncio.Task, int] = dict()
        self._pending_task_by_tid: Dict[int, asyncio.Task] = dict()
        self._next_tid = 0
        self._results: List[Tuple[int, Any]] = []
        self._optional_exceptions: List[Tuple[int, Optional[Exception]]] = []

    def wait_then_start(self, _max_count: int, _timeout: Optional[float],
                        coro: Callable[[Any], Coroutine], *args, **kwargs) -> int:
        # Wait until no more than *_max_count* - 1 coroutines started by 'wait_then_run()' are pending, then
        # run 'coro(*args, **kwargs)'.
        #
        # Returns a non-negative integer as the task ID for the started task. The task ID is unique among all tasks
        # started by 'wait_then_start()' of this instance in the past and in the future.
        #
        # Does not wait until *coro* is done. Use 'complete()' to get the return value of *coro*.

        results, exceptions = self._wait_for_pending_sync(max_count=int(_max_count) - 1, timeout=_timeout)
        self._results.extend(results)
        self._optional_exceptions.extend(exceptions)
        # noinspection PyCallingNonCallable
        tid, self._next_tid = self._next_tid, self._next_tid + 1  # reserve task id unique for self
        task: asyncio.Task = self._asyncio_loop.create_task(coro(*args, **kwargs))  # is also a Future
        self._tid_by_pending_task[task] = tid
        self._pending_task_by_tid[tid] = task
        return tid

    def complete(self, tid: int):
        # Wait until the task with task ID *tid* is completed and return its result.

        task = self._pending_task_by_tid.get(tid)
        if task is None:
            raise ValueError("not a tid of a pending task")
        try:
            result = self._asyncio_loop.run_until_complete(task)
        finally:
            del self._tid_by_pending_task[task]
            del self._pending_task_by_tid[tid]

        return result

    def complete_all(self, *, timeout: Optional[float]):
        # Wait until all pending coroutines are done or cancelled.
        #
        # Returns a tuple '(results, optional_exceptions)'.
        # *results* is a dictionary with the task ID of all completed couroutines as key and their result as value.
        # *optional_exceptions* is a dictionary with the task ID of all completed couroutines as key and their
        # raised exception or None (if cancelled) as value.

        results, optional_exceptions = self._wait_for_pending_sync(max_count=0, timeout=timeout)

        results = {tid: r for tid, r in self._results + results}
        optional_exceptions = {tid: e for tid, e in self._optional_exceptions + optional_exceptions}

        self._results = []
        self._optional_exceptions = []
        return results, optional_exceptions

    def cancel_all(self, *, timeout: Optional[float]):
        for t in self._tid_by_pending_task:
            t.cancel()
        return self.complete_all(timeout=timeout)

    async def _wait_until_number_of_pending(self, *, max_count: int, timeout_ns: int):
        max_count = max(0, max_count)

        previous_result_count = len(self._results)
        previous_optional_exception_count = len(self._optional_exceptions)

        t0 = time.monotonic_ns()
        while len(self._tid_by_pending_task) > max_count:
            if timeout_ns is None:
                timeout = None
            else:
                timeout = (timeout_ns - (time.monotonic_ns() - t0)) / 1e9
                if timeout <= 0.0:
                    raise TimeoutError

            done_tasks: Set[asyncio.Task]
            done_tasks, pending = await asyncio.wait(self._tid_by_pending_task, return_when=asyncio.FIRST_COMPLETED,
                                                     timeout=timeout)  # does _not_ raise TimeoutError

            for task in done_tasks:  # "consume" all futures that are done
                tid = self._tid_by_pending_task.get(task)

                # tid is None: only seen when tasks were cancelled after KeyboardInterrupt (Python 3.7.3) under this
                # circumstances:
                #
                #  - pending is empty
                #  - task.cancelled() is True

                if tid is not None:
                    del self._tid_by_pending_task[task]
                    del self._pending_task_by_tid[tid]

                if task.cancelled():
                    self._optional_exceptions.append((tid, None))  # None instead of asyncio.CancelledError
                else:
                    try:
                        self._results.append((tid, task.result()))
                    except Exception as e:  # asyncio.CancelledError possible (in theory)
                        self._optional_exceptions.append((tid, e))

        results = self._results[previous_result_count:]
        optional_exceptions = self._optional_exceptions[previous_optional_exception_count:]

        del self._results[previous_result_count:]
        del self._optional_exceptions[previous_optional_exception_count:]

        return results, optional_exceptions

    def _wait_for_pending_sync(self, *, max_count: int, timeout: Optional[float]):
        timeout_ns = None if timeout is None else max(0, int(timeout * 1e9))
        task = self._asyncio_loop.create_task(self._wait_until_number_of_pending(
            max_count=max_count, timeout_ns=timeout_ns))
        self._asyncio_loop.run_until_complete(task)
        results, optional_exceptions = task.result()
        return results, optional_exceptions
