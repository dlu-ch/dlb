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


class LimitingCoroutineSequencerTest(unittest.TestCase):

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

        sequencer.complete_all(timeout=None)
        results, exceptions = sequencer.consume_all()

        self.assertEqual(n, len(results) + len(exceptions))
        self.assertEqual(n, len(results))
        self.assertEqual(0, len(exceptions))

        r = {tid: 7 * tid + 5 + tid for tid in range(n)}
        self.assertEqual(r, results)

        results, exceptions = sequencer.consume_all()
        self.assertEqual({}, results)
        self.assertEqual({}, exceptions)

    def test_cancel_all(self):

        async def sleep_long():
            await asyncio.sleep(10.0)
            return 42

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        n = 3
        for i in range(n):
            sequencer.wait_then_start(n, None, sleep_long)

        sequencer.cancel_all(timeout=None)
        results, exceptions = sequencer.consume_all()

        self.assertEqual(n, len(results) + len(exceptions))
        self.assertEqual(0, len(results))
        self.assertEqual(n, len(exceptions))
        self.assertTrue(all(isinstance(e, asyncio.CancelledError) for e in exceptions.values()))

        results, exceptions = sequencer.consume_all()
        self.assertEqual({}, results)
        self.assertEqual({}, exceptions)

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

        sequencer.cancel_all(timeout=None)
        results, exceptions = sequencer.consume_all()
        self.assertEqual(3, len(results) + len(exceptions))
        self.assertEqual(1, len(results))
        self.assertEqual({0: 0.5}, results)
        self.assertTrue([1, 2], sorted(exceptions))
        self.assertTrue(all(isinstance(e, asyncio.CancelledError) for e in exceptions.values()))

    def test_exception(self):

        async def sleep_or_raise(t):
            assert t > 0.0
            await asyncio.sleep(t)

        sequencer = dlb.ex.aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())

        sequencer.wait_then_start(3, None, sleep_or_raise, 0.5)
        sequencer.wait_then_start(3, None, sleep_or_raise, 0.0)  # raise AssertionError
        sequencer.wait_then_start(3, None, sleep_or_raise, 1.0)

        sequencer.complete_all(timeout=None)
        results, exceptions = sequencer.consume_all()
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

        sequencer.complete(tid, timeout=None)
        self.assertEqual(0.5, sequencer.consume(tid))
        sequencer.complete(tid, timeout=None)
        with self.assertRaises(ValueError):
            sequencer.consume(tid)

        tid = sequencer.wait_then_start(3, None, sleep_or_raise, 0.0)

        sequencer.complete(tid, timeout=None)
        with self.assertRaises(AssertionError):
            sequencer.consume(tid)

        sequencer.complete_all(timeout=None)
        results, exceptions = sequencer.consume_all()
        self.assertEqual(1, len(results) + len(exceptions))
        self.assertEqual(1, len(results))
        self.assertEqual({1: 1.0}, results)


class LimitingResultSequencerTest(unittest.TestCase):

    class Result:
        def __init__(self, value):
            self.value = value

    @staticmethod
    async def sleep_or_raise(t):
        assert t > 0.0
        await asyncio.sleep(t)
        return LimitingResultSequencerTest.Result(t)

    def test_result_attributes_are_readonly(self):

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.5)

        proxy = sequencer.create_result_proxy(tid, uid=1)
        with self.assertRaises(AttributeError):
            proxy.value = 27

        sequencer.cancel_all(timeout=None)

    def test_fails_for_nonunique_uid(self):
        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid1 = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.5)
        tid2 = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.75)

        proxy = sequencer.create_result_proxy(tid1, uid=1)
        self.assertFalse(proxy)  # not complete

        with self.assertRaises(dlb.ex.aseq.IdError) as cm:
            sequencer.create_result_proxy(tid1, uid=2)
        self.assertEqual("tid is not unique", str(cm.exception))

        with self.assertRaises(dlb.ex.aseq.IdError) as cm:
            sequencer.create_result_proxy(tid2, uid=1)
        self.assertEqual("id(uid) is not unique", str(cm.exception))

        with proxy:
            pass

        with self.assertRaises(dlb.ex.aseq.IdError) as cm:
            sequencer.create_result_proxy(tid1, uid=1)
        self.assertEqual("nothing to consume for tid", str(cm.exception))

        sequencer.create_result_proxy(tid2, uid=1)  # can resue uid

        sequencer.cancel_all(timeout=None)

    def test_attribute_access_completes(self):

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.5)

        uid = 1
        proxy = sequencer.create_result_proxy(tid, uid)
        self.assertFalse(proxy)  # not complete

        p = sequencer.get_result_proxy(uid)
        self.assertIs(proxy, p)
        self.assertFalse(proxy)  # not complete

        self.assertEqual(0.5, proxy.value)  # waits for completion
        self.assertTrue(proxy)  # complete

        self.assertIsNone(sequencer.get_result_proxy(uid))

    def test_context_manager_completes(self):

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.5)

        uid = 1
        proxy = sequencer.create_result_proxy(tid, uid)
        self.assertFalse(proxy)  # not complete

        with proxy:
            pass

        self.assertTrue(proxy)  # complete
        self.assertEqual(0.5, proxy.value)

    def test_consume_all_completes(self):

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.5)

        proxy = sequencer.create_result_proxy(tid, uid=1)

        self.assertFalse(proxy)  # not complete
        sequencer.cancel_all(timeout=None)
        self.assertFalse(proxy)  # not complete

        sequencer.consume_all()
        self.assertTrue(proxy)  # complete

    def test_attribute_before_completion_access_raises_exception(self):

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.0)

        proxy = sequencer.create_result_proxy(tid, uid=1)

        self.assertFalse(proxy)  # not complete
        with self.assertRaises(AssertionError):
            proxy.value

        with self.assertRaises(AssertionError):
            proxy.value  # and again

    def test_attribute_after_completion_access_raises_exception(self):

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, LimitingResultSequencerTest.sleep_or_raise, 0.0)

        proxy = sequencer.create_result_proxy(tid, uid=1)

        self.assertFalse(proxy)  # not complete
        sequencer.complete_all(timeout=None)
        self.assertFalse(proxy)  # not complete

        sequencer.consume_all()
        self.assertTrue(proxy)  # complete

        with self.assertRaises(AssertionError):
            proxy.value

        with self.assertRaises(AssertionError):
            proxy.value  # and again


class ResultProxyReprTest(unittest.TestCase):

    def test_repr_is_meaningful_without_expected_class(self):

        async def return_int():
            return 42

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, return_int)

        proxy = sequencer.create_result_proxy(tid, uid=1)
        s = repr(proxy)
        self.assertEqual('<proxy object for future result>', s)

        with proxy:
            pass

        s = repr(proxy)
        self.assertEqual('<proxy object for 42 result>', s)

    def test_repr_is_meaningful_with_expected_class(self):

        async def return_int():
            return 42

        sequencer = dlb.ex.aseq.LimitingResultSequencer(asyncio.get_event_loop())
        tid = sequencer.wait_then_start(3, None, return_int)

        proxy = sequencer.create_result_proxy(tid, uid=1, expected_class=int)
        s = repr(proxy)
        self.assertEqual("<proxy object for future <class 'int'> result>", s)

        with proxy:
            pass

        s = repr(proxy)
        self.assertEqual('<proxy object for 42 result>', s)
