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

    def test_complete_all(self):

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

        results, exceptions = sequencer.complete_all(timeout=None)

        self.assertEqual(n, len(results) + len(exceptions))
        self.assertEqual(n, len(results))
        self.assertEqual(0, len(exceptions))

        r = {tid: 7 * tid + 5 + tid for tid in range(n)}
        self.assertEqual(r, results)

    def test_cancel_all(self):

        async def sleep_long():
            await asyncio.sleep(10.0)
            return 42

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        n = 3
        for i in range(n):
            sequencer.wait_then_start(n, None, sleep_long)

        results, exceptions = sequencer.cancel_all(timeout=None)

        self.assertEqual(n, len(results) + len(exceptions))
        self.assertEqual(0, len(results))
        self.assertEqual(n, len(exceptions))

        e = {tid: None for tid in range(n)}
        self.assertEqual(e, exceptions)

    def test_timeout(self):

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
            sequencer.complete_all(timeout=1.0)

        results, exceptions = sequencer.cancel_all(timeout=None)
        self.assertEqual(3, len(results) + len(exceptions))
        self.assertEqual(1, len(results))
        self.assertEqual({0: 0.5}, results)
        self.assertEqual({1: None, 2: None}, exceptions)

    def test_exception(self):

        async def sleep_or_raise(t):
            assert t > 0.0
            await asyncio.sleep(t)

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        sequencer.wait_then_start(3, None, sleep_or_raise, 0.5)
        sequencer.wait_then_start(3, None, sleep_or_raise, 0.0)  # raise AssertionError
        sequencer.wait_then_start(3, None, sleep_or_raise, 1.0)

        results, exceptions = sequencer.complete_all(timeout=None)
        self.assertEqual(3, len(results) + len(exceptions))
        self.assertEqual(1, len(exceptions))
        self.assertIsInstance(exceptions[1], AssertionError)

    def test_complete_returns_result_or_raises(self):

        async def sleep_or_raise(t):
            assert t > 0.0
            await asyncio.sleep(t)
            return t

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        tid = sequencer.wait_then_start(3, None, sleep_or_raise, 0.5)
        sequencer.wait_then_start(3, None, sleep_or_raise, 1.0)

        self.assertEqual(0.5, sequencer.complete(tid))
        with self.assertRaises(ValueError):
            sequencer.complete(tid)

        tid = sequencer.wait_then_start(3, None, sleep_or_raise, 0.0)

        with self.assertRaises(AssertionError):
            sequencer.complete(tid)

        results, exceptions = sequencer.complete_all(timeout=None)
        self.assertEqual(1, len(results) + len(exceptions))
        self.assertEqual(1, len(results))
        self.assertEqual({1: 1.0}, results)
