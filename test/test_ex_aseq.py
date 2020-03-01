# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex.aseq
import asyncio
import random
import unittest


class GetLevelMarkerTest(unittest.TestCase):

    def test_run_to_completion(self):

        async def sleep_randomly(a, b):
            dt = random.random()
            print(a, dt)
            await asyncio.sleep(0.2 + 0.5 * dt)
            r = a + b
            print(r)
            return r

        random.seed(0)

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        n = 5
        for i in range(n):
            sequencer.wait_then_start(3, None, sleep_randomly, 7 * i, b=5 + i)

        results, exceptions = sequencer.complete(timeout=None)

        self.assertEqual(n, len(results) + len(exceptions))
        self.assertEqual(n, len(results))
        self.assertEqual(0, len(exceptions))

        results.sort()
        r = [(
            (sleep_randomly, (7 * i,), {'b': 5 + i}),
            7 * i + 5 + i
        ) for i in range(n)]
        r.sort()

        self.assertEqual(sorted(r), sorted(results))

    def test_cancel(self):

        async def sleep_long():
            await asyncio.sleep(10.0)
            return 42

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        n = 3
        for i in range(n):
            sequencer.wait_then_start(n, None, sleep_long)

        results, exceptions = sequencer.cancel(timeout=None)

        self.assertEqual(n, len(results) + len(exceptions))
        self.assertEqual(0, len(results))
        self.assertEqual(n, len(exceptions))

        exceptions.sort()
        e = [((sleep_long, (), {}), None) for _ in range(n)]
        e.sort()

        self.assertEqual(sorted(e), sorted(exceptions))

    def test_timeout_does_not_lose_results(self):

        async def sleep(t):
            print('s', t)
            await asyncio.sleep(t)
            print('p', t)
            return t

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        sequencer.wait_then_start(3, 0.0, sleep, 0.5)
        sequencer.wait_then_start(3, 0.0, sleep, 2.5)
        sequencer.wait_then_start(3, 0.0, sleep, 3.0)
        with self.assertRaises(TimeoutError):
            sequencer.wait_then_start(3, 0.0, sleep, 0.0)

        with self.assertRaises(TimeoutError):
            sequencer.complete(timeout=1.0)

        results, exceptions = sequencer.cancel(timeout=None)
        self.assertEqual(3, len(results) + len(exceptions))
        self.assertEqual(1, len(results))
        self.assertEqual([((sleep, (0.5,), {}), 0.5)], results)
        self.assertEqual([None, None], [e for _, e in exceptions])

    def test_exception(self):

        async def sleep_or_raise(t):
            assert t > 0.0
            await asyncio.sleep(t)

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        sequencer.wait_then_start(3, None, sleep_or_raise, 0.5)
        sequencer.wait_then_start(3, None, sleep_or_raise, 0.0)  # raise AssertionError
        sequencer.wait_then_start(3, None, sleep_or_raise, 1.0)

        results, exceptions = sequencer.complete(timeout=None)
        self.assertEqual(3, len(results) + len(exceptions))
        self.assertEqual(1, len(exceptions))
        e = exceptions[0]
        self.assertEqual((sleep_or_raise, (0.0,), {}), e[0])
        self.assertIsInstance(e[1], AssertionError)
