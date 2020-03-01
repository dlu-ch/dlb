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
    # All methods are "synchronous", so this class acts as a ??? between ??? and async???.

    def __init__(self, asyncio_loop: asyncio.AbstractEventLoop):
        self._asyncio_loop = asyncio_loop
        self._args_by_pending_task: Dict[asyncio.Task, Tuple[Any, Tuple, Dict]] = dict()
        self._results: List[Tuple[Tuple[Coroutine, Tuple, Dict[str, Any]], Any]] = []
        self._optional_exceptions: List[Tuple[Tuple[Coroutine, Tuple, Dict[str, Any]], Optional[Exception]]] = []

    def wait_then_start(self, _max_count: int, _timeout: Optional[float],
                        coro: Callable[[Any], Coroutine], *args, **kwargs):
        # Wait until no more than *_max_count* - 1 coroutines started by 'wait_then_run()' are pending, then
        # run 'coro(*args, **kwargs)'.
        #
        # Does not wait until *coro* is done. Use 'complete()' to get the return value of *coro*.

        results, exceptions = self._wait_for_pending_sync(max_count=int(_max_count) - 1, timeout=_timeout)
        self._results.extend(results)
        self._optional_exceptions.extend(exceptions)
        # noinspection PyCallingNonCallable
        task: asyncio.Task = self._asyncio_loop.create_task(coro(*args, **kwargs))  # is also a Future
        self._args_by_pending_task[task] = (coro, args, kwargs)

    def complete(self, *, timeout: Optional[float]):
        # Wait until all pending coroutines are done or cancelled.
        #
        # Returns a list of results (sig, r) and a list of optional exceptions (sig, e), where sig is
        # (coro, args, kwargs) from wait_then_start(), r is the return value of coro and e is the exception raised by
        # coro or None if coro was cancelled.

        results, optional_exceptions = self._wait_for_pending_sync(max_count=0, timeout=timeout)
        results = self._results + results
        optional_exceptions = self._optional_exceptions + optional_exceptions
        self._results = []
        self._optional_exceptions = []
        return results, optional_exceptions

    def cancel(self, *, timeout: Optional[float]):
        for t in self._args_by_pending_task:
            t.cancel()
        return self.complete(timeout=timeout)

    async def _wait_until_number_of_pending(self, *, max_count: int, timeout_ns: int):
        max_count = max(0, max_count)

        previous_result_count = len(self._results)
        previous_optional_exception_count = len(self._optional_exceptions)

        t0 = time.monotonic_ns()
        while len(self._args_by_pending_task) > max_count:
            if timeout_ns is None:
                timeout = None
            else:
                timeout = (timeout_ns - (time.monotonic_ns() - t0)) / 1e9
                if timeout <= 0.0:
                    raise TimeoutError

            done_tasks: Set[asyncio.Task]
            done_tasks, pending = await asyncio.wait(self._args_by_pending_task, return_when=asyncio.FIRST_COMPLETED,
                                                     timeout=timeout)  # does _not_ raise TimeoutError

            for task in done_tasks:  # "consume" all futures that are done
                args = self._args_by_pending_task.get(task)

                # args is None: only seen when tasks were cancelled after KeyboardInterrupt (Python 3.7.3) under this
                # circumstances:
                #
                #  - pending is empty
                #  - task.cancelled() is True

                if args is not None:
                    del self._args_by_pending_task[task]

                if task.cancelled():
                    self._optional_exceptions.append((args, None))  # None instead of asyncio.CancelledError
                else:
                    try:
                        self._results.append((args, task.result()))
                    except Exception as e:  # asyncio.CancelledError possible (in theory)
                        self._optional_exceptions.append((args, e))

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
